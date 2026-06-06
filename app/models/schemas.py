from typing import Any

from pydantic import BaseModel, Field, field_validator

SCRAPABLE_FIELDS = frozenset(
    {"name", "phone", "website", "address", "rating", "reviews", "category"}
)
ALWAYS_INCLUDED_FIELDS = frozenset(
    {
        "keyword",
        "city",
        "search_query",
        "maps_url",
        "rank_position",
        "seo_opportunity",
    }
)


class ScrapeRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)
    cities: list[str] = Field(..., min_length=1)
    fields: list[str] = Field(default_factory=lambda: list(SCRAPABLE_FIELDS))
    max_results_per_search: int = Field(default=20, ge=1, le=100)
    need_website: bool | None = Field(
        default=None,
        description=(
            "Filter by website presence. "
            "true = only businesses with a website, "
            "false = only businesses without a website, "
            "omit = no filter"
        ),
    )

    @field_validator("keywords", "cities")
    @classmethod
    def strip_and_validate_non_empty(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty value is required")
        return cleaned

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, values: list[str]) -> list[str]:
        if not values:
            return list(SCRAPABLE_FIELDS)
        invalid = set(values) - SCRAPABLE_FIELDS
        if invalid:
            raise ValueError(
                f"Invalid fields: {sorted(invalid)}. "
                f"Allowed: {sorted(SCRAPABLE_FIELDS)}"
            )
        return values


class ScrapeResponse(BaseModel):
    results: list[dict[str, Any]]
    total: int
