import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import quote

from playwright.async_api import Browser, Page, async_playwright

from app.core.config import settings
from app.services.filters import matches_website_filter
from app.services.seo import compute_seo_opportunity

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class GoogleMapsScraper:
    """Playwright-based Google Maps UI scraper."""

    FEED_SELECTOR = 'div[role="feed"]'
    LISTING_LINK_SELECTOR = 'div[role="feed"] a.hfpxzc'
    END_OF_LIST_SELECTOR = 'span:has-text("You\'ve reached the end of the list")'
    CONSENT_BUTTON_SELECTORS = [
        'button:has-text("Accept all")',
        'button:has-text("Reject all")',
        "#L2AGLb",
        'form[action*="consent"] button',
    ]
    SEARCH_INPUT_SELECTORS = [
        "#searchboxinput",
        'input[name="q"]',
        'input[aria-label*="Search Google Maps"]',
        'input[aria-label*="Search"]',
    ]

    def __init__(self) -> None:
        self._browser: Browser | None = None

    async def __aenter__(self) -> "GoogleMapsScraper":
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=settings.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._playwright = playwright
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()

    async def scrape_search(
        self,
        keyword: str,
        city: str,
        fields: set[str],
        max_results: int,
        need_website: bool | None = None,
    ) -> list[dict[str, Any]]:
        if not self._browser:
            raise RuntimeError("Scraper must be used as an async context manager")

        search_query = f"{keyword} in {city}"
        extract_fields = fields | ({"website"} if need_website is not None else set())
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            user_agent=USER_AGENT,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()
        page.set_default_timeout(settings.page_timeout_ms)

        results: list[dict[str, Any]] = []

        try:
            await self._navigate_and_search(page, search_query)
            url_limit = (
                max_results
                if need_website is None
                else min(100, max(max_results * 5, max_results))
            )
            listing_entries = await self._collect_listing_urls(page, url_limit)

            for maps_url, rank_position in listing_entries:
                if len(results) >= max_results:
                    break
                try:
                    record = await self._scrape_listing(
                        page=page,
                        maps_url=maps_url,
                        keyword=keyword,
                        city=city,
                        fields=extract_fields,
                    )
                    if record and matches_website_filter(
                        record.get("website"), need_website
                    ):
                        record["rank_position"] = rank_position
                        record["seo_opportunity"] = compute_seo_opportunity(
                            rank_position
                        )
                        results.append(record)
                except Exception as exc:
                    logger.warning(
                        "Skipping listing rank %d for '%s': %s",
                        rank_position,
                        search_query,
                        exc,
                    )
                await self._random_delay()
        except Exception as exc:
            logger.error("Search failed for '%s': %s", search_query, exc)
        finally:
            await context.close()

        return results

    async def _navigate_and_search(self, page: Page, search_query: str) -> None:
        search_url = f"{settings.google_maps_url}/search/{quote(search_query)}"
        await page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=settings.navigation_timeout_ms,
        )
        await self._random_delay(0.5, 1.5)
        await self._dismiss_consent_if_present(page)

        try:
            await page.locator(self.FEED_SELECTOR).wait_for(
                state="visible",
                timeout=settings.page_timeout_ms,
            )
        except Exception:
            logger.info("Feed not found via direct URL, falling back to search input")
            await self._search_via_input(page, search_query)
            await page.locator(self.FEED_SELECTOR).wait_for(
                state="visible",
                timeout=settings.page_timeout_ms,
            )

        await self._random_delay()

    async def _dismiss_consent_if_present(self, page: Page) -> None:
        for selector in self.CONSENT_BUTTON_SELECTORS:
            button = page.locator(selector).first
            try:
                if await button.is_visible(timeout=2000):
                    await button.click()
                    await self._random_delay(0.5, 1.0)
                    return
            except Exception:
                continue

    async def _search_via_input(self, page: Page, search_query: str) -> None:
        if "google.com/maps" not in page.url:
            await page.goto(
                settings.google_maps_url,
                wait_until="domcontentloaded",
                timeout=settings.navigation_timeout_ms,
            )
            await self._dismiss_consent_if_present(page)

        search_input = await self._find_search_input(page)
        await search_input.fill(search_query)
        await search_input.press("Enter")

    async def _find_search_input(self, page: Page):
        for selector in self.SEARCH_INPUT_SELECTORS:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=5000)
                return locator
            except Exception:
                continue
        raise RuntimeError("Could not find Google Maps search input")

    async def _collect_listing_urls(
        self, page: Page, max_results: int
    ) -> list[tuple[str, int]]:
        ordered_urls: list[str] = []
        seen: set[str] = set()
        stale_rounds = 0

        while len(ordered_urls) < max_results and stale_rounds < 5:
            links = page.locator(self.LISTING_LINK_SELECTOR)
            count = await links.count()

            for i in range(count):
                if len(ordered_urls) >= max_results:
                    break
                href = await links.nth(i).get_attribute("href")
                if href and href not in seen:
                    seen.add(href)
                    ordered_urls.append(href)

            if len(ordered_urls) >= max_results:
                break

            end_visible = await page.locator(self.END_OF_LIST_SELECTOR).count()
            if end_visible > 0:
                break

            previous_count = len(ordered_urls)
            feed = page.locator(self.FEED_SELECTOR)
            await feed.evaluate("el => el.scrollTop = el.scrollHeight")
            await self._random_delay(1.0, 2.0)

            if len(ordered_urls) == previous_count:
                stale_rounds += 1
            else:
                stale_rounds = 0

        return [
            (url, rank)
            for rank, url in enumerate(ordered_urls[:max_results], start=1)
        ]

    async def _scrape_listing(
        self,
        page: Page,
        maps_url: str,
        keyword: str,
        city: str,
        fields: set[str],
    ) -> dict[str, Any] | None:
        await page.goto(
            maps_url,
            wait_until="domcontentloaded",
            timeout=settings.navigation_timeout_ms,
        )
        await self._random_delay(0.8, 1.5)

        await page.locator("h1").first.wait_for(
            state="visible",
            timeout=settings.page_timeout_ms,
        )

        raw: dict[str, Any] = {
            "keyword": keyword,
            "city": city,
            "maps_url": page.url,
        }

        if "name" in fields:
            raw["name"] = await self._extract_name(page)
        if "category" in fields:
            raw["category"] = await self._extract_category(page)
        if "phone" in fields:
            raw["phone"] = await self._extract_phone(page)
        if "website" in fields:
            raw["website"] = await self._extract_website(page)
        if "address" in fields:
            raw["address"] = await self._extract_address(page)
        if "rating" in fields:
            raw["rating"] = await self._extract_rating(page)
        if "reviews" in fields:
            raw["reviews"] = await self._extract_reviews(page)

        return raw

    async def _extract_name(self, page: Page) -> str | None:
        selectors = ["h1.DUwDvf", "h1", '[data-attrid="title"]']
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        return None

    async def _extract_category(self, page: Page) -> str | None:
        selectors = ["button.DkEaL", 'button[jsaction*="category"]']
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        return None

    async def _extract_phone(self, page: Page) -> str | None:
        selectors = [
            'button[data-item-id*="phone"]',
            'button[aria-label*="Phone"]',
            'button[data-tooltip="Copy phone number"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                aria = await locator.get_attribute("aria-label")
                if aria:
                    match = re.search(r"([\d\s\-+().]+)", aria)
                    if match:
                        return match.group(1).strip()
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        return None

    async def _extract_website(self, page: Page) -> str | None:
        selectors = [
            'a[data-item-id="authority"]',
            'a[aria-label*="Website"]',
            'a[data-tooltip="Open website"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                href = await locator.get_attribute("href")
                if href and href.startswith("http"):
                    return href
        return None

    async def _extract_address(self, page: Page) -> str | None:
        selectors = [
            'button[data-item-id="address"]',
            'button[aria-label*="Address"]',
            'button[data-tooltip="Copy address"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                aria = await locator.get_attribute("aria-label")
                if aria:
                    cleaned = aria.replace("Address:", "").strip()
                    if cleaned:
                        return cleaned
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        return None

    async def _extract_rating(self, page: Page) -> float | None:
        selectors = [
            'div.F7nice span[aria-hidden="true"]',
            'span[role="img"][aria-label*="stars"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                text = (await locator.inner_text()).strip().replace(",", ".")
                try:
                    return float(text)
                except ValueError:
                    aria = await locator.get_attribute("aria-label")
                    if aria:
                        match = re.search(r"([\d.]+)", aria)
                        if match:
                            return float(match.group(1))
        return None

    async def _extract_reviews(self, page: Page) -> int | None:
        selectors = [
            'div.F7nice span span span',
            'button[aria-label*="reviews"]',
            'span[aria-label*="reviews"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                text = (await locator.inner_text()).strip()
                match = re.search(r"([\d,]+)", text)
                if match:
                    return int(match.group(1).replace(",", ""))
                aria = await locator.get_attribute("aria-label")
                if aria:
                    match = re.search(r"([\d,]+)", aria)
                    if match:
                        return int(match.group(1).replace(",", ""))
        return None

    async def _random_delay(
        self,
        min_seconds: float | None = None,
        max_seconds: float | None = None,
    ) -> None:
        low = min_seconds if min_seconds is not None else settings.min_delay_seconds
        high = max_seconds if max_seconds is not None else settings.max_delay_seconds
        await asyncio.sleep(random.uniform(low, high))
