# Needle Lead Generation & LinkedIn Outreach Pipeline

This pipeline manages discovery, lead schema formatting, and automated multichannel outreach with [Needle](https://needle.app) (`https://needle.app/mcp/v1`).

Needle provides agent-native outbound infrastructure across **LinkedIn**, **Instagram**, and **Google Places**, with AI-composed messaging and automated graph sequences.

---

## Connected LinkedIn Account

- **User**: Xavor Trennt (`xavor-trennt-61b2472a1`)
- **Account ID**: `01a191ff-038b-7790-974d-5a0da6f261ea`
- **Status**: `active` (`canUse: true`)
- **Proxy**: DE (German residential IP)

## Automated LinkedIn Outreach Campaign

- **Campaign Name**: `Meisterpfad SHK sales outreach Berlin & Brandenburg`
- **Campaign ID**: `01a191f1-3778-7cb1-a608-4af5b68accb4`
- **Schedule**: Mon–Fri 09:00–17:00 (Europe/Berlin)
- **Multi-Step Graph**:
  ```
  [Start] ──> [Already Connection?]
                  │              │
                (Yes)           (No)
                  │              │
                  │              ▼
                  │     [Send Connection Invite]
                  │              │
                  │              ▼
                  │     [Wait Acceptance (14d)] ──(timeout)──> [End]
                  │              │
                  │          (accepted)
                  ▼              ▼
           [First AI Message (German SHK Backoffice pitch, <500 chars)]
                                 │
                                 ▼
                     [Wait for Reply (3d)] ──(replied)──> [End]
                                 │
                             (timeout)
                                 ▼
           [Nudge AI Message (Automated dunning & site reports, <300 chars)]
                                 │
                                 ▼
                              [End]
  ```

---

## Files

| File | Purpose |
|---|---|
| `linkedin_outreach.py` | Complete LinkedIn CLI: discovery, preview, invite, messaging, campaign management |
| `test_linkedin_outreach.py` | Unit tests for LinkedIn outreach module |
| `needle_pipeline.py` | Core pipeline: schema conversion, Places discovery, bulk upload |
| `needle_dach_handwerker_hvac_828_leads.csv` | Needle-ready CSV dataset with LinkedIn URLs |
| `needle_leads_batch.json` | JSON payload batch for Needle's bulk lead API |
| `.env` | `NEEDLE_API_KEY` (git-ignored) |

---

## LinkedIn Outreach CLI Usage

### 1. Check Connected Account & Limits
```bash
python3 linkedin_outreach.py status
```

### 2. Live Search for Decision-Makers on LinkedIn
```bash
python3 linkedin_outreach.py search --keywords "Geschäftsführer SHK Berlin" --limit 5
```

### 3. Generate Personalized AI Outreach Message Preview
Preview an AI message crafted from the recipient's live LinkedIn profile:
```bash
python3 linkedin_outreach.py preview --identity "philip-krone-266756106"
```

### 4. Send LinkedIn Connection Invitation
```bash
python3 linkedin_outreach.py invite \
  --identity "philip-krone-266756106" \
  --note "Guten Tag Herr Krone, gerne würde ich mich mit Ihnen zum Thema SHK-Digitalisierung vernetzen."
```

### 5. Send Direct LinkedIn Message
```bash
python3 linkedin_outreach.py message \
  --identity "philip-krone-266756106" \
  --text "Guten Tag Herr Krone, vielen Dank für die Vernetzung..."
```

### 6. Monitor Automated Campaign Funnel & Enrolled Leads
```bash
python3 linkedin_outreach.py campaign-stats
python3 linkedin_outreach.py campaign-leads
```

### 7. Start / Pause Automated Campaign
```bash
python3 linkedin_outreach.py campaign-start
python3 linkedin_outreach.py campaign-pause
```

---

## Run All Tests

```bash
python3 -m unittest test_linkedin_outreach.py -v
python3 -m unittest test_needle_pipeline.py -v
```
