"""Scheme tools — RAG search and eligibility checking for government schemes.

Uses core/db/chroma_client.py for vector search with domain isolation.
Falls back gracefully when ChromaDB is unavailable.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Sample scheme data for in-memory fallback when ChromaDB is not available
SAMPLE_SCHEMES = [
    {
        "scheme_code": "PM_KISAN",
        "name_en": "PM-KISAN Samman Nidhi",
        "name_hi": "पीएम किसान सम्मान निधि",
        "description": "Direct income support of Rs.6000/year to farmer families.",
        "benefit_type": "direct_transfer",
        "subsidy_percentage": None,
        "max_amount": 6000,
        "sector": "agriculture",
        "eligibility": "All farmer families with cultivable land",
    },
    {
        "scheme_code": "PMFBY",
        "name_en": "PM Fasal Bima Yojana",
        "name_hi": "पीएम फसल बीमा योजना",
        "description": "Crop insurance at 2% premium for Kharif, 1.5% for Rabi crops.",
        "benefit_type": "insurance",
        "subsidy_percentage": 98,
        "max_amount": None,
        "sector": "agriculture",
        "eligibility": "All farmers growing notified crops",
    },
    {
        "scheme_code": "KCC",
        "name_en": "Kisan Credit Card",
        "name_hi": "किसान क्रेडिट कार्ड",
        "description": "Short-term credit at 4% interest (with subvention) for crop production.",
        "benefit_type": "credit",
        "subsidy_percentage": None,
        "max_amount": 300000,
        "sector": "agriculture",
        "eligibility": "All farmers, sharecroppers, tenant farmers",
    },
    {
        "scheme_code": "SMAM",
        "name_en": "Sub-Mission on Agricultural Mechanization",
        "name_hi": "कृषि मशीनीकरण उप-मिशन",
        "description": "50-80% subsidy on farm machinery for small/marginal farmers.",
        "benefit_type": "subsidy",
        "subsidy_percentage": 50,
        "max_amount": 500000,
        "sector": "agriculture",
        "eligibility": "Small and marginal farmers",
    },
    {
        "scheme_code": "PMEGP",
        "name_en": "PM Employment Generation Programme",
        "name_hi": "पीएम रोजगार सृजन कार्यक्रम",
        "description": "15-35% subsidy for new micro enterprises up to Rs.50 lakh.",
        "benefit_type": "subsidy",
        "subsidy_percentage": 25,
        "max_amount": 5000000,
        "sector": "msme",
        "eligibility": "Any individual above 18 for manufacturing/service projects",
    },
    {
        "scheme_code": "NABARD_DEDS",
        "name_en": "NABARD Dairy Entrepreneurship Development",
        "name_hi": "नाबार्ड डेयरी उद्यमिता विकास",
        "description": "25-33% subsidy for dairy farming setup, up to Rs.7 lakh.",
        "benefit_type": "subsidy",
        "subsidy_percentage": 25,
        "max_amount": 700000,
        "sector": "dairy",
        "eligibility": "Farmers, entrepreneurs for dairy projects",
    },
]


async def search_schemes_rag(
    query: str,
    app_id: str = "kisanmitra",
    sector: str | None = None,
    state: str | None = None,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """Search schemes via ChromaDB RAG, falling back to keyword match."""
    # Try ChromaDB first
    try:
        from core.db.chroma_client import ChromaClient
        client = ChromaClient()
        if client.is_connected:
            where = {}
            if sector:
                where["sector"] = sector
            results = client.search(
                app_id=app_id,
                collection="schemes",
                query=query,
                n_results=n_results,
                where=where if where else None,
            )
            if results:
                return results
    except Exception as exc:
        logger.debug("ChromaDB search failed, using fallback: %s", exc)

    # Fallback: simple keyword matching against sample data
    lower = query.lower()
    matches = []
    for scheme in SAMPLE_SCHEMES:
        score = 0
        searchable = f"{scheme['name_en']} {scheme['description']} {scheme.get('sector', '')}".lower()
        for word in lower.split():
            if word in searchable:
                score += 1
        if sector and scheme.get("sector") != sector:
            continue
        if score > 0:
            matches.append({**scheme, "_score": score})

    # If no keyword matches, return all (filtered by sector if given)
    if not matches:
        matches = [
            {**s, "_score": 0} for s in SAMPLE_SCHEMES
            if not sector or s.get("sector") == sector
        ]

    matches.sort(key=lambda x: x["_score"], reverse=True)
    return [{k: v for k, v in m.items() if k != "_score"} for m in matches[:n_results]]


def check_eligibility(
    user_profile: dict[str, Any],
    scheme: dict[str, Any],
) -> dict[str, Any]:
    """Check if a user profile matches scheme eligibility criteria.

    Simple rule engine — checks income, category, occupation, land.
    """
    matched = []
    failed = []

    criteria = scheme.get("eligibility_criteria", {})
    if not criteria:
        return {
            "eligible": True,
            "match_score": 1.0,
            "scheme_code": scheme.get("scheme_code", ""),
            "scheme_name": scheme.get("name_en", ""),
            "matched": ["general_eligibility"],
            "failed": [],
        }

    # Income check
    if criteria.get("income_max") and user_profile.get("income_annual"):
        if float(user_profile["income_annual"]) <= criteria["income_max"]:
            matched.append("income")
        else:
            failed.append(f"income exceeds max {criteria['income_max']}")

    # Category check
    if criteria.get("categories") and user_profile.get("category"):
        cats = [c.lower() for c in criteria["categories"]]
        if user_profile["category"].lower() in cats:
            matched.append("category")
        else:
            failed.append(f"category '{user_profile['category']}' not eligible")

    # Occupation check
    if criteria.get("occupation"):
        occupations = [o.lower() for o in criteria["occupation"]]
        if "any" in occupations:
            matched.append("occupation")
        elif user_profile.get("occupation", "").lower() in occupations:
            matched.append("occupation")
        else:
            failed.append("occupation not eligible")

    # Land check
    if criteria.get("land_max_acres") and user_profile.get("land_acres"):
        if float(user_profile["land_acres"]) <= criteria["land_max_acres"]:
            matched.append("land_size")
        else:
            failed.append("land exceeds maximum")

    eligible = len(failed) == 0
    total = max(len(matched) + len(failed), 1)

    return {
        "eligible": eligible,
        "match_score": round(len(matched) / total, 2),
        "scheme_code": scheme.get("scheme_code", ""),
        "scheme_name": scheme.get("name_en", ""),
        "matched": matched,
        "failed": failed,
    }
