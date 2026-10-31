#!/usr/bin/env python3
"""
ElevenLabs Cold Call Pipeline for HVAC/SHK Lead Generation
==========================================================

Creates a Conversational AI agent with an attractive female voice (Sarah)
and triggers outbound calls to enriched leads from AI Ark.

Flow:
  1. create-agent   → Creates the German HVAC sales agent on ElevenLabs
  2. list-agents    → Lists existing agents
  3. list-phones    → Lists imported phone numbers
  4. import-phone   → Imports a Twilio phone number for outbound calling
  5. call           → Triggers an outbound call to a single lead
  6. batch-call     → Batch call top N leads (with phone numbers)
  7. list-calls     → Lists recent conversation history
  8. get-call       → Gets details/transcript of a specific call

Usage:
  python cold_call.py create-agent
  python cold_call.py call --to "+4930123456" --company "Krone GmbH" --contact "Herr Müller"
  python cold_call.py batch-call --csv ../ai_ark/ai_ark_dach_handwerker_hvac_828_enriched.csv --limit 5
  python cold_call.py list-calls
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from root or local directory
ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
LOCAL_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(ROOT_ENV if ROOT_ENV.exists() else LOCAL_ENV)

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Sarah
BASE_URL = "https://api.elevenlabs.io/v1"

HEADERS = {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json",
}

# Cache directory for call logs
CACHE_DIR = Path(__file__).parent / "call_logs"
CACHE_DIR.mkdir(exist_ok=True)

# Agent config file
AGENT_CONFIG_FILE = Path(__file__).parent / "agent_config.json"


# ─────────────────────────────────────────────────────────────
# English HVAC Sales Agent Prompt (Meisterpfad)
# ─────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are Lisa Weber, an energetic, warm, and highly professional sales development representative calling on behalf of Meisterpfad (https://www.meisterpfad.de/). Meisterpfad is the leading modern, AI-native back-office software built specifically for HVAC, plumbing, heating, and mechanical trade companies (SHK-Betriebe) in the DACH region.

## Objective
Your goal is to connect with the managing director or operations lead ({{contact_name}} at {{company_name}} in {{city}}), introduce how Meisterpfad saves HVAC contractors 10+ hours a week by automating job calculations, technician dispatch, tender document parsing (Leistungsverzeichnisse), and back-office invoicing, and schedule a brief 15-minute live demo.

## Conversation Flow
1. Greet the contact warmly in clear, natural English.
2. Confirm you are speaking with {{contact_name}} from {{company_name}} in {{city}}.
3. Pitch the value proposition: Meisterpfad was built specifically for HVAC teams with {{technician_count}} technicians to eliminate late-night quotation work and dispatch chaos through AI automation.
4. Ask a quick qualifying question: "How is your team currently handling tender calculations and technician scheduling?"
5. Listen actively and propose a quick 15-minute screen-share demo next Tuesday or Thursday.
6. If agreed, ask for their preferred email address to send the calendar invite.
7. If not interested or busy, thank them politely and ask if you can send a one-page summary by email.

## Persona & Tone
- Confident, polite, articulate, friendly, and natural.
- Never sound robotic or pushy.
- Keep responses concise (1 to 2 sentences per turn) so it feels like a real conversation.
- If they ask about pricing, mention that Meisterpfad starts at flexible plans based on technician count and typically pays for itself in the first month.
"""


def _save_agent_config(agent_id: str, voice_id: str):
    """Save agent config to file for reuse."""
    config = {
        "agent_id": agent_id,
        "voice_id": voice_id,
        "created_at": datetime.now().isoformat(),
    }
    AGENT_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"  ✓ Agent config saved to {AGENT_CONFIG_FILE}")


def _load_agent_config() -> dict:
    """Load saved agent config."""
    if AGENT_CONFIG_FILE.exists():
        return json.loads(AGENT_CONFIG_FILE.read_text())
    return {}


