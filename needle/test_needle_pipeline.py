#!/usr/bin/env python3
"""
Unit and Integration Tests for Needle Lead Gen Pipeline.
"""

import json
import os
import unittest
from needle_pipeline import format_lead_for_needle, DACH_TIMEZONES, NeedleClient

class TestNeedlePipeline(unittest.TestCase):

    def test_lead_formatting(self):
        sample_lead = {
            "Company Name": "Meier Tobler AG",
            "Company Domain": "www.meiertobler.ch",
            "Phone Number": "0448064141",
            "Fax Number": "0448064142",
            "Email": "info@meiertobler.ch",
            "Company Description": "Einfach Haustechnik",
            "Country": "Switzerland",
            "Country Code": "CH",
            "City": "Schwerzenbach",
            "Location": "Schwerzenbach, Switzerland",
            "Employee Headcount": "878",
            "Sub-Industry": "Specialty Trade Contractors",
            "Trade Focus": "HVAC",
            "Company LinkedIn": "https://www.linkedin.com/company/meier-tobler-ag",
            "Lusha ID": "v1.test123"
        }

        formatted = format_lead_for_needle(sample_lead)

        self.assertEqual(formatted["companyName"], "Meier Tobler AG")
        self.assertEqual(formatted["companyDomain"], "www.meiertobler.ch")
        self.assertEqual(formatted["timezone"], "Europe/Zurich")
        self.assertEqual(formatted["identities"]["linkedin"], "https://www.linkedin.com/company/meier-tobler-ag")
        self.assertEqual(formatted["properties"]["phone"], "0448064141")
        self.assertEqual(formatted["properties"]["fax"], "0448064142")
        self.assertEqual(formatted["properties"]["country_code"], "CH")
        self.assertEqual(formatted["properties"]["lusha_id"], "v1.test123")

    def test_batch_json_structure(self):
        json_path = os.path.join(os.path.dirname(__file__), "needle_leads_batch.json")
        self.assertTrue(os.path.exists(json_path), "Batch JSON file must exist")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("leads", data)
        self.assertEqual(len(data["leads"]), 828)
        first_lead = data["leads"][0]
        self.assertIn("companyName", first_lead)
        self.assertIn("identities", first_lead)
        self.assertIn("properties", first_lead)
        self.assertIn("timezone", first_lead)

    def test_client_init(self):
        client = NeedleClient(api_key="test_key")
        self.assertEqual(client.api_key, "test_key")
        self.assertIn("Authorization", client._headers())
        self.assertEqual(client._headers()["Authorization"], "Bearer test_key")

if __name__ == "__main__":
    unittest.main()
