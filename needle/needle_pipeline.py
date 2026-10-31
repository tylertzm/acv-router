#!/usr/bin/env python3
"""
Needle Lead Generation Pipeline
-------------------------------
Pipeline to manage lead generation, formatting, places enrichment,
and outreach integration with Needle (https://needle.app / https://needle.app/mcp/v1).
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error

# Default Timezone mapping for DACH countries
DACH_TIMEZONES = {
    "DE": "Europe/Berlin",
    "Germany": "Europe/Berlin",
    "Deutschland": "Europe/Berlin",
    "CH": "Europe/Zurich",
    "Switzerland": "Europe/Zurich",
    "Schweiz": "Europe/Zurich",
    "AT": "Europe/Vienna",
    "Austria": "Europe/Vienna",
    "Österreich": "Europe/Vienna",
    "LI": "Europe/Vaduz",
    "Liechtenstein": "Europe/Vaduz"
}

NEEDLE_API_BASE = "https://needle.app/api/v1"
NEEDLE_MCP_URL = "https://needle.app/mcp/v1"


class NeedleClient:
    """Client for Needle REST API and MCP integration."""

    def __init__(self, api_key=None):
        if not api_key:
            api_key = os.getenv("NEEDLE_API_KEY", "").strip()
        if not api_key:
            # Check for .env file in script dir or parent
            for p in [os.path.join(os.path.dirname(__file__), ".env"), os.path.join(os.path.dirname(__file__), "../.env")]:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("NEEDLE_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break
                if api_key:
                    break
        self.api_key = api_key

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NeedleLeadGenPipeline/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def test_connection(self):
        """Verify API key validity against Needle."""
        if not self.api_key:
            return {"authenticated": False, "message": "No NEEDLE_API_KEY provided."}
        try:
            req = urllib.request.Request(f"{NEEDLE_API_BASE}/me", headers=self._headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"authenticated": True, "data": data}
        except urllib.error.HTTPError as e:
            return {"authenticated": False, "status_code": e.code, "error": e.read().decode("utf-8")}
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    def search_places(self, query, region="DE", language="de"):
        """Search local businesses via Needle Places API."""
        if not self.api_key:
            raise ValueError("NEEDLE_API_KEY is required to query Needle Places API.")
        url = f"{NEEDLE_API_BASE}/places/search"
        payload = {
            "query": query,
            "region": region,
            "language": language
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def create_leads_bulk(self, leads_batch):
        """Create up to 500 leads in Needle using bulk endpoint."""
        if not self.api_key:
            raise ValueError("NEEDLE_API_KEY is required to upload leads.")
        if len(leads_batch) > 500:
            raise ValueError("Needle bulk lead creation supports up to 500 leads per batch.")
        url = f"{NEEDLE_API_BASE}/leads/bulk"
        payload = {"leads": leads_batch}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def create_campaign(self, name, channel="linkedin"):
        """Create a new outreach campaign in Needle."""
        if not self.api_key:
            raise ValueError("NEEDLE_API_KEY is required to create campaigns.")
        url = f"{NEEDLE_API_BASE}/campaigns"
        payload = {"name": name, "channel": channel}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def enroll_leads(self, campaign_id, lead_ids):
        """Enroll lead IDs into a campaign."""
        if not self.api_key:
            raise ValueError("NEEDLE_API_KEY is required to enroll leads.")
        url = f"{NEEDLE_API_BASE}/campaigns/{campaign_id}/enroll"
        payload = {"leadIds": lead_ids}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))


def format_lead_for_needle(row):
    """
    Format a single lead record into Needle's schema.
    """
    country = row.get("Country", "")
    country_code = row.get("Country Code", "")
    tz = DACH_TIMEZONES.get(country_code, DACH_TIMEZONES.get(country, "Europe/Berlin"))

    # Extract LinkedIn identifier or URL
    linkedin = row.get("Company LinkedIn", row.get("LinkedIn", "")).strip()

    lead_obj = {
        "identities": {},
        "companyName": row.get("Company Name", "").strip(),
        "companyDomain": row.get("Company Domain", row.get("Domain", "")).strip(),
        "firstName": row.get("First Name", "").strip(),
        "lastName": row.get("Last Name", "").strip(),
        "jobTitle": row.get("Job Title", "Geschäftsführer / Inhaber").strip(),
        "email": row.get("Email", "").strip(),
        "timezone": tz,
        "properties": {
            "phone": row.get("Phone Number", row.get("Phone", "")).strip(),
            "fax": row.get("Fax Number", row.get("Fax", "")).strip(),
            "city": row.get("City", "").strip(),
            "state": row.get("State", "").strip(),
            "country": country.strip(),
            "country_code": country_code.strip(),
            "location": row.get("Location", "").strip(),
            "employee_count": str(row.get("Employee Headcount", "")).strip(),
            "sub_industry": row.get("Sub-Industry", "").strip(),
            "trade_focus": row.get("Trade Focus", "").strip(),
            "description": row.get("Company Description", row.get("Description", "")).strip(),
            "lusha_id": row.get("Lusha ID", "").strip()
        }
    }

    if linkedin:
        lead_obj["identities"]["linkedin"] = linkedin

    return lead_obj


def convert_csv_to_needle(input_csv_path, output_csv_path, output_json_path=None):
    """
    Read an input leads CSV and produce a Needle-ready CSV and JSON batch file.
    """
    if not os.path.exists(input_csv_path):
        raise FileNotFoundError(f"Input file not found: {input_csv_path}")

    with open(input_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Reading {len(rows)} leads from {input_csv_path}...")

    formatted_leads = []
    needle_csv_rows = []

    for r in rows:
        lead = format_lead_for_needle(r)
        formatted_leads.append(lead)

        needle_csv_rows.append({
            "Company Name": lead["companyName"],
            "Company Domain": lead["companyDomain"],
            "First Name": lead["firstName"],
            "Last Name": lead["lastName"],
            "Job Title": lead["jobTitle"],
            "Email": lead["email"],
            "Phone": lead["properties"]["phone"],
            "Fax": lead["properties"]["fax"],
            "LinkedIn": lead["identities"].get("linkedin", ""),
            "Timezone": lead["timezone"],
            "City": lead["properties"]["city"],
            "State": lead["properties"]["state"],
            "Country": lead["properties"]["country"],
            "Country Code": lead["properties"]["country_code"],
            "Location": lead["properties"]["location"],
            "Employee Headcount": lead["properties"]["employee_count"],
            "Sub-Industry": lead["properties"]["sub_industry"],
            "Trade Focus": lead["properties"]["trade_focus"],
            "Description": lead["properties"]["description"],
            "Lusha ID": lead["properties"]["lusha_id"]
        })

    fieldnames = [
        "Company Name",
        "Company Domain",
        "First Name",
        "Last Name",
        "Job Title",
        "Email",
        "Phone",
        "Fax",
        "LinkedIn",
        "Timezone",
        "City",
        "State",
        "Country",
        "Country Code",
        "Location",
        "Employee Headcount",
        "Sub-Industry",
        "Trade Focus",
        "Description",
        "Lusha ID"
    ]

    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(needle_csv_rows)

    print(f"Exported {len(needle_csv_rows)} Needle CSV leads to: {output_csv_path}")

    if output_json_path:
        with open(output_json_path, mode="w", encoding="utf-8") as f:
            json.dump({"leads": formatted_leads}, f, indent=2, ensure_ascii=False)
        print(f"Exported Needle JSON payload to: {output_json_path}")

    return formatted_leads


def main():
    parser = argparse.ArgumentParser(description="Needle Lead Gen Pipeline CLI")
    parser.add_argument("--mode", choices=["convert", "test", "upload", "places"], default="convert")
    parser.add_argument("--input", default="../lusha/lusha_dach_handwerker_hvac_828_leads.csv")
    parser.add_argument("--output-csv", default="needle_dach_handwerker_hvac_828_leads.csv")
    parser.add_argument("--output-json", default="needle_leads_batch.json")
    parser.add_argument("--places-query", default="Heizungsbau Berlin")
    args = parser.parse_args()

    # Resolve relative paths relative to script directory if needed
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.abspath(os.path.join(script_dir, args.input))
    output_csv = os.path.abspath(os.path.join(script_dir, args.output_csv))
    output_json = os.path.abspath(os.path.join(script_dir, args.output_json))

    client = NeedleClient()

    if args.mode == "convert":
        convert_csv_to_needle(input_path, output_csv, output_json)

    elif args.mode == "test":
        status = client.test_connection()
        print("Needle Connection Status:", json.dumps(status, indent=2))

    elif args.mode == "places":
        print(f"Searching Needle Places for: '{args.places_query}'...")
        try:
            results = client.search_places(args.places_query)
            print(f"Found {len(results.get('places', []))} places.")
            print(json.dumps(results, indent=2))
        except Exception as e:
            print("Places search failed:", e)

    elif args.mode == "upload":
        if not os.path.exists(output_json):
            convert_csv_to_needle(input_path, output_csv, output_json)
        with open(output_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        leads = data.get("leads", [])
        print(f"Uploading {len(leads)} leads to Needle in batches of 500...")
        batch_size = 500
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            print(f"Uploading batch {i // batch_size + 1} ({len(batch)} leads)...")
            res = client.create_leads_bulk(batch)
            print("Batch response:", res)


if __name__ == "__main__":
    main()