def _log_call(to_number: str, company: str, result: dict):
    """Log call result to call_logs/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = "".join(c if c.isalnum() or c in "-_ " else "" for c in company).strip().replace(" ", "_")
    log_file = CACHE_DIR / f"{ts}_{safe_company}.json"
    log_data = {
        "to_number": to_number,
        "company": company,
        "timestamp": datetime.now().isoformat(),
        "response": result,
    }
    log_file.write_text(json.dumps(log_data, indent=2, ensure_ascii=False))
    print(f"  ✓ Call logged to {log_file.name}")


# ─────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────


def cmd_create_agent(args):
    """Create the ElevenLabs Conversational AI agent."""
    print("🤖 Creating ElevenLabs Conversational AI Agent...")
    print(f"   Voice: Sarah ({VOICE_ID})")
    print(f"   Language: German (de)")
    print()

    payload = {
        "name": "ACV Router - HVAC Sales (Lisa Weber)",
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": AGENT_SYSTEM_PROMPT,
                },
                "first_message": (
                    "Guten Tag, mein Name ist Lisa Weber von ACV Router. "
                    "Spreche ich mit {{contact_name}} von {{company_name}} in {{city}}? "
                    "Wunderbar! Ich rufe an, weil wir speziell für SHK-Betriebe wie Ihren "
                    "eine Lösung entwickelt haben, die Ihnen bei der Auftragsverwaltung "
                    "und Technikerplanung enorm Zeit sparen kann. Haben Sie kurz zwei Minuten?"
                ),
                "language": "de",
            },
            "tts": {
                "voice_id": VOICE_ID,
            },
        },
    }

    resp = requests.post(f"{BASE_URL}/convai/agents/create", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        data = resp.json()
        agent_id = data.get("agent_id", "")
        print(f"  ✅ Agent created successfully!")
        print(f"     Agent ID: {agent_id}")
        _save_agent_config(agent_id, VOICE_ID)
        return agent_id
    else:
        print(f"  ❌ Error creating agent: {resp.status_code}")
        print(f"     {resp.text}")
        return None


def cmd_list_agents(args):
    """List all existing agents."""
    print("📋 Listing ElevenLabs agents...")
    resp = requests.get(f"{BASE_URL}/convai/agents", headers=HEADERS)

    if resp.status_code == 200:
        data = resp.json()
        agents = data.get("agents", [])
        if not agents:
            print("  No agents found. Run: python cold_call.py create-agent")
            return

        for a in agents:
            print(f"  • {a.get('name', 'unnamed'):50s} | ID: {a.get('agent_id', '?')}")
    else:
        print(f"  ❌ Error: {resp.status_code} — {resp.text}")


def cmd_list_phones(args):
    """List imported phone numbers."""
    print("📞 Listing phone numbers...")
    resp = requests.get(f"{BASE_URL}/convai/phone-numbers", headers=HEADERS)

    if resp.status_code == 200:
        numbers = resp.json()
        if isinstance(numbers, list):
            if not numbers:
                print("  No phone numbers imported yet.")
                print("  To make outbound calls, import a Twilio number:")
                print("    python cold_call.py import-phone --number '+49...' --sid 'AC...' --token '...'")
                return
            for n in numbers:
                print(f"  • {n.get('phone_number', '?'):20s} | ID: {n.get('phone_number_id', '?')} | Label: {n.get('label', '')}")
        else:
            print(f"  Response: {json.dumps(numbers, indent=2)}")
    else:
        print(f"  ❌ Error: {resp.status_code} — {resp.text}")


def cmd_import_phone(args):
    """Import a Twilio phone number into ElevenLabs."""
    print(f"📱 Importing phone number: {args.number}")

    payload = {
        "provider": "twilio",
        "label": args.label or "ACV Router Outbound",
        "phone_number": args.number,
        "sid": args.sid,
        "token": args.token,
    }

    resp = requests.post(f"{BASE_URL}/convai/phone-numbers", headers=HEADERS, json=payload)

    if resp.status_code in (200, 201):
        data = resp.json()
        phone_id = data.get("phone_number_id", "")
        print(f"  ✅ Phone number imported!")
        print(f"     Phone Number ID: {phone_id}")
        print(f"     Use this ID for outbound calls.")

        # Update agent config
        config = _load_agent_config()
        config["phone_number_id"] = phone_id
        AGENT_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    else:
        print(f"  ❌ Error: {resp.status_code} — {resp.text}")


def cmd_call(args):
    """Trigger a single outbound call."""
    config = _load_agent_config()
    agent_id = args.agent_id or config.get("agent_id", "")
    phone_id = args.phone_id or config.get("phone_number_id", "")

    if not agent_id:
        print("  ❌ No agent_id. Run: python cold_call.py create-agent")
        return
    if not phone_id:
        print("  ❌ No phone_number_id. Run: python cold_call.py import-phone ...")
        return

    to_number = args.to
    company = args.company or "Ihr Unternehmen"
    contact = args.contact or "dem Geschäftsführer"
    city = args.city or ""
    technicians = args.technicians or "einigen"

    print(f"📞 Calling {to_number} ({company})...")
    print(f"   Agent: {agent_id}")
    print(f"   From:  {phone_id}")

    payload = {
        "agent_id": agent_id,
        "agent_phone_number_id": phone_id,
        "to_number": to_number,
        "conversation_initiation_client_data": {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": {
                "company_name": company,
                "contact_name": contact,
                "city": city,
                "technician_count": str(technicians),
            },
        },
    }

    resp = requests.post(f"{BASE_URL}/convai/twilio/outbound-call", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✅ Call initiated!")
        print(f"     Conversation ID: {data.get('conversation_id', '?')}")
        if data.get("callSid"):
            print(f"     Twilio Call SID: {data['callSid']}")
        _log_call(to_number, company, data)
    else:
        print(f"  ❌ Error: {resp.status_code}")
        print(f"     {resp.text}")
        _log_call(to_number, company, {"error": resp.status_code, "body": resp.text})


def cmd_batch_call(args):
    """Batch call top N leads from enriched CSV."""
    csv_path = args.csv
    limit = args.limit
    delay = args.delay

    config = _load_agent_config()
    agent_id = args.agent_id or config.get("agent_id", "")
    phone_id = args.phone_id or config.get("phone_number_id", "")

    if not agent_id:
        print("  ❌ No agent_id. Run: python cold_call.py create-agent")
        return
    if not phone_id:
        print("  ❌ No phone_number_id. Run: python cold_call.py import-phone ...")
        return

    print(f"📞 Batch calling from: {csv_path}")
    print(f"   Limit: {limit} calls, Delay: {delay}s between calls")
    print()

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    # Filter to leads with phone numbers
    callable_leads = [
        lead for lead in leads
        if lead.get("Phone Number", "").strip()
    ]

    print(f"   Total leads: {len(leads)}")
    print(f"   With phone:  {len(callable_leads)}")
    print(f"   Will call:   {min(limit, len(callable_leads))}")
    print()

    called = 0
    for lead in callable_leads[:limit]:
        phone = lead["Phone Number"].strip()
        company = lead.get("Company Name", "Unbekannt")
        city = lead.get("City", "")
        contact = "dem Geschäftsführer"  # Default, could be enriched

        # Normalize phone to E.164 if not already
        if not phone.startswith("+"):
            if phone.startswith("0"):
                phone = "+49" + phone[1:]  # Assume German
            else:
                phone = "+" + phone

        print(f"  [{called + 1}/{min(limit, len(callable_leads))}] Calling {company} ({phone})...")

        payload = {
            "agent_id": agent_id,
            "agent_phone_number_id": phone_id,
            "to_number": phone,
            "conversation_initiation_client_data": {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": {
                    "company_name": company,
                    "contact_name": contact,
                    "city": city,
                    "technician_count": lead.get("AI Ark Headcount", "einigen"),
                },
            },
        }

        resp = requests.post(f"{BASE_URL}/convai/twilio/outbound-call", headers=HEADERS, json=payload)

        if resp.status_code == 200:
            data = resp.json()
            print(f"       ✅ Conversation: {data.get('conversation_id', '?')}")
            _log_call(phone, company, data)
        else:
            print(f"       ❌ Error: {resp.status_code} — {resp.text[:100]}")
            _log_call(phone, company, {"error": resp.status_code, "body": resp.text[:200]})

        called += 1
        if called < min(limit, len(callable_leads)):
            print(f"       ⏳ Waiting {delay}s...")
            time.sleep(delay)

    print()
    print(f"  ✅ Batch complete: {called} calls initiated")


def cmd_list_calls(args):
    """List recent conversations/calls."""
    config = _load_agent_config()
    agent_id = args.agent_id or config.get("agent_id", "")

    if not agent_id:
        print("  ❌ No agent_id. Run: python cold_call.py create-agent")
        return

    print(f"📋 Listing recent calls for agent: {agent_id}")

    resp = requests.get(
        f"{BASE_URL}/convai/conversations",
        headers=HEADERS,
        params={"agent_id": agent_id},
    )

    if resp.status_code == 200:
        data = resp.json()
        convos = data.get("conversations", [])
        if not convos:
            print("  No conversations found.")
            return

        for c in convos:
            status = c.get("status", "?")
            cid = c.get("conversation_id", "?")
            created = c.get("start_time_unix_secs", "")
            duration = c.get("call_duration_secs", "?")
            print(f"  • {cid[:12]}... | Status: {status:10s} | Duration: {duration}s | Started: {created}")
    else:
        print(f"  ❌ Error: {resp.status_code} — {resp.text}")


def cmd_get_call(args):
    """Get transcript/details of a specific conversation."""
    conv_id = args.conversation_id

    print(f"📄 Getting conversation: {conv_id}")

    resp = requests.get(f"{BASE_URL}/convai/conversations/{conv_id}", headers=HEADERS)

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Status: {data.get('status', '?')}")
        print(f"  Duration: {data.get('call_duration_secs', '?')}s")
        print()

        transcript = data.get("transcript", [])
        if transcript:
            print("  === Transcript ===")
            for msg in transcript:
                role = msg.get("role", "?")
                text = msg.get("message", "")
                icon = "🤖" if role == "agent" else "👤"
                print(f"  {icon} {role.upper()}: {text}")
        else:
            print("  No transcript available.")

        # Save full response
        log_file = CACHE_DIR / f"conversation_{conv_id}.json"
        log_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n  ✓ Full details saved to {log_file.name}")
    else:
        print(f"  ❌ Error: {resp.status_code} — {resp.text}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="ElevenLabs Cold Call Pipeline for HVAC/SHK Leads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # create-agent
    sub.add_parser("create-agent", help="Create the Conversational AI agent")

    # list-agents
    sub.add_parser("list-agents", help="List all agents")

    # list-phones
    sub.add_parser("list-phones", help="List imported phone numbers")

    # import-phone
    p_phone = sub.add_parser("import-phone", help="Import a Twilio phone number")
    p_phone.add_argument("--number", required=True, help="Phone number in E.164 format")
    p_phone.add_argument("--sid", required=True, help="Twilio Account SID")
    p_phone.add_argument("--token", required=True, help="Twilio Auth Token")
    p_phone.add_argument("--label", default="ACV Router Outbound", help="Label for this number")

    # call
    p_call = sub.add_parser("call", help="Call a single lead")
    p_call.add_argument("--to", required=True, help="Phone number to call (E.164)")
    p_call.add_argument("--company", default="", help="Company name")
    p_call.add_argument("--contact", default="dem Geschäftsführer", help="Contact name")
    p_call.add_argument("--city", default="", help="City")
    p_call.add_argument("--technicians", default="", help="Estimated technician count")
    p_call.add_argument("--agent-id", default="", help="Agent ID (auto-loaded from config)")
    p_call.add_argument("--phone-id", default="", help="Phone number ID (auto-loaded from config)")

    # batch-call
    p_batch = sub.add_parser("batch-call", help="Batch call leads from CSV")
    p_batch.add_argument(
        "--csv",
        default=str(Path(__file__).parent.parent / "ai_ark" / "ai_ark_dach_handwerker_hvac_828_enriched.csv"),
        help="Path to enriched CSV",
    )
    p_batch.add_argument("--limit", type=int, default=5, help="Max calls to make (default 5)")
    p_batch.add_argument("--delay", type=int, default=30, help="Seconds between calls (default 30)")
    p_batch.add_argument("--agent-id", default="", help="Agent ID")
    p_batch.add_argument("--phone-id", default="", help="Phone number ID")

    # list-calls
    p_list = sub.add_parser("list-calls", help="List recent calls/conversations")
    p_list.add_argument("--agent-id", default="", help="Agent ID")

    # get-call
    p_get = sub.add_parser("get-call", help="Get call transcript/details")
    p_get.add_argument("conversation_id", help="Conversation ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if not API_KEY:
        print("❌ ELEVENLABS_API_KEY not set. Check elevenlabs/.env")
        sys.exit(1)

    commands = {
        "create-agent": cmd_create_agent,
        "list-agents": cmd_list_agents,
        "list-phones": cmd_list_phones,
        "import-phone": cmd_import_phone,
        "call": cmd_call,
        "batch-call": cmd_batch_call,
        "list-calls": cmd_list_calls,
        "get-call": cmd_get_call,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
