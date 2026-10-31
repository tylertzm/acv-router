#!/usr/bin/env python3
"""
Unit tests for AI Ark Lead Gen Pipeline.
"""

import os
import unittest
from ai_ark_pipeline import format_lead_for_ai_ark, AIArkClient

class TestAIArkPipeline(unittest.TestCase):

    def test_lead_formatting(self):
        sample = {
            "Company Name": "Meier Tobler AG",
            "Company Domain": "www.meiertobler.ch",
            "Phone Number": "0448064141",
            "Fax Number": "0448064142",
            "Email": "info@meiertobler.ch",
            "Company Description": "Haustechnik",
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
        res = format_lead_for_ai_ark(sample)
        self.assertEqual(res["Company Name"], "Meier Tobler AG")
        self.assertEqual(res["Industry"], "heating, ventilation, and air conditioning (hvac)")
        self.assertEqual(res["Country"], "Switzerland")
        self.assertEqual(res["Target Persona"], "Geschäftsführer / Inhaber / Head of Operations")

    def test_client_headers(self):
        client = AIArkClient(api_key="ark_test_123")
        self.assertEqual(client.api_key, "ark_test_123")
        headers = client._headers()
        self.assertEqual(headers["X-TOKEN"], "ark_test_123")
        self.assertEqual(headers["Authorization"], "Bearer ark_test_123")

    def test_csv_file_exists(self):
        csv_path = os.path.join(os.path.dirname(__file__), "ai_ark_dach_handwerker_hvac_828_leads.csv")
        self.assertTrue(os.path.exists(csv_path), "AI Ark CSV file must exist")

if __name__ == "__main__":
    unittest.main()
