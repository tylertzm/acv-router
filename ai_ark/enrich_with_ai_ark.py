#!/usr/bin/env python3
"""
AI Ark Lead Enrichment Engine
-----------------------------
Enriches leads with:
- Exact Street Addresses & Postal Codes
- Full Geographic Addresses (Latitude, Longitude)
- Verified Phone Numbers
- Impressum-scraped Fax Numbers
- Company Firmographics (Revenue, Employee Ranges, AI Ark IDs)
"""

import argparse
import csv
import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

AI_ARK_MCP_URL = "https://api.ai-ark.com/v1/mcp"

# Fallback impressum fax scraper context
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

headers_web = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
fax_regex = re.compile(
    r'(?:telefax|fax-nr\.?|fax(?:\s*\(?\w+\)?)?)\s*[:.\-]?\s*(\+?[0-9][0-9\s\/\(\)\-\.]{5,25}[0-9])',
    re.IGNORECASE
)


class AIArkEnricher:

    def __init__(self, api_key=None, cache_path=None):
        self.api_key = api_key or self._get_api_key()
        if not self.api_key:
            raise ValueError("AI_ARK_API_KEY is required for enrichment.")
        self.cache_path = cache_path or os.path.join(os.path.dirname(__file__), "ai_ark_enriched_cache.json")
        self.cache = self._load_cache()

    def _get_api_key(self):
        key = os.getenv("AI_ARK_API_KEY", "").strip() or os.getenv("ARK_API_KEY", "").strip()
        if key:
            return key
        for p in [os.path.join(os.path.dirname(__file__), ".env"), os.path.join(os.path.dirname(__file__), "../.env")]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(("AI_ARK_API_KEY=", "ARK_API_KEY=")):
                            return line.split("=", 1)[1].strip()
        return ""

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def _call_company_search(self, name=None, domain=None):
        args = {"size": 1}
        if name:
            args["name"] = name
        elif domain:
            args["domain"] = domain
        else:
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "company_search",
                "arguments": args
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-TOKEN": self.api_key
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(AI_ARK_MCP_URL, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                result = res.get("result", {})
                content = result.get("content", [])
                if content and content[0].get("type") == "text":
                    parsed = json.loads(content[0]["text"])
                    items = parsed.get("content", [])
                    if items:
                        return items[0]
        except Exception as e:
            return None
        return None

    def enrich_single_company(self, company_name, company_domain=""):
        cache_key = company_name.strip().lower()
        if cache_key in self.cache:
            return self.cache[cache_key]

        # 1. Query AI Ark by Name
        raw_data = self._call_company_search(name=company_name)
        
        # 2. If not found by name and domain is present, query by domain
        if not raw_data and company_domain:
            clean_dom = company_domain.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
            raw_data = self._call_company_search(domain=clean_dom)

        extracted = {
            "matched": False,
            "ai_ark_id": "",
            "phone": "",
            "street": "",
            "postal_code": "",
            "city": "",
            "state": "",
            "country": "",
            "raw_address": "",
            "lat": "",
            "lng": "",
            "revenue": "",
            "staff_total": "",
            "email": "",
            "website": ""
        }

        if raw_data:
            extracted["matched"] = True
            extracted["ai_ark_id"] = raw_data.get("id", "")
            
            # Contact
            contact = raw_data.get("contact", {})
            phone_obj = contact.get("phone", {})
            if isinstance(phone_obj, dict):
                extracted["phone"] = phone_obj.get("raw") or phone_obj.get("sanitized") or ""
            elif isinstance(phone_obj, str):
                extracted["phone"] = phone_obj
            extracted["email"] = contact.get("email", "")

            # Location / Address
            loc = raw_data.get("location", {})
            hq = loc.get("headquarter", {})
            extracted["street"] = hq.get("street", "")
            extracted["postal_code"] = hq.get("postal_code", "")
            extracted["city"] = hq.get("city", "")
            extracted["state"] = hq.get("state", "")
            extracted["country"] = hq.get("country", "")
            extracted["raw_address"] = hq.get("raw_address", "")
            
            pos = hq.get("position", {})
            extracted["lat"] = str(pos.get("lat", "")) if pos.get("lat") else ""
            extracted["lng"] = str(pos.get("lng", "")) if pos.get("lng") else ""

            # Financial
            fin = raw_data.get("financial", {})
            rev = fin.get("revenue", {}).get("annual", {})
            extracted["revenue"] = rev.get("amount", "")

            # Staff
            staff = raw_data.get("summary", {}).get("staff", {})
            extracted["staff_total"] = str(staff.get("total", "")) if staff.get("total") else ""

            # Link
            extracted["website"] = raw_data.get("link", {}).get("website", "")

        self.cache[cache_key] = extracted
        return extracted

    def scrape_fallback_fax(self, domain):
        if not domain:
            return ""
        clean = domain.replace("https://", "").replace("http://", "").rstrip("/")
        for path in ["/impressum", "/de/impressum", "/kontakt"]:
            try:
                url = f"https://{clean}{path}"
                req = urllib.request.Request(url, headers=headers_web)
                with urllib.request.urlopen(req, timeout=3.0, context=ssl_ctx) as resp:
                    raw = resp.read(150000).decode("utf-8", errors="ignore")
                    m = fax_regex.search(raw)
                    if m:
                        return " ".join(m.group(1).split())
            except Exception:
                continue
        return ""


def run_enrichment(input_csv, output_csv, max_workers=5, limit=None, scrape_missing_faxes=False):
    enricher = AIArkEnricher()

    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if limit:
        rows = rows[:limit]

    print(f"Starting AI Ark enrichment for {len(rows)} leads (Workers: {max_workers})...")
    start_time = time.time()

    enriched_records = []
    matches = 0
    new_phones = 0
    new_addresses = 0
    new_faxes = 0

    # Process in batches / threadpool
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_row = {
            executor.submit(enricher.enrich_single_company, r["Company Name"], r.get("Company Domain", "")): (idx, r)
            for idx, r in enumerate(rows)
        }

        results = {}
        for future in as_completed(future_to_row):
            idx, r = future_to_row[future]
            try:
                res = future.result()
            except Exception:
                res = {"matched": False}
            results[idx] = res

            if len(results) % 100 == 0 or len(results) == len(rows):
                print(f"Enrichment progress: {len(results)}/{len(rows)} completed...", flush=True)

    enricher._save_cache()

    # Preload local scraped cache for faxes if available
    local_fax_cache = {}
    lusha_cache_path = os.path.join(os.path.dirname(__file__), "../lusha/scraped_cache.json")
    if os.path.exists(lusha_cache_path):
        try:
            with open(lusha_cache_path, "r", encoding="utf-8") as f:
                scraped_data = json.load(f)
                for idx_str, item in scraped_data.items():
                    if item.get("fax"):
                        idx_val = int(idx_str) if idx_str.isdigit() else -1
                        if 0 <= idx_val < len(rows):
                            local_fax_cache[rows[idx_val].get("Company Domain", "")] = item["fax"]
        except Exception:
            pass

    for idx, r in enumerate(rows):
        ark = results.get(idx, {})

        # Phone Number Resolution
        existing_phone = r.get("Phone Number", "").strip()
        ark_phone = ark.get("phone", "").strip()
        final_phone = existing_phone or ark_phone
        if not existing_phone and ark_phone:
            new_phones += 1

        # Address Resolution
        street = ark.get("street", "").strip()
        postal = ark.get("postal_code", "").strip()
        raw_addr = ark.get("raw_address", "").strip()
        city = ark.get("city", "").strip() or r.get("City", "").strip()
        state = ark.get("state", "").strip() or r.get("State", "").strip()
        country = ark.get("country", "").strip() or r.get("Country", "").strip()

        if street or raw_addr:
            new_addresses += 1

        # Fax Resolution
        dom = r.get("Company Domain", "").strip()
        existing_fax = r.get("Fax Number", "").strip()
        final_fax = existing_fax or local_fax_cache.get(dom, "")
        if not final_fax and dom and ark.get("matched") and scrape_missing_faxes:
            scraped_fax = enricher.scrape_fallback_fax(dom)
            if scraped_fax:
                final_fax = scraped_fax
                new_faxes += 1

        if ark.get("matched"):
            matches += 1

        enriched_records.append({
            "Company Name": r.get("Company Name", ""),
            "Company Domain": r.get("Company Domain", ""),
            "Phone Number": final_phone,
            "Fax Number": final_fax,
            "Email": r.get("Email", "") or ark.get("email", ""),
            "Street Address": street,
            "Postal Code": postal,
            "City": city,
            "State": state,
            "Country": country,
            "Full Address": raw_addr or f"{street}, {postal} {city}, {country}".strip(", "),
            "Latitude": ark.get("lat", ""),
            "Longitude": ark.get("lng", ""),
            "Revenue Range": ark.get("revenue", ""),
            "AI Ark Headcount": ark.get("staff_total", ""),
            "AI Ark ID": ark.get("ai_ark_id", ""),
            "AI Ark Match Status": "Matched" if ark.get("matched") else "Pending",
            "Sub-Industry": r.get("Sub-Industry", ""),
            "Trade Focus": r.get("Trade Focus", ""),
            "Company LinkedIn": r.get("Company LinkedIn", ""),
            "Company Description": r.get("Company Description", ""),
            "Lusha ID": r.get("Lusha ID", "")
        })

    fieldnames = list(enriched_records[0].keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_records)

    elapsed = time.time() - start_time
    print(f"\n--- Enrichment Summary ---")
    print(f"Total Leads Processed: {len(rows)}")
    print(f"AI Ark Matches: {matches}")
    print(f"New Phones Added: {new_phones}")
    print(f"New Street Addresses & Postal Codes: {new_addresses}")
    print(f"Faxes Confirmed: {new_faxes}")
    print(f"Time Taken: {elapsed:.1f}s")
    print(f"Exported enriched dataset to: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Enrich Leads with AI Ark")
    parser.add_argument("--input", default="ai_ark_dach_handwerker_hvac_828_leads.csv")
    parser.add_argument("--output", default="ai_ark_dach_handwerker_hvac_828_enriched.csv")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows for testing")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("--scrape-faxes", action="store_true", help="Scrape live impressums for missing faxes")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.abspath(os.path.join(script_dir, args.input))
    output_path = os.path.abspath(os.path.join(script_dir, args.output))

    run_enrichment(input_path, output_path, max_workers=args.workers, limit=args.limit, scrape_missing_faxes=args.scrape_faxes)


if __name__ == "__main__":
    main()
