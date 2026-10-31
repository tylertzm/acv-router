# ElevenLabs Cold Call Pipeline

AI-powered outbound cold calling for HVAC/SHK leads using ElevenLabs Conversational AI.

## Agent: Lisa Weber

- **Voice**: Sarah (EXAVITQu4vr4xnSDxMaL) — Mature, Reassuring, Confident
- **Language**: German (formal "Sie")
- **Agent ID**: `agent_6001m691m0v1eh3b6w07nqrgy188`
- **Persona**: Professional sales development rep for ACV Router

## Setup

```bash
cd elevenlabs
python3 -m venv .venv
source .venv/bin/activate
pip install python-dotenv requests
```

## Commands

| Command | Description |
|---|---|
| `python cold_call.py create-agent` | Create the AI sales agent on ElevenLabs |
| `python cold_call.py list-agents` | List all agents |
| `python cold_call.py list-phones` | List imported phone numbers |
| `python cold_call.py import-phone --number '+49...' --sid 'AC...' --token '...'` | Import Twilio number |
| `python cold_call.py call --to '+4930123456' --company 'Krone GmbH'` | Call single lead |
| `python cold_call.py batch-call --limit 5` | Batch call top 5 leads from enriched CSV |
| `python cold_call.py list-calls` | List recent call history |
| `python cold_call.py get-call <conversation_id>` | Get call transcript |

## Outbound Calling Flow

```
ElevenLabs Agent (Lisa Weber)
         ↓
   Twilio Phone Number (must import first)
         ↓
   Outbound Call to Lead's Phone
         ↓
   AI converses in German, qualifies lead
         ↓
   Call logged to call_logs/
```

### Prerequisites for Live Calls

1. ✅ ElevenLabs agent created
2. ⬜ Twilio account with a German phone number (+49...)
3. ⬜ Import Twilio number into ElevenLabs:
   ```bash
   python cold_call.py import-phone \
     --number "+49301234567" \
     --sid "ACXXXXXXXX" \
     --token "your_twilio_auth_token"
   ```
4. Then call:
   ```bash
   python cold_call.py call \
     --to "+49309929350" \
     --company "Krone GmbH" \
     --contact "Herr Schmidt" \
     --city "Berlin"
   ```

## Data Source

Reads enriched leads from `../ai_ark/ai_ark_dach_handwerker_hvac_828_enriched.csv` (498 leads with phone numbers).

## Files

| File | Purpose |
|---|---|
| `cold_call.py` | Main CLI — agent management, calling, logging |
| `agent_config.json` | Saved agent ID + voice ID |
| `.env` | API key (git-ignored) |
| `call_logs/` | JSON logs per call |
| `test_cold_call.py` | Unit tests |
