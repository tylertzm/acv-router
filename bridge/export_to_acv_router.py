#!/usr/bin/env python3
"""
ACV Router Data Bridge
======================

Converts enriched CSV data from AI Ark / Lusha / Needle pipelines into
the ACV Router frontend's ScoredCompany JSON format.

Implements the ACV formula, confidence scoring, and motion routing as
defined in the ACV Router spec:

  monthly = 200 + 100 * (officeSeats - 1) + 25 * technicians
  acv     = 12 * monthly

Motions:
  1. Registered in last 90 days → "welcome"
  2. Low confidence, ACV within ±25% of threshold → "check"
  3. ACV >= threshold → "high_touch"
  4. Otherwise → "automated"

Usage:
  python export_to_acv_router.py                          # Full export
  python export_to_acv_router.py --berlin-only             # Berlin/BB only
  python export_to_acv_router.py --output ../data/results.json
  python export_to_acv_router.py --stats                   # Print stats only
"""

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# ACV Router Config (matches lib/config.ts)
# ─────────────────────────────────────────────────────────────

REPS = 2
CALLS_PER_REP = 30
CAPACITY = REPS * CALLS_PER_REP  # 60

LUSHA_MAX_ACCOUNTS = 20

# Pricing
BASE_MONTHLY = 200
PER_OFFICE_SEAT = 100  # after the first
PER_TECHNICIAN = 25

# Default Demo / Mock Target Lead
TYLER_TAN_LEAD = {
    "id": "tyler-tan-hvac-installation-gmbh",
    "name": "HVAC Installation GmbH",
    "contactName": "Tyler Tan",
    "legalForm": "GmbH",
    "specialty": "Haustechnik & HVAC für gemeinnützige Träger (Kitas, Geflüchtetenunterkünfte, LGBTQ+ Zentren)",
    "description": "Spezialisierter SHK-Meisterbetrieb in Berlin für soziale & gemeinnützige Einrichtungen: Moderne Heizungs-, Lüftungs- und Sanitärinstallation für Kindergärten, Unterkünfte für Geflüchtete und LGBTQ+ Community-Spaces.",
    "address": {
        "street": "Friedrichstraße 123",
        "zip": "10117",
        "city": "Berlin",
    },
    "phone": "015730699953",
    "phoneE164": "+4915730699953",
    "website": "www.hvac-installation-berlin.de",
    "linkedin": "https://www.linkedin.com/in/tylertan0/",
    "linkedinSlug": "tylertan0",
    "sources": ["innung", "register"],
    "registerId": "HRB 198234 B",
    "registeredAt": "2024-01-15T00:00:00Z",
    "managingDirectors": ["Tyler Tan"],
    "isDemoTarget": True,
    "estimate": {
        "technicians": {
            "value": 18,
            "low": 16,
            "high": 20,
            "confidence": "high",
            "evidence": [
                {
                    "source": "website",
                    "url": "https://www.linkedin.com/in/tylertan0/",
                    "finding": "18 spezialisierte Monteure & Techniker für soziale Bauvorhaben (Kitas, Geflüchtetenunterkünfte, LGBTQ+ Zentren in Berlin)",
                    "fetchedAt": datetime.now().isoformat(),
                }
            ],
        },
        "officeSeats": {
            "value": 3,
            "low": 2,
            "high": 4,
            "confidence": "high",
            "evidence": [
                {
                    "source": "impressum",
                    "finding": "Geschäftsführung Tyler Tan, 3 Bürokräfte für Projektkoordination und gemeinnützige Vergabeverfahren",
                    "fetchedAt": datetime.now().isoformat(),
                }
            ],
        },
        "monthly": 833,
        "acv": 10000,
        "acvLow": 8800,
        "acvHigh": 11200,
        "confidence": "high",
    },
    "motion": "high_touch",
    "motionReason": "Top High-Touch Priority Account: ACV €10,000 (Threshold €6,300). Berlin Non-Profit & Social Infrastructure Specialist (Kitas, Refugee camps, LGBTQ+ community). Priority for Lisa Weber voice call & Needle LinkedIn outreach.",
}



# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def clean_record(d):
    """Recursively remove None values so Zod optional fields do not fail validation."""
    if isinstance(d, dict):
        return {k: clean_record(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [clean_record(v) for v in d if v is not None]
    return d


def slugify(name: str, zip_code: str) -> str:
    """Create a stable slug from company name and zip."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", slug)
    slug = slug.strip("-")
    if zip_code:
        slug = f"{slug}-{zip_code.strip()}"
    return slug


def detect_legal_form(name: str) -> str:
    """Detect legal form from company name."""
    name_lower = name.lower()
    if "gmbh & co. kg" in name_lower or "gmbh & co kg" in name_lower:
        return "GmbH & Co. KG"
    elif "gmbh" in name_lower:
        return "GmbH"
    elif "ug" in name_lower and ("haftungsbeschränkt" in name_lower or "(haftungsbeschränkt)" in name_lower):
        return "UG"
    elif " ug " in name_lower or name_lower.endswith(" ug"):
        return "UG"
    elif "e.k." in name_lower or " e.k" in name_lower:
        return "e.K."
    elif "ag" in name_lower.split():
        return "GmbH"  # Map AG to GmbH for scoring purposes
    else:
        return "unknown"


def estimate_headcount(row: dict) -> int:
    """Estimate total headcount from available data."""
    # Try AI Ark headcount first
    hc = row.get("AI Ark Headcount", "").strip()
    if hc:
        try:
            return int(float(hc))
        except ValueError:
            pass

    # Try Employee Headcount
    hc = row.get("Employee Headcount", "").strip()
    if hc:
        try:
            return int(float(hc))
        except ValueError:
            pass

    return 0


def estimate_revenue_range(row: dict) -> tuple:
    """Parse revenue range string into (low, high) in EUR."""
    rev = row.get("Revenue Range", "").strip()
    if not rev:
        return (0, 0)

    # Parse "50000000-100000000" format
    parts = rev.split("-")
    if len(parts) == 2:
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            pass

    return (0, 0)


def estimate_technicians(headcount: int, legal_form: str) -> dict:
    """Estimate technician count from headcount."""
    if headcount > 0:
        # HVAC companies: roughly 60-75% are technicians
        tech_ratio = 0.65
        value = max(1, round(headcount * tech_ratio))
        low = max(1, round(headcount * 0.5))
        high = round(headcount * 0.8)
        confidence = "high" if headcount > 10 else "medium"
    elif legal_form in ("GmbH", "GmbH & Co. KG"):
        # Medium-sized estimate for GmbH
        value, low, high = 5, 2, 10
        confidence = "low"
    elif legal_form == "e.K.":
        # Small sole trader
        value, low, high = 2, 1, 4
        confidence = "low"
    else:
        # Unknown — very conservative
        value, low, high = 3, 1, 6
        confidence = "low"

    return {"value": value, "low": low, "high": high, "confidence": confidence}


def estimate_office_seats(technicians: int, headcount: int) -> dict:
    """Estimate office staff count."""
    if headcount > 0:
        # Office = total - technicians (rough)
        office = max(1, headcount - technicians)
        low = max(1, office - 1)
        high = office + 2
        confidence = "medium"
    else:
        # Fallback formula from ACV Router spec
        value = 1 + math.floor(technicians / 7)
        return {"value": value, "low": 1, "high": value + 1, "confidence": "low"}

    return {"value": office, "low": low, "high": high, "confidence": confidence}


def compute_acv(technicians: dict, office_seats: dict) -> dict:
    """Compute ACV using the ACV Router formula."""
    monthly = BASE_MONTHLY + PER_OFFICE_SEAT * (office_seats["value"] - 1) + PER_TECHNICIAN * technicians["value"]
    monthly_low = BASE_MONTHLY + PER_OFFICE_SEAT * (office_seats["low"] - 1) + PER_TECHNICIAN * technicians["low"]
    monthly_high = BASE_MONTHLY + PER_OFFICE_SEAT * (office_seats["high"] - 1) + PER_TECHNICIAN * technicians["high"]

    acv = 12 * monthly
    acv_low = 12 * monthly_low
    acv_high = 12 * monthly_high

    # Overall confidence is the lower of the two
    conf_order = {"low": 0, "medium": 1, "high": 2}
    overall = min(conf_order[technicians["confidence"]], conf_order[office_seats["confidence"]])
    confidence = ["low", "medium", "high"][overall]

    return {
        "monthly": monthly,
        "acv": acv,
        "acvLow": acv_low,
        "acvHigh": acv_high,
        "confidence": confidence,
    }


def determine_motion(acv: int, confidence: str, threshold: int, registered_at: str = None) -> tuple:
    """Determine the motion for a company. Returns (motion, reason)."""
    # 1. Welcome: registered in last 90 days
    if registered_at:
        try:
            reg_date = datetime.fromisoformat(registered_at.replace("Z", "+00:00"))
            if (datetime.now(reg_date.tzinfo) if reg_date.tzinfo else datetime.now()) - reg_date < timedelta(days=90):
                return ("welcome", f"Newly registered ({registered_at[:10]}), receives early hello and warm intro.")
        except (ValueError, TypeError):
            pass

    # 2. Check: low confidence and ACV within ±25% of threshold
    if confidence == "low" and threshold > 0:
        if abs(acv - threshold) <= 0.25 * threshold:
            return ("check", f"Low confidence estimate (€{acv:,}) near threshold (€{threshold:,}), needs manual review.")

    # 3. High-touch: ACV >= threshold
    if acv >= threshold:
        return ("high_touch", f"ACV €{acv:,} exceeds threshold €{threshold:,}, assigned to named rep for personal experience.")

    # 4. Automated
    return ("automated", f"ACV €{acv:,} below threshold €{threshold:,}, self-serve automated motion.")


def build_evidence(row: dict) -> list:
    """Build evidence array from available data."""
    evidence = []
    now = datetime.now().isoformat()

    if row.get("AI Ark Match Status", "") == "Matched":
        evidence.append({
            "source": "register",
            "finding": f"Matched in AI Ark database (ID: {row.get('AI Ark ID', '?')})",
            "fetchedAt": now,
        })

    if row.get("Revenue Range", ""):
        evidence.append({
            "source": "register",
            "finding": f"Revenue range: {row['Revenue Range']}",
            "fetchedAt": now,
        })

    if row.get("AI Ark Headcount", ""):
        evidence.append({
            "source": "register",
            "finding": f"Staff count from AI Ark: {row['AI Ark Headcount']}",
            "fetchedAt": now,
        })

    domain = row.get("Company Domain", row.get("Domain", "")).strip()
    linkedin = row.get("Company LinkedIn", row.get("LinkedIn", "")).strip()
    if domain:
        evidence.append({
            "source": "website",
            "url": f"https://{domain}",
            "finding": f"Company website: {domain}",
            "fetchedAt": now,
        })

    if linkedin:
        evidence.append({
            "source": "website",
            "url": linkedin,
            "finding": "LinkedIn company page found",
            "fetchedAt": now,
        })

    return evidence


def convert_row(row: dict) -> dict:
    """Convert a single CSV row to ScoredCompany format."""
    name = row.get("Company Name", "").strip()
    zip_code = row.get("Postal Code", "").strip()
    city = row.get("City", "").strip()

    company_id = slugify(name, zip_code)
    legal_form = detect_legal_form(name)
    headcount = estimate_headcount(row)

    # Estimate drivers
    tech = estimate_technicians(headcount, legal_form)
    office = estimate_office_seats(tech["value"], headcount)
    acv_data = compute_acv(tech, office)

    # Build evidence
    evidence = build_evidence(row)

    # Sources
    sources = []
    if row.get("AI Ark Match Status", "") == "Matched":
        sources.append("register")
    if row.get("Lusha ID", "").strip():
        sources.append("innung")

    if not sources:
        sources = ["innung"]  # Default

    raw_linkedin = (row.get("Company LinkedIn", "") or row.get("LinkedIn", "")).strip()
    linkedin_slug = ""
    if raw_linkedin:
        linkedin_slug = raw_linkedin.rstrip("/").split("/")[-1]

    contact_name = (
        row.get("Contact Name", "").strip() or
        row.get("Target Persona", "").strip() or
        "Geschäftsführung"
    )

    company = {
        "id": company_id,
        "name": name,
        "contactName": contact_name,
        "legalForm": legal_form,
        "address": {
            "street": row.get("Street Address", "").strip() or None,
            "zip": zip_code or None,
            "city": city or None,
        },
        "phone": (row.get("Phone Number", "") or row.get("Phone", "")).strip() or None,
        "website": (row.get("Company Domain", "") or row.get("Domain", "")).strip() or None,
        "linkedin": raw_linkedin or None,
        "linkedinSlug": linkedin_slug or None,
        "sources": sources,
        "registerId": row.get("AI Ark ID", "").strip() or None,
    }

    # Clean None values from address
    company["address"] = {k: v for k, v in company["address"].items() if v}

    estimate = {
        "technicians": {
            "value": tech["value"],
            "low": tech["low"],
            "high": tech["high"],
            "confidence": tech["confidence"],
            "evidence": [e for e in evidence if "staff" in e.get("finding", "").lower() or "headcount" in e.get("finding", "").lower()] or evidence[:1],
        },
        "officeSeats": {
            "value": office["value"],
            "low": office["low"],
            "high": office["high"],
            "confidence": office["confidence"],
            "evidence": evidence[:1],
        },
        "monthly": acv_data["monthly"],
        "acv": acv_data["acv"],
        "acvLow": acv_data["acvLow"],
        "acvHigh": acv_data["acvHigh"],
        "confidence": acv_data["confidence"],
    }

    return {**company, "estimate": estimate}


def compute_threshold(companies: list) -> int:
    """Compute the ACV threshold from sorted companies."""
    sorted_by_acv = sorted(companies, key=lambda c: c["estimate"]["acv"], reverse=True)

    if len(sorted_by_acv) >= CAPACITY:
        threshold = sorted_by_acv[CAPACITY - 1]["estimate"]["acv"]
    elif sorted_by_acv:
        threshold = sorted_by_acv[-1]["estimate"]["acv"]
    else:
        threshold = 0

    # Round to nearest 100
    return round(threshold / 100) * 100

    return threshold


def export(csv_path: str, output_path: str, berlin_only: bool = False, stats_only: bool = False):
    """Main export function."""
    print(f"📊 Loading enriched CSV: {csv_path}")

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"   Total rows: {len(rows)}")

    # Optional Berlin/Brandenburg filter
    if berlin_only:
        rows = [r for r in rows if r.get("Postal Code", "").strip()[:2] in ("10", "12", "13", "14", "15", "16")]
        print(f"   Berlin/BB filter: {len(rows)} leads")

    # Convert to ScoredCompany format (without motion yet)
    companies = [convert_row(row) for row in rows]

    # Compute threshold
    threshold = compute_threshold(companies)
    print(f"   ACV Threshold: €{threshold:,}")

    # Assign motions
    motion_counts = {"high_touch": 0, "automated": 0, "welcome": 0, "check": 0}
    for c in companies:
        motion, reason = determine_motion(
            c["estimate"]["acv"],
            c["estimate"]["confidence"],
            threshold,
        )
        c["motion"] = motion
        c["motionReason"] = reason
        motion_counts[motion] += 1

    # Sort by ACV descending
    companies.sort(key=lambda c: c["estimate"]["acv"], reverse=True)

    # Always ensure Tyler Tan is prepended at index 0 as the default demo target
    companies = [TYLER_TAN_LEAD] + [c for c in companies if c.get("id") != TYLER_TAN_LEAD["id"]]
    motion_counts["high_touch"] += 1


    # Stats
    print()
    print("   📈 Pipeline Stats:")
    print(f"      Total companies:  {len(companies)}")
    print(f"      High-touch:       {motion_counts['high_touch']}")
    print(f"      Automated:        {motion_counts['automated']}")
    print(f"      Welcome:          {motion_counts['welcome']}")
    print(f"      Check:            {motion_counts['check']}")
    print()

    acv_values = [c["estimate"]["acv"] for c in companies]
    if acv_values:
        print(f"      Max ACV:    €{max(acv_values):,}")
        print(f"      Min ACV:    €{min(acv_values):,}")
        print(f"      Avg ACV:    €{sum(acv_values) // len(acv_values):,}")
        print(f"      Threshold:  €{threshold:,}")
    print()

    # Top 5
    print("   🏆 Top 5 by ACV:")
    for c in companies[:5]:
        print(f"      {c['name']:40s} | ACV: €{c['estimate']['acv']:>8,} | {c['motion']}")
    print()

    if stats_only:
        return

    # Clean all records of None values
    companies = [clean_record(c) for c in companies]

    # Write output
    run_payload = {
        "generatedAt": datetime.now().isoformat(),
        "niche": {
            "id": "hvac-shk",
            "label": "HVAC / SHK contractors",
            "source": "Innung Berlin-Brandenburg & Handelsregister",
        },
        "threshold": threshold,
        "callsPerWeek": CAPACITY,
        "thresholdNote": f"set to fit {CAPACITY} calls a week",
        "companies": companies,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run_payload, indent=2, ensure_ascii=False))
    print(f"   ✅ Exported {len(companies)} companies to {output_path}")

    # Also write a summary metadata file
    meta = {
        "generated_at": datetime.now().isoformat(),
        "source_csv": csv_path,
        "total_companies": len(companies),
        "threshold_acv": threshold,
        "motions": motion_counts,
        "config": {
            "reps": REPS,
            "calls_per_rep": CALLS_PER_REP,
            "capacity": CAPACITY,
            "base_monthly": BASE_MONTHLY,
            "per_office_seat": PER_OFFICE_SEAT,
            "per_technician": PER_TECHNICIAN,
        },
    }
    meta_path = output.parent / "pipeline_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"   ✅ Metadata saved to {meta_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export enriched CSV to ACV Router ScoredCompany JSON",
    )
    parser.add_argument(
        "--csv",
        default=str(Path(__file__).parent.parent / "ai_ark" / "ai_ark_dach_handwerker_hvac_828_enriched.csv"),
        help="Path to enriched CSV",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent.parent / "data" / "results.json"),
        help="Output JSON path",
    )
    parser.add_argument("--berlin-only", action="store_true", help="Filter to Berlin/Brandenburg only (PLZ 10-16xxx)")
    parser.add_argument("--stats", action="store_true", help="Print stats only, don't write file")

    args = parser.parse_args()
    export(args.csv, args.output, berlin_only=args.berlin_only, stats_only=args.stats)


if __name__ == "__main__":
    main()
