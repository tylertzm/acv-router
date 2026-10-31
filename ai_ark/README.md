# AI Ark Lead Generation Pipeline

This pipeline manages B2B contact and company discovery, decision-maker matching, and real-time contact verification with [AI Ark](https://ai-ark.com) via their Model Context Protocol (MCP) server (`https://api.ai-ark.com/v1/mcp`) and REST API.

AI Ark provides access to 70M+ companies and 400M+ contacts with 30-day refresh cycles and real-time email verification.

## Contents

- `ai_ark_dach_handwerker_hvac_828_leads.csv`: Enriched DACH HVAC / Handwerker leads mapped to AI Ark taxonomy (`heating, ventilation, and air conditioning (hvac)`).
- `ai_ark_pipeline.py`: Pipeline CLI to:
  - Query AI Ark's 921-industry catalog (`industry_search`)
  - Query valid geographic location tokens (`location_search`)
  - Search companies (`company_search`)
  - Search decision-makers & people (`people_search`)
  - Real-time email finding and verification (`export_single`)
- `test_ai_ark_pipeline.py`: Unit tests.

## MCP Configuration

The AI Ark MCP server is configured in `~/.gemini/config/mcp_config.json`:
```json
"ai-ark": {
  "url": "https://api.ai-ark.com/v1/mcp"
}
```

When you have an AI Ark API token:
1. Export `AI_ARK_API_KEY="your-token"` or add it to `ai_ark/.env`
2. Or add headers to `mcp_config.json`:
   ```json
   "ai-ark": {
     "url": "https://api.ai-ark.com/v1/mcp",
     "headers": {
       "X-TOKEN": "your-token"
     }
   }
   ```

## CLI Usage

### 1. Test MCP Tool Connection & Catalog Lookup
```bash
python3 ai_ark_pipeline.py --mode test
```

### 2. Lookup Taxonomy (Industries & Locations)
```bash
python3 ai_ark_pipeline.py --mode lookup-industry --query "heating,ventilation"
python3 ai_ark_pipeline.py --mode lookup-location --location "Germany,Austria,Switzerland"
```

### 3. Re-generate AI Ark CSV Leads
```bash
python3 ai_ark_pipeline.py --mode convert
```

### 4. Search Companies in DACH Region
```bash
python3 ai_ark_pipeline.py --mode search-company --location "Germany"
```

### 5. Search People & Decision-Makers
```bash
python3 ai_ark_pipeline.py --mode search-people --location "Germany"
```
