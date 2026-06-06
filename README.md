# Google Maps Scraper

Production-ready FastAPI + Playwright service for bulk Google Maps scraping.

## Features

- **Bulk scraping**: Every `keyword × city` combination is scraped independently
- **Dynamic fields**: Request only the fields you need
- **Resilient**: Failed listings are skipped; searches run sequentially with randomized delays
- **No Google Maps API**: UI scraping via Playwright only

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload
```

## API

### `POST /scrape`

**Request:**

```json
{
  "keywords": ["Dentists", "Roofing Contractors"],
  "cities": ["Houston", "Dallas", "Austin"],
  "fields": ["name", "phone", "website", "address", "rating"],
  "max_results_per_search": 20
}
```

**Response:**

```json
{
  "results": [
    {
      "keyword": "Dentists",
      "city": "Houston",
      "name": "ABC Dental Clinic",
      "phone": "+1 555 123 4567",
      "website": "https://abcdental.com",
      "address": "123 Main St, Houston, TX",
      "rating": 4.8,
      "maps_url": "https://maps.google.com/..."
    }
  ],
  "total": 120
}
```

### Field filtering

The `fields` array controls returned data. Allowed values:

`name`, `phone`, `website`, `address`, `rating`, `reviews`, `category`

These are **always** included regardless of `fields`:

- `keyword`
- `city`
- `maps_url`

Missing values are returned as `null`. Extra fields are never returned.

### `GET /health`

Health check endpoint.

## Docker

```bash
docker build -t maps-scraper .
docker run -p 8000:8000 maps-scraper
```

## Project Structure

```
app/
├── main.py              # FastAPI application
├── api/routes.py        # POST /scrape endpoint
├── core/config.py       # Settings
├── models/schemas.py    # Request/response models
└── services/
    ├── scraper.py       # Playwright Google Maps scraper
    └── orchestrator.py  # Bulk combination runner
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADLESS` | `true` | Run browser headless |
| `MIN_DELAY_SECONDS` | `1.0` | Min delay between actions |
| `MAX_DELAY_SECONDS` | `3.0` | Max delay between actions |
| `DEFAULT_MAX_RESULTS` | `20` | Default max results per search |

## Notes

- Scraping runs **sequentially** across combinations to reduce blocking risk
- Google Maps DOM selectors may change; update `app/services/scraper.py` if extraction breaks
- Respect Google Terms of Service and rate limits for your use case
