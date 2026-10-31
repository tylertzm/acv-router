#!/usr/bin/env python3
"""
Needle LinkedIn Automated Outreach Module
=========================================

Automates LinkedIn lead discovery, personalized outreach, connection requests,
and multi-step campaign execution using Needle's MCP tools & REST API.

Connected Account:
  Account ID: 01a191ff-038b-7790-974d-5a0da6f261ea (Xavor Trennt)

Default Campaign:
  Campaign ID: 01a191f1-3778-7cb1-a608-4af5b68accb4
  Name: Meisterpfad SHK sales outreach Berlin & Brandenburg
  Multi-step Graph: Connection check -> Invite -> AI 1st Message -> Nudge

Commands:
  python linkedin_outreach.py status
  python linkedin_outreach.py search --keywords "Geschäftsführer SHK Berlin" --limit 5
  python linkedin_outreach.py preview --identity "philip-krone-266756106"
  python linkedin_outreach.py invite --identity "<identity>" --note "Guten Tag Herr..."
  python linkedin_outreach.py message --identity "<identity>" --text "Guten Tag..."
  python linkedin_outreach.py campaign-stats
  python linkedin_outreach.py campaign-leads
  python linkedin_outreach.py campaign-start
  python linkedin_outreach.py campaign-pause
  python linkedin_outreach.py enroll --lead-id "<leadId>"
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Load environment
ROOT_DIR = Path(__file__).resolve().parent.parent
NEEDLE_API_KEY = os.getenv("NEEDLE_API_KEY", "")
if not NEEDLE_API_KEY:
    for env_candidate in [ROOT_DIR / ".env", Path(__file__).parent / ".env"]:
        if env_candidate.exists():
            for line in env_candidate.read_text(encoding="utf-8").splitlines():
                if line.startswith("NEEDLE_API_KEY="):
                    NEEDLE_API_KEY = line.split("=", 1)[1].strip()
                    break
        if NEEDLE_API_KEY:
            break

NEEDLE_MCP_URL = "https://needle.app/mcp/v1"
DEFAULT_CONNECTED_ACCOUNT_ID = "01a19241-3eac-7160-adf4-e97821c29170"
DEFAULT_CAMPAIGN_ID = "01a191f1-3778-7cb1-a608-4af5b68accb4"

LOG_DIR = Path(__file__).parent / "linkedin_logs"
LOG_DIR.mkdir(exist_ok=True)


class NeedleLinkedInClient:
    """Client for Needle LinkedIn MCP integration."""

    def __init__(self, api_key=None, connected_account_id=None, campaign_id=None):
        self.api_key = api_key or NEEDLE_API_KEY
        self.connected_account_id = connected_account_id or DEFAULT_CONNECTED_ACCOUNT_ID
        self.campaign_id = campaign_id or DEFAULT_CAMPAIGN_ID

    def call_mcp(self, tool_name: str, arguments: dict) -> dict:
        """Call a Needle MCP tool via JSON-RPC / SSE endpoint."""
        if not self.api_key:
            raise ValueError("NEEDLE_API_KEY is not set. Check needle/.env")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        req = urllib.request.Request(
            NEEDLE_MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                for line in body.splitlines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if "error" in data:
                            return {"error": data["error"]}
                        result_obj = data.get("result", {})
                        content_list = result_obj.get("content", [])
                        if content_list and content_list[0].get("type") == "text":
                            try:
                                return json.loads(content_list[0]["text"])
                            except json.JSONDecodeError:
                                return {"raw": content_list[0]["text"]}
                        return result_obj
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return {"error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            return {"error": str(e)}

        return {}

    # ─────────────────────────────────────────────────────────────
    # Status & Connected Accounts
    # ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Fetch connected accounts and default account details."""
        accs = self.call_mcp("needleListConnectedAccounts", {})
        return accs

    # ─────────────────────────────────────────────────────────────
    # LinkedIn Search & Discovery
    # ─────────────────────────────────────────────────────────────

    def search_people(self, keywords: str, limit: int = 5, company: str = None, title: str = None) -> dict:
        """Search people on LinkedIn Classic."""
        args = {
            "connectedAccountId": self.connected_account_id,
            "keywords": keywords,
            "limit": min(limit, 10),
        }
        adv = {}
        if company:
            adv["company"] = company
        if title:
            adv["title"] = title
        if adv:
            args["advancedKeywords"] = adv

        return self.call_mcp("needleSearchLinkedinPeopleClassic", args)

    # ─────────────────────────────────────────────────────────────
    # AI Message Generation & Preview
    # ─────────────────────────────────────────────────────────────

    def compose_preview(self, identity: str, prompt: str = None) -> dict:
        """Preview an AI-composed personalized LinkedIn outreach message."""
        default_prompt = (
            "Write a short, highly personalized first LinkedIn outreach message in German (formal 'Sie') "
            "from Meisterpfad / ACV Router. Meisterpfad helps HVAC/SHK Meisterbetriebe automate their back-office, "
            "quote drafting, and technician scheduling so they get their evenings back. "
            "Keep it under 300 characters, no hype, no links, end with one question."
        )
        args = {
            "channel": "linkedin",
            "connectedAccountId": self.connected_account_id,
            "identity": identity,
            "context": ["profile"],
            "prompt": prompt or default_prompt,
        }
        return self.call_mcp("needleComposePreview", args)

    # ─────────────────────────────────────────────────────────────
    # Direct Outreach (Invitations & Messages)
    # ─────────────────────────────────────────────────────────────

    def send_invitation(self, identity: str, note: str = "") -> dict:
        """Send a LinkedIn connection request with an optional note."""
        args = {
            "connectedAccountId": self.connected_account_id,
            "identity": identity,
        }
        if note:
            args["note"] = note[:300]
        return self.call_mcp("needleSendLinkedinInvitation", args)

    def send_message(self, identity: str, text: str) -> dict:
        """Send a direct LinkedIn message to a connection."""
        args = {
            "connectedAccountId": self.connected_account_id,
            "identity": identity,
            "text": text,
        }
        return self.call_mcp("needleSendLinkedinMessage", args)

    # ─────────────────────────────────────────────────────────────
    # Automated Campaign Management
    # ─────────────────────────────────────────────────────────────

    def get_campaign_stats(self, campaign_id: str = None) -> dict:
        """Get funnel and node metrics for an outreach campaign."""
        cid = campaign_id or self.campaign_id
        return self.call_mcp("needleGetCampaignStats", {"campaignId": cid})

    def list_campaign_leads(self, campaign_id: str = None) -> dict:
        """List all leads enrolled in the campaign."""
        cid = campaign_id or self.campaign_id
        return self.call_mcp("needleListCampaignLeads", {"campaignId": cid})

    def set_campaign_status(self, status: str, campaign_id: str = None) -> dict:
        """Activate ('active') or pause ('paused') an automated campaign."""
        cid = campaign_id or self.campaign_id
        return self.call_mcp("needleUpdateCampaign", {"campaignId": cid, "status": status})

    def enroll_leads(self, lead_ids: list, campaign_id: str = None) -> dict:
        """Enroll lead IDs into the automated multi-step campaign."""
        cid = campaign_id or self.campaign_id
        return self.call_mcp("needleEnrollCampaignLeads", {"campaignId": cid, "leadIds": lead_ids})


