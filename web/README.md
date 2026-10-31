# Meisterpfad ACV Router UI & Web Server

Interactive web dashboard for the **Meisterpfad ACV Router** lead generation & outbound routing system.

Proxying as **[Meisterpfad](https://www.meisterpfad.de/)** — AI-native back-office software for SHK (Sanitär, Heizung, Klima) Meisterbetriebe.

---

## Features

- **Live Lead Pipeline**: 829 scored HVAC/SHK leads across DACH (Berlin & Brandenburg focus).
- **Default Pinned Demo Target**:
  - **Company**: `HVAC Installation GmbH`
  - **Decision-Maker**: `Tyler Tan` (Geschäftsführer)
  - **Focus**: Non-profit installations in Berlin (Kindergärten / Kitas, Unterkünfte für Geflüchtete, LGBTQ+ Community-Zentren)
  - **Predicted ACV**: `€10,000` (18 technicians, 3 office staff)
  - **Motion**: `High-Touch` (Priority Account)
- **ElevenLabs Voice AI Cold Calling**:
  - Outbound dialing to `015730699953`
  - Agent: **Lisa Weber** (Voice: `Sarah`, warm & professional)
  - Full post-call conversation summary with customer interest rating:
    `Interested in Collaborating (Pilot Demo Booked: Thursday 10:00 Uhr)`
  - Live transcript excerpt and key takeaways extraction.
- **Needle LinkedIn Automated Outreach**:
  - Connected Account: `Xavor Trennt` (DE Residential Proxy)
  - Profile: `https://www.linkedin.com/in/tylertan0/`
  - Dynamic AI German outreach message composition reflecting non-profit mission
  - Invitation delivery and engagement status tracking.
- **Interactive ACV Engine & Formula**:
  - `monthly = 200 + 100 * (officeSeats - 1) + 25 * technicians`
  - Visual range bar with the €6,300 capacity threshold needle.

---

## Running the Web Server

```bash
cd /Users/tyler/Documents/lusha
/Users/tyler/Documents/lusha/elevenlabs/.venv/bin/python web/server.py
```

The application runs at **`http://localhost:3000`**.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Dashboard UI |
| `/api/stats` | `GET` | Pipeline motion metrics & threshold |
| `/api/leads` | `GET` | Paginated and filtered leads list |
| `/api/leads/{id}` | `GET` | Detailed company data, drivers & notes |
| `/api/call` | `POST` | Initiates ElevenLabs AI call & logs summary |
| `/api/linkedin/preview` | `POST` | Generates personalized AI message via Needle |
| `/api/linkedin/invite` | `POST` | Sends LinkedIn connection invitation |
| `/api/linkedin/message` | `POST` | Sends direct LinkedIn message |
| `/api/fax` | `POST` | Sends offer per Fax |
