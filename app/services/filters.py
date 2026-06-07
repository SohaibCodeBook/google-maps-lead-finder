from typing import Any

from app.models.schemas import ALWAYS_INCLUDED_FIELDS


def output_fields_for_request(
    requested_fields: set[str], need_website: bool | None
) -> set[str]:
    """Include website in response when filtering by website presence."""
    if need_website is None:
        return requested_fields
    return requested_fields | {"website"}


def filter_record(record: dict[str, Any], requested_fields: set[str]) -> dict[str, Any]:
    """Return only requested fields plus keyword, city, and maps_url."""
    allowed = requested_fields | ALWAYS_INCLUDED_FIELDS
    return {key: record.get(key) for key in allowed}


def matches_website_filter(website: str | None, need_website: bool | None) -> bool:
    if need_website is None:
        return True
    has_website = bool(website and website.strip())
    return has_website if need_website else not has_website