# ─────────────────────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────────────────────


def cmd_status(client, args):
    print("🔍 Fetching Needle LinkedIn Connected Account Status...")
    res = client.get_status()
    accs = res.get("connectedAccounts", [])
    if not accs:
        print("  No connected accounts found.")
        return

    for acc in accs:
        print(f"  • Name:     {acc.get('displayName')}")
        print(f"    Channel:  {acc.get('channel')}")
        print(f"    Identity: {acc.get('channelIdentity')}")
        print(f"    Status:   {acc.get('status')} (canUse: {acc.get('canUse')})")
        print(f"    ID:       {acc.get('id')}")
        print()


def cmd_search(client, args):
    print(f"🔎 Searching LinkedIn for: '{args.keywords}'...")
    res = client.search_people(args.keywords, limit=args.limit, company=args.company, title=args.title)
    hits = res.get("hits", [])
    print(f"  Found {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {h.get('headline')}")
        print(f"      Location: {h.get('location')}")
        print(f"      Profile:  {h.get('profileUrl')}")
        print(f"      Degree:   {h.get('degree')}")
        print()


def cmd_preview(client, args):
    print(f"🤖 Generating AI message preview for: {args.identity}...")
    res = client.compose_preview(args.identity, prompt=args.prompt)
    if "error" in res:
        print(f"  ❌ Error: {res['error']}")
        return
    text = res.get("text", "")
    print(f"\n  📝 AI-Generated Message ({len(text)} chars):\n")
    print(f"  \"{text}\"\n")


def cmd_invite(client, args):
    print(f"🤝 Sending LinkedIn Invitation to: {args.identity}...")
    if args.note:
        print(f"   Note: \"{args.note}\"")
    res = client.send_invitation(args.identity, note=args.note or "")
    print("  Response:", json.dumps(res, indent=2))


