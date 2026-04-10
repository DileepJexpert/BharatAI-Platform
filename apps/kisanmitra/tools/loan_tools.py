"""Loan tools — EMI calculation, eligibility checking, loan comparison.

All loan rules are defined inline (no external JSON dependency).
Amounts are in Rupees.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Loan product catalog — covers major schemes for farmers and MSMEs
LOAN_CATALOG: list[dict[str, Any]] = [
    {
        "loan_code": "KCC",
        "loan_name": "Kisan Credit Card",
        "loan_name_hi": "किसान क्रेडिट कार्ड",
        "max_amount": 300000,
        "interest_rate_min": 4.0,
        "interest_rate_max": 7.0,
        "tenure_years_max": 5,
        "subsidy_percentage": 0,
        "collateral_required": False,
        "occupation": ["farmer", "sharecropper", "tenant"],
        "description": "Short-term crop loan at subsidised interest rates.",
    },
    {
        "loan_code": "MUDRA_SHISHU",
        "loan_name": "MUDRA Shishu",
        "loan_name_hi": "मुद्रा शिशु",
        "max_amount": 50000,
        "interest_rate_min": 10.0,
        "interest_rate_max": 12.0,
        "tenure_years_max": 5,
        "subsidy_percentage": 0,
        "collateral_required": False,
        "occupation": ["any"],
        "description": "Micro enterprise loan up to Rs.50,000.",
    },
    {
        "loan_code": "MUDRA_KISHORE",
        "loan_name": "MUDRA Kishore",
        "loan_name_hi": "मुद्रा किशोर",
        "max_amount": 500000,
        "interest_rate_min": 10.0,
        "interest_rate_max": 14.0,
        "tenure_years_max": 7,
        "subsidy_percentage": 0,
        "collateral_required": False,
        "occupation": ["any"],
        "description": "Small enterprise loan Rs.50,000 to Rs.5 lakh.",
    },
    {
        "loan_code": "MUDRA_TARUN",
        "loan_name": "MUDRA Tarun",
        "loan_name_hi": "मुद्रा तरुण",
        "max_amount": 1000000,
        "interest_rate_min": 11.0,
        "interest_rate_max": 14.0,
        "tenure_years_max": 7,
        "subsidy_percentage": 0,
        "collateral_required": False,
        "occupation": ["any"],
        "description": "Growing enterprise loan Rs.5 lakh to Rs.10 lakh.",
    },
    {
        "loan_code": "NABARD_DEDS",
        "loan_name": "NABARD Dairy Entrepreneurship Development",
        "loan_name_hi": "नाबार्ड डेयरी उद्यमिता",
        "max_amount": 700000,
        "interest_rate_min": 9.0,
        "interest_rate_max": 12.0,
        "tenure_years_max": 7,
        "subsidy_percentage": 25,
        "collateral_required": True,
        "occupation": ["farmer", "entrepreneur", "any"],
        "description": "25-33% subsidy for dairy farm setup.",
    },
    {
        "loan_code": "PMEGP",
        "loan_name": "PM Employment Generation Programme",
        "loan_name_hi": "पीएम रोजगार सृजन कार्यक्रम",
        "max_amount": 5000000,
        "interest_rate_min": 11.0,
        "interest_rate_max": 14.0,
        "tenure_years_max": 7,
        "subsidy_percentage": 25,
        "collateral_required": True,
        "occupation": ["any"],
        "description": "15-35% subsidy for new micro enterprises.",
    },
    {
        "loan_code": "STANDUP_INDIA",
        "loan_name": "Stand Up India",
        "loan_name_hi": "स्टैंड अप इंडिया",
        "max_amount": 10000000,
        "interest_rate_min": 10.0,
        "interest_rate_max": 14.0,
        "tenure_years_max": 7,
        "subsidy_percentage": 0,
        "collateral_required": True,
        "occupation": ["sc", "st", "women"],
        "categories": ["sc", "st"],
        "description": "Loans for SC/ST and women entrepreneurs.",
    },
]


def calculate_emi(
    principal: float, annual_rate: float, tenure_years: int,
) -> dict[str, Any]:
    """Standard EMI calculation.

    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    """
    if principal <= 0:
        return {"emi_monthly": 0, "total_interest": 0, "total_payment": 0}

    if annual_rate == 0:
        monthly = principal / (tenure_years * 12)
        return {
            "emi_monthly": round(monthly, 2),
            "total_interest": 0,
            "total_payment": round(principal, 2),
        }

    r = annual_rate / 100 / 12  # monthly rate
    n = tenure_years * 12  # total months
    emi = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total_payment = emi * n
    total_interest = total_payment - principal

    return {
        "emi_monthly": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_payment": round(total_payment, 2),
    }


def get_eligible_loans(
    loan_type: str | None = None,
    amount_needed: float | None = None,
    user_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Get eligible loans, optionally filtered by type and amount."""
    profile = user_profile or {}
    results = []

    for loan in LOAN_CATALOG:
        if loan_type and loan["loan_code"] != loan_type:
            continue

        eligible = True
        reasons: list[str] = []

        # Occupation check
        occupations = [o.lower() for o in loan.get("occupation", ["any"])]
        if "any" not in occupations and profile.get("occupation"):
            if profile["occupation"].lower() not in occupations:
                eligible = False
                reasons.append(f"Occupation '{profile['occupation']}' not eligible")

        # Category check (for Stand Up India etc.)
        if loan.get("categories") and profile.get("category"):
            cats = [c.lower() for c in loan["categories"]]
            if profile["category"].lower() not in cats:
                eligible = False
                reasons.append(f"Category '{profile['category']}' not eligible")

        # Amount check
        if amount_needed and amount_needed > loan["max_amount"]:
            # Still eligible, but note the max
            pass

        # Calculate EMI for max amount or requested amount
        principal = min(amount_needed, loan["max_amount"]) if amount_needed else loan["max_amount"]
        subsidy = principal * loan.get("subsidy_percentage", 0) / 100
        loan_after_subsidy = principal - subsidy
        emi = calculate_emi(
            loan_after_subsidy,
            loan["interest_rate_max"],
            loan["tenure_years_max"],
        )

        results.append({
            "loan_code": loan["loan_code"],
            "loan_name": loan["loan_name"],
            "loan_name_hi": loan["loan_name_hi"],
            "description": loan["description"],
            "eligible": eligible,
            "max_amount": loan["max_amount"],
            "interest_rate_range": f"{loan['interest_rate_min']}-{loan['interest_rate_max']}%",
            "subsidy_percentage": loan.get("subsidy_percentage", 0),
            "collateral_required": loan.get("collateral_required", False),
            "tenure_years": loan["tenure_years_max"],
            "emi_monthly": emi["emi_monthly"],
            "total_interest": emi["total_interest"],
            "reason_if_ineligible": "; ".join(reasons) if not eligible else None,
        })

    return results


