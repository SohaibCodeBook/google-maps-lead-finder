import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import ScrapeRequest, ScrapeResponse
from app.services.orchestrator import ScrapeOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest) -> ScrapeResponse:
    orchestrator = ScrapeOrchestrator()
    try:
        results = await orchestrator.run(
            keywords=request.keywords,
            cities=request.cities,
            fields=request.fields,
            max_results_per_search=request.max_results_per_search,
            need_website=request.need_website,
        )
    except Exception as exc:
        logger.exception("Scrape request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ScrapeResponse(results=results, total=len(results))
