from typing import Literal

SeoOpportunity = Literal["Low", "Medium", "High", "Very High"]


def compute_seo_opportunity(rank_position: int) -> SeoOpportunity:
    if rank_position <= 3:
        return "Low"
    if rank_position <= 10:
        return "Medium"
    if rank_position <= 20:
        return "High"
    return "Very High"
