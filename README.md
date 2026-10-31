# ACV Router: Autonomous Outbound Lead Generation & Outreach Engine

An integrated AI-native outbound pipeline and live Bento dashboard built for DACH HVAC & mechanical trades (**SHK-Betriebe**), proxying as **[Meisterpfad](https://www.meisterpfad.de/)**.

The system automates the complete outbound lifecycle:
1. **Multi-Channel Enrichment:** Discovers and validates postal addresses, headcount, and official phone numbers via **AI Ark** and **Lusha**.
2. **ACV Router & Motion Scoring:** Estimates Annual Contract Value (ACV) and assigns leads to GTM motions (*High-Touch*, *Automated*, *Welcome*, *Check*).
3. **LinkedIn Social Selling:** Tailors AI-personalized German outreach messages and connects directly via **Needle MCP** (`https://needle.app`).
4. **Conversational AI Cold Calling:** Dials cell phones via **Twilio** carrier trunking connected to **ElevenLabs Conversational AI** (Agent: *Lisa Weber*, voice: *Sarah*), featuring patient turn-taking and natural pacing.
5. **Multi-Channel Demo Dispatch:** Automatically delivers SMS confirmations via Twilio trial carrier and registers calendar invitations to `tzm2002@protonmail.com`.
6. **Bento Grid Dashboard:** Modern dark-dock and rounded bento UI (`http://localhost:3000`) displaying pipeline ACV, lead volume, and call metrics.

---

## Architecture & Directory Layout

```
├── .env.example              # Consolidated environment configuration template
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
│
├── data/                     # Lead data & ACV scoring results
│   ├── dach_handwerker_hvac_828_leads.csv   # 828 Handwerker/HVAC master leads
│   ├── results.json                         # Scored companies with ACV, motions & evidence
│   └── pipeline_meta.json                   # Pipeline configuration and motion stats
│
├── web/                      # Fast-API Backend & Modern Bento Dashboard
│   ├── server.py             # Telephony, SMS, LinkedIn bridge & REST API
│   ├── templates/index.html  # Modern Bento-Grid UI
│   └── static/               # Assets & voice greeting audio
│
├── elevenlabs/               # ElevenLabs Conversational AI & Telephony
│   ├── cold_call.py          # Voice agent configuration and outbound calling CLI
│   ├── agent_config.json     # Agent ID & Twilio phone link
│   └── call_logs/            # Telephony transcripts and call records
│
├── needle/                   # Needle LinkedIn Outreach Pipeline
│   ├── linkedin_outreach.py  # LinkedIn connection, AI message composer, & DM sender
│   ├── needle_pipeline.py    # Places discovery & bulk ingestion
│   └── needle_dach_handwerker_hvac_828_leads.csv
│
├── ai_ark/                   # AI Ark Lead Intelligence Engine
│   ├── enrich_with_ai_ark.py # Enrichment runner (phones, addresses, headcount)
│   ├── ai_ark_pipeline.py    # AI Ark search & verification pipeline
│   └── ai_ark_enriched_cache.json
│
├── lusha/                    # High-Touch Contact Scraping & Phone Discovery
│   ├── scrape_full_details_and_export_csv.py
│   └── lusha_dach_handwerker_hvac_828_leads.csv
│
└── bridge/                   # Data Transform & Motion Router
    └── export_to_acv_router.py # Computes formula: monthly = 200 + 100*(office-1) + 25*techs
```

---

## Quickstart

### 1. Installation

```bash
# Clone repository
git clone https://github.com/tyler-t-ai/acv-router.git
cd acv-router

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

```ini
# ElevenLabs Conversational Voice AI
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
ELEVENLABS_AGENT_ID=agent_6001m691m0v1eh3b6w07nqrgy188

# Twilio Telephony Carrier & SMS Trunk
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+17813854598

# Needle LinkedIn Outreach
NEEDLE_API_KEY=sk-ndl-...

# AI Ark Enrichment Engine
AI_ARK_API_KEY=...
```

### 3. Start the Web Dashboard

```bash
python web/server.py
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Pipelines & Capabilities

### 1. Bento Dashboard (`web/`)
- **Dock Sidebar:** Obsidian rounded navigation dock with quick shortcuts.
- **Top Metrics Bento:**
  - *Leads Generated:* 829 accounts loaded with capsule progress indicators.
  - *Pipeline ACV:* €9.9M in total pipeline value (Neon Lime Bento card).
  - *Agent Calls Made:* 428 calls dispatched, 38 demos booked.
  - *Dual Capsule Bar Chart:* Visual activity breakdown with floating percentage tags.
- **Leads Table:** Filter by motion (*High-Touch*, *Automated*, *Berlin Focus*).
- **Interactive Details Drawer:**
  - Full ACV breakdown (Monteure, Office seats, Monthly recurring, Annual ACV).
  - Outbound actions: **Call via Twilio**, **Send LinkedIn Message**, **Send Demo Invite (SMS + Email)**.
  - Zero mock history: Conversation history stays blank until a real phone call or LinkedIn outreach completes.

### 2. Conversational AI Cold Calling (`elevenlabs/`)
- Agent persona: **Lisa Weber** (Meisterpfad SDR).
- Voice: **Sarah** (`EXAVITQu4vr4xnSDxMaL`).
- **Patient Turn-Taking:** Configured with `turn_eagerness: "patient"` and `turn_timeout: 10.0s`, waiting silently for prospects to finish speaking before responding.
- **Telephony Carrier:** Direct Twilio outbound carrier dialing.

### 3. LinkedIn Social Selling (`needle/`)
- Direct integration with **Needle MCP** (`https://needle.app/mcp/v1`).
- Dynamically composes personalized outreach messages in formal German based on the target's business focus and technician count.
- Direct inbox message delivery for 1st-degree connections and connection requests for out-of-network leads.

### 4. ACV Scoring Engine (`bridge/`)
- **Formula:**
  $$\text{Monthly} = 200 + 100 \times (\text{Office Seats} - 1) + 25 \times \text{Technicians}$$
  $$\text{ACV} = 12 \times \text{Monthly}$$
- Threshold: accounts at or above **€6,300** route to the **High-Touch** lane for outbound calling and LinkedIn outreach.
