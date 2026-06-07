import logging
from typing import Any

from app.services.filters import filter_record
from app.services.scraper import GoogleMapsScraper

logger = logging.getLogger(__name__)


class ScrapeOrchestrator:
    """Runs keyword × city combinations sequentially."""

    async def run(
        self,
        keywords: list[str],
        cities: list[str],
        fields: list[str],
        max_results_per_search: int,
        need_website: bool | None = None,
        min_rank: int | None = None,
    ) -> list[dict[str, Any]]:
        requested_fields = set(fields)
        all_results: list[dict[str, Any]] = []

        async with GoogleMapsScraper() as scraper:
            for keyword in keywords:
                for city in cities:
                    filter_label = (
                        "with website"
                        if need_website is True
                        else "without website"
                        if need_website is False
                        else "all"
                    )
                    logger.info(
                        "Scraping: %s in %s (%s)",
                        keyword,
                        city,
                        filter_label,
                    )
                    try:
                        batch = await scraper.scrape_search(
                            keyword=keyword,
                            city=city,
                            fields=requested_fields,
                            max_results=max_results_per_search,
                            need_website=need_website,
                            min_rank=min_rank,
                        )
                        filtered = [
                            filter_record(record, requested_fields) for record in batch
                        ]
                        all_results.extend(filtered)
                    except Exception as exc:
                        logger.error(
                            "Failed combination '%s in %s': %s",
                            keyword,
                            city,
                            exc,
                        )

        return all_results