def cmd_message(client, args):
    print(f"💬 Sending LinkedIn Message to: {args.identity}...")
    res = client.send_message(args.identity, text=args.text)
    print("  Response:", json.dumps(res, indent=2))


def cmd_campaign_stats(client, args):
    print(f"📊 Fetching Campaign Stats for: {client.campaign_id}...")
    res = client.get_campaign_stats()
    stats = res.get("stats", {})
    funnel = stats.get("funnel", {})
    enrollments = stats.get("enrollments", {})

    print(f"  Progress:        {stats.get('progress')}%")
    print(f"  Enrolled Total:  {funnel.get('enrolled', 0)}")
    print(f"  Active:          {enrollments.get('active', 0)}")
    print(f"  Invites Sent:    {funnel.get('invitesSent', 0)}")
    print(f"  Invites Accepted:{funnel.get('invitesAccepted', 0)}")
    print(f"  Messages Sent:   {funnel.get('messagesSent', 0)}")
    print(f"  Replies:         {funnel.get('repliedLeads', 0)}")
    print()


def cmd_campaign_leads(client, args):
    print(f"👥 Fetching Leads in Campaign: {client.campaign_id}...")
    res = client.list_campaign_leads()
    leads = res.get("leads", [])
    print(f"  Total leads: {len(leads)}\n")
    for l in leads:
        name = f"{l.get('firstName', '')} {l.get('lastName', '')}".strip() or "Unnamed"
        comp = l.get("companyName", "N/A")
        step = l.get("currentNodeId", "start")
        print(f"  • {name:25s} | {comp:35s} | Step: {step:15s} | Status: {l.get('status')}")


def cmd_campaign_start(client, args):
    print(f"🚀 Activating Automated Outreach Campaign: {client.campaign_id}...")
    res = client.set_campaign_status("active")
    print("  Response:", json.dumps(res, indent=2))


def cmd_campaign_pause(client, args):
    print(f"⏸️  Pausing Automated Outreach Campaign: {client.campaign_id}...")
    res = client.set_campaign_status("paused")
    print("  Response:", json.dumps(res, indent=2))


def cmd_enroll(client, args):
    print(f"📥 Enrolling lead {args.lead_id} into campaign: {client.campaign_id}...")
    res = client.enroll_leads([args.lead_id])
    print("  Response:", json.dumps(res, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Needle LinkedIn Automated Outreach CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Outreach commands")

    sub.add_parser("status", help="Check LinkedIn connected account status")

    p_search = sub.add_parser("search", help="Search LinkedIn profiles")
    p_search.add_argument("--keywords", default="Geschäftsführer SHK Berlin", help="Search keywords")
    p_search.add_argument("--company", default=None, help="Filter by company name")
    p_search.add_argument("--title", default=None, help="Filter by job title")
    p_search.add_argument("--limit", type=int, default=5, help="Max results (max 10)")

    p_prev = sub.add_parser("preview", help="Preview AI-personalized German outreach message")
    p_prev.add_argument("--identity", required=True, help="LinkedIn profile identifier or slug")
    p_prev.add_argument("--prompt", default=None, help="Custom prompt override")

    p_inv = sub.add_parser("invite", help="Send connection request with optional note")
    p_inv.add_argument("--identity", required=True, help="LinkedIn profile identifier")
    p_inv.add_argument("--note", default="", help="Note up to 300 chars")

    p_msg = sub.add_parser("message", help="Send direct LinkedIn message")
    p_msg.add_argument("--identity", required=True, help="LinkedIn profile identifier")
    p_msg.add_argument("--text", required=True, help="Message text")

    sub.add_parser("campaign-stats", help="View live funnel and stats of automated campaign")
    sub.add_parser("campaign-leads", help="List all leads currently in the campaign")
    sub.add_parser("campaign-start", help="Start/activate the automated campaign")
    sub.add_parser("campaign-pause", help="Pause the automated campaign")

    p_enr = sub.add_parser("enroll", help="Enroll a lead into the campaign")
    p_enr.add_argument("--lead-id", required=True, help="Needle Lead ID")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    client = NeedleLinkedInClient()
    commands = {
        "status": cmd_status,
        "search": cmd_search,
        "preview": cmd_preview,
        "invite": cmd_invite,
        "message": cmd_message,
        "campaign-stats": cmd_campaign_stats,
        "campaign-leads": cmd_campaign_leads,
        "campaign-start": cmd_campaign_start,
        "campaign-pause": cmd_campaign_pause,
        "enroll": cmd_enroll,
    }

    commands[args.command](client, args)


if __name__ == "__main__":
    main()