def find_best_combination(
    amount_needed: float,
    user_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recommend best loan combination to cover needed amount."""
    eligible = [
        l for l in get_eligible_loans(user_profile=user_profile)
        if l["eligible"]
    ]

    # Sort: highest subsidy first, then lowest interest
    eligible.sort(
        key=lambda x: (-(x.get("subsidy_percentage") or 0), x.get("emi_monthly", 0)),
    )

    combination = []
    remaining = amount_needed
    total_subsidy = 0.0

    for loan in eligible:
        if remaining <= 0:
            break
        amount = min(remaining, loan["max_amount"])
        subsidy = amount * (loan.get("subsidy_percentage") or 0) / 100
        loan_amount = amount - subsidy

        rate_str = loan.get("interest_rate_range", "10-12%")
        max_rate = float(rate_str.split("-")[1].replace("%", ""))
        emi = calculate_emi(loan_amount, max_rate, loan["tenure_years"])

        combination.append({
            "loan_code": loan["loan_code"],
            "loan_name": loan["loan_name"],
            "amount": amount,
            "subsidy": round(subsidy, 2),
            "loan_after_subsidy": round(loan_amount, 2),
            "emi_monthly": emi["emi_monthly"],
        })
        remaining -= amount
        total_subsidy += subsidy

    return {
        "recommended_combination": combination,
        "total_funding": amount_needed,
        "total_subsidy": round(total_subsidy, 2),
        "gap": round(max(0, remaining), 2),
    }
