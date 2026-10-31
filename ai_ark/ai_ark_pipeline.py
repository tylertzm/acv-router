#!/usr/bin/env python3
"""
AI Ark Lead Generation Pipeline
-------------------------------
Pipeline to manage lead generation, contact enrichment, and company discovery
using AI Ark (https://ai-ark.com / https://api.ai-ark.com/v1/mcp).
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error

AI_ARK_MCP_URL = "https://api.ai-ark.com/v1/mcp"
AI_ARK_REST_URL = "https://api.ai-ark.com/v1"


class AIArkClient:
    """Client for AI Ark MCP and REST API integration."""

    def __init__(self, api_key=None):
        self.api_key = api_key or self._discover_api_key()

    def _discover_api_key(self):
        """Find API key from environment or local .env files."""
        key = os.getenv("AI_ARK_API_KEY", "").strip() or os.getenv("ARK_API_KEY", "").strip()
        if key:
            return key
        # Check .env in current directory or parent
        for p in [os.path.join(os.path.dirname(__file__), ".env"), os.path.join(os.path.dirname(__file__), "../.env")]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(("AI_ARK_API_KEY=", "ARK_API_KEY=")):
                            return line.split("=", 1)[1].strip()
        return ""

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.api_key:
            headers["X-TOKEN"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def call_mcp_tool(self, tool_name, arguments=None):
        """Call an MCP tool on the AI Ark MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        url = AI_ARK_MCP_URL
        if self.api_key and "?" not in url:
            url = f"{url}?token={self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers())
        with urllib.request.urlopen(req, timeout=20) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            if "error" in res_json:
                return {"error": res_json["error"]}
            
            result = res_json.get("result", {})
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                try:
                    return json.loads(content[0]["text"])
                except Exception:
                    return {"raw": content[0]["text"]}
            return result

    def lookup_industry(self, query="hvac,construction"):
        """Search valid industry enums from AI Ark catalog."""
        return self.call_mcp_tool("industry_search", {"query": query})

    def lookup_location(self, query="Germany,Switzerland,Austria"):
        """Search valid location tokens in AI Ark catalog."""
        return self.call_mcp_tool("location_search", {"query": query})

    def search_companies(self, industry=None, location=None, keyword=None, size=25, page=0):
        """Search companies in AI Ark."""
        args = {"size": size, "page": page}
        if industry:
            args["industry"] = industry
        if location:
            args["location"] = location
        if keyword:
            args["keyword"] = keyword
        return self.call_mcp_tool("company_search", args)

    def search_people(self, title=None, company_domain=None, location=None, size=25, page=0):
        """Search people / decision-makers in AI Ark."""
        args = {"size": size, "page": page}
        if title:
            args["title"] = title
        if company_domain:
            args["companyDomain"] = company_domain
        if location:
            args["location"] = location
        return self.call_mcp_tool("people_search", args)

    def export_single_person(self, person_id=None, linkedin_url=None):
        """Export single person with real-time email verification."""
        args = {}
        if person_id:
            args["id"] = person_id
        if linkedin_url:
            args["url"] = linkedin_url
        return self.call_mcp_tool("export_single", args)


def format_lead_for_ai_ark(row):
    """Format lead for AI Ark pipeline."""
    return {
        "Company Name": row.get("Company Name", "").strip(),
        "Company Domain": row.get("Company Domain", row.get("Domain", "")).strip(),
        "Industry": "heating, ventilation, and air conditioning (hvac)",
        "Sub-Industry": row.get("Sub-Industry", "").strip(),
        "Trade Focus": row.get("Trade Focus", "").strip(),
        "Country": row.get("Country", "").strip(),
        "Country Code": row.get("Country Code", "").strip(),
        "State": row.get("State", "").strip(),
        "City": row.get("City", "").strip(),
        "Location": row.get("Location", "").strip(),
        "Phone Number": row.get("Phone Number", row.get("Phone", "")).strip(),
        "Fax Number": row.get("Fax Number", row.get("Fax", "")).strip(),
        "Email": row.get("Email", "").strip(),
        "Company LinkedIn": row.get("Company LinkedIn", row.get("LinkedIn", "")).strip(),
        "Employee Headcount": str(row.get("Employee Headcount", "")).strip(),
        "Company Description": row.get("Company Description", row.get("Description", "")).strip(),
        "Lusha ID": row.get("Lusha ID", "").strip(),
        "Target Persona": "Geschäftsführer / Inhaber / Head of Operations"
    }


def convert_csv_to_ai_ark(input_csv_path, output_csv_path):
    """Convert input leads CSV into AI Ark format."""
    if not os.path.exists(input_csv_path):
        raise FileNotFoundError(f"File not found: {input_csv_path}")

    with open(input_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Reading {len(rows)} leads from {input_csv_path}...")
    ark_leads = [format_lead_for_ai_ark(r) for r in rows]

    fieldnames = list(ark_leads[0].keys())
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ark_leads)

    print(f"Exported {len(ark_leads)} AI Ark CSV leads to: {output_csv_path}")
    return ark_leads


def main():
    parser = argparse.ArgumentParser(description="AI Ark Lead Gen Pipeline CLI")
    parser.add_argument("--mode", choices=["convert", "enrich", "test", "lookup-industry", "lookup-location", "search-company", "search-people"], default="convert")
    parser.add_argument("--input", default="ai_ark_dach_handwerker_hvac_828_leads.csv")
    parser.add_argument("--output-csv", default="ai_ark_dach_handwerker_hvac_828_enriched.csv")
    parser.add_argument("--query", default="hvac,construction")
    parser.add_argument("--location", default="Germany")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.abspath(os.path.join(script_dir, args.input))
    output_csv = os.path.abspath(os.path.join(script_dir, args.output_csv))

    client = AIArkClient()

    if args.mode == "convert":
        convert_csv_to_ai_ark(input_path, output_csv)

    elif args.mode == "enrich":
        from enrich_with_ai_ark import run_enrichment
        run_enrichment(input_path, output_csv, max_workers=args.workers, limit=args.limit)

    elif args.mode == "lookup-industry":
        res = client.lookup_industry(args.query)
        print("AI Ark Industry Lookup:", json.dumps(res, indent=2))

    elif args.mode == "lookup-location":
        res = client.lookup_location(args.location)
        print("AI Ark Location Lookup:", json.dumps(res, indent=2))

    elif args.mode == "test":
        print(f"Checking AI Ark API Key: {'Present' if client.api_key else 'Missing (set AI_ARK_API_KEY in .env)'}")
        print("Testing Industry Search tool...")
        res = client.lookup_industry("heating")
        print("Result:", json.dumps(res, indent=2))

    elif args.mode == "search-company":
        res = client.search_companies(industry="heating, ventilation, and air conditioning (hvac)", location=args.location, size=5)
        print("Company Search Result:", json.dumps(res, indent=2))

    elif args.mode == "search-people":
        res = client.search_people(title="Geschäftsführer", location=args.location, size=5)
        print("People Search Result:", json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
