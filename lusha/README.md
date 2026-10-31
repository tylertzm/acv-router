# Lusha Lead Generation Pipeline

This pipeline manages discovery, enrichment, phone/fax extraction, and CSV formatting tailored for Lusha contact enrichment and CRM export.

## Contents

- `lusha_dach_handwerker_hvac_828_leads.csv`: The enriched 828-lead dataset formatted for direct Lusha platform import (includes phone numbers, fax numbers, emails, descriptions, domains, and Lusha IDs).
- `scrape_full_details_and_export_csv.py`: Multi-threaded website scraper (40 workers) that extracts verified phone numbers, fax numbers, emails, and company descriptions from company websites and impressum pages.
- `scrape_fax_and_export_lusha_csv.py`: Dedicated scraper for German/Swiss/Austrian fax formats.
- `scraped_cache.json`: Cached scraped data for fast re-exports without network re-fetching.
- `test_scrape.py`: Unit test and probe script for website extraction regexes.

## Execution

To run the full scraper & export:
```bash
python3 scrape_full_details_and_export_csv.py
```

## Lusha MCP Integration

The Lusha MCP server is configured in `~/.gemini/config/mcp_config.json`:
- Endpoint: `https://mcp.lusha.com`
- Available tools: `prospecting_company_search`, `prospecting_contact_enrich`, `companies_search`, `contacts_search`, etc.
