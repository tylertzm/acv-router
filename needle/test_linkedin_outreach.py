#!/usr/bin/env python3
"""Tests for the Needle LinkedIn automated outreach module."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

import linkedin_outreach


class TestNeedleLinkedInClient(unittest.TestCase):
    """Test Needle LinkedIn client functions."""

    def setUp(self):
        self.client = linkedin_outreach.NeedleLinkedInClient(
            api_key="sk-test-key",
            connected_account_id="01a191ff-038b-7790-974d-5a0da6f261ea",
            campaign_id="01a191f1-3778-7cb1-a608-4af5b68accb4",
        )

    def test_init_defaults(self):
        """Test default client properties."""
        self.assertEqual(self.client.connected_account_id, "01a191ff-038b-7790-974d-5a0da6f261ea")
        self.assertEqual(self.client.campaign_id, "01a191f1-3778-7cb1-a608-4af5b68accb4")

    @patch.object(linkedin_outreach.NeedleLinkedInClient, "call_mcp")
    def test_get_status(self, mock_call):
        """Test fetching connected account status."""
        mock_call.return_value = {
            "connectedAccounts": [
                {
                    "id": "01a191ff-038b-7790-974d-5a0da6f261ea",
                    "displayName": "Xavor Trennt",
                    "status": "active",
                }
            ]
        }
        res = self.client.get_status()
        self.assertEqual(len(res["connectedAccounts"]), 1)
        self.assertEqual(res["connectedAccounts"][0]["displayName"], "Xavor Trennt")
        mock_call.assert_called_once_with("needleListConnectedAccounts", {})

    @patch.object(linkedin_outreach.NeedleLinkedInClient, "call_mcp")
    def test_search_people(self, mock_call):
        """Test searching people on LinkedIn."""
        mock_call.return_value = {"hits": [{"headline": "GF SHK Berlin"}]}
        res = self.client.search_people("SHK Berlin", limit=3, company="Krone GmbH")
        mock_call.assert_called_once()
        args = mock_call.call_args[0][1]
        self.assertEqual(args["keywords"], "SHK Berlin")
        self.assertEqual(args["limit"], 3)
        self.assertEqual(args["advancedKeywords"]["company"], "Krone GmbH")

    @patch.object(linkedin_outreach.NeedleLinkedInClient, "call_mcp")
    def test_send_invitation(self, mock_call):
        """Test sending invitation."""
        mock_call.return_value = {"status": "sent"}
        res = self.client.send_invitation("philip-krone-266756106", note="Hallo Herr Krone")
        mock_call.assert_called_once_with(
            "needleSendLinkedinInvitation",
            {
                "connectedAccountId": "01a191ff-038b-7790-974d-5a0da6f261ea",
                "identity": "philip-krone-266756106",
                "note": "Hallo Herr Krone",
            },
        )

    @patch.object(linkedin_outreach.NeedleLinkedInClient, "call_mcp")
    def test_send_message(self, mock_call):
        """Test sending direct message."""
        mock_call.return_value = {"status": "delivered"}
        res = self.client.send_message("philip-krone-266756106", text="Guten Tag")
        mock_call.assert_called_once_with(
            "needleSendLinkedinMessage",
            {
                "connectedAccountId": "01a191ff-038b-7790-974d-5a0da6f261ea",
                "identity": "philip-krone-266756106",
                "text": "Guten Tag",
            },
        )

    @patch.object(linkedin_outreach.NeedleLinkedInClient, "call_mcp")
    def test_campaign_management(self, mock_call):
        """Test campaign pause and start calls."""
        mock_call.return_value = {"status": "updated"}
        self.client.set_campaign_status("active")
        mock_call.assert_called_with(
            "needleUpdateCampaign",
            {"campaignId": "01a191f1-3778-7cb1-a608-4af5b68accb4", "status": "active"},
        )

        self.client.set_campaign_status("paused")
        mock_call.assert_called_with(
            "needleUpdateCampaign",
            {"campaignId": "01a191f1-3778-7cb1-a608-4af5b68accb4", "status": "paused"},
        )


if __name__ == "__main__":
    unittest.main()
