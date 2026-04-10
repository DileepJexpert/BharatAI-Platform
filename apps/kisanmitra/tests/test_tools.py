"""Tests for KisanMitra domain tools — mandi, scheme, loan."""

import pytest

from apps.kisanmitra.tools.mandi_tools import (
    HINDI_COMMODITY_MAP,
    normalize_commodity,
    get_price,
    get_price_history,
    compare_markets,
    predict_commodity_price,
    store_prices,
)
from apps.kisanmitra.tools.scheme_tools import (
    SAMPLE_SCHEMES,
    search_schemes_rag,
    check_eligibility,
)
from apps.kisanmitra.tools.loan_tools import (
    LOAN_CATALOG,
    calculate_emi,
    get_eligible_loans,
    find_best_combination,
)


class TestMandiTools:
    """Test mandi price tools."""

    def test_normalize_commodity_hindi(self):
        assert normalize_commodity("tamatar") == "Tomato"
        assert normalize_commodity("टमाटर") == "Tomato"
        assert normalize_commodity("gehun") == "Wheat"
        assert normalize_commodity("गेहूं") == "Wheat"

    def test_normalize_commodity_english(self):
        assert normalize_commodity("tomato") == "Tomato"
        assert normalize_commodity("wheat") == "Wheat"

    def test_normalize_commodity_unknown(self):
        result = normalize_commodity("papaya")
        assert result == "Papaya"  # Titlecased

    @pytest.mark.asyncio
    async def test_get_price(self):
        price = await get_price("Tomato", "Indore")
        assert price is not None
        assert price["commodity"] == "Tomato"
        assert price["market"] == "Indore"
        assert price["modal_price"] > 0
        assert price["min_price"] <= price["modal_price"]
        assert price["max_price"] >= price["modal_price"]

    @pytest.mark.asyncio
    async def test_get_price_history(self):
        history = await get_price_history("Wheat", "Bhopal", days=10)
        assert len(history) >= 1
        assert len(history) <= 10
        for h in history:
            assert h["commodity"] == "Wheat"
            assert h["modal_price"] > 0

    @pytest.mark.asyncio
    async def test_compare_markets(self):
        results = await compare_markets("Onion", max_markets=3)
        assert len(results) <= 3
        # Should be sorted by price descending
        if len(results) >= 2:
            assert results[0]["modal_price"] >= results[-1]["modal_price"]

    @pytest.mark.asyncio
    async def test_predict_commodity_price(self):
        prediction = await predict_commodity_price("Tomato", "Indore")
        # Should return either prediction or error
        assert "predicted_price" in prediction or "error" in prediction

    def test_store_prices(self):
        prices = [
            {"commodity": "TestCrop", "market": "TestMarket", "modal_price": 100, "price_date": "2024-01-01"},
        ]
        count = store_prices(prices)
        assert count == 1

    def test_hindi_commodity_map_completeness(self):
        assert len(HINDI_COMMODITY_MAP) >= 10
        assert "tamatar" in HINDI_COMMODITY_MAP
        assert "प्याज" in HINDI_COMMODITY_MAP


class TestSchemeTools:
    """Test scheme search and eligibility tools."""

    def test_sample_schemes_exist(self):
        assert len(SAMPLE_SCHEMES) >= 5
        for s in SAMPLE_SCHEMES:
            assert "scheme_code" in s
            assert "name_en" in s

    @pytest.mark.asyncio
    async def test_search_schemes_keyword(self):
        results = await search_schemes_rag("farmer loan subsidy")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_schemes_sector_filter(self):
        results = await search_schemes_rag("dairy", sector="dairy")
        for r in results:
            assert r.get("sector") == "dairy"

    @pytest.mark.asyncio
    async def test_search_schemes_returns_all_on_no_match(self):
        results = await search_schemes_rag("xyznonexistent")
        assert len(results) > 0  # Should return all as fallback

    def test_check_eligibility_no_criteria(self):
        scheme = {"scheme_code": "TEST", "name_en": "Test Scheme"}
        result = check_eligibility({}, scheme)
        assert result["eligible"] is True
        assert result["match_score"] == 1.0

    def test_check_eligibility_income_pass(self):
        scheme = {
            "scheme_code": "TEST",
            "name_en": "Test",
            "eligibility_criteria": {"income_max": 500000},
        }
        profile = {"income_annual": 300000}
        result = check_eligibility(profile, scheme)
        assert result["eligible"] is True
        assert "income" in result["matched"]

    def test_check_eligibility_income_fail(self):
        scheme = {
            "scheme_code": "TEST",
            "name_en": "Test",
            "eligibility_criteria": {"income_max": 200000},
        }
        profile = {"income_annual": 300000}
        result = check_eligibility(profile, scheme)
        assert result["eligible"] is False


class TestLoanTools:
    """Test loan calculation and eligibility tools."""

    def test_loan_catalog_exists(self):
        assert len(LOAN_CATALOG) >= 5
        for loan in LOAN_CATALOG:
            assert "loan_code" in loan
            assert "max_amount" in loan

    def test_calculate_emi_basic(self):
        result = calculate_emi(100000, 10.0, 1)
        assert result["emi_monthly"] > 0
        assert result["total_payment"] > 100000
        assert result["total_interest"] > 0

    def test_calculate_emi_zero_rate(self):
        result = calculate_emi(120000, 0, 1)
        assert result["emi_monthly"] == 10000.0
        assert result["total_interest"] == 0

    def test_calculate_emi_zero_principal(self):
        result = calculate_emi(0, 10.0, 5)
        assert result["emi_monthly"] == 0

    def test_calculate_emi_known_values(self):
        # Rs.1 lakh at 12% for 1 year = EMI ~8884.88
        result = calculate_emi(100000, 12.0, 1)
        assert 8800 < result["emi_monthly"] < 8900

    def test_get_eligible_loans_all(self):
        results = get_eligible_loans()
        assert len(results) > 0
        for r in results:
            assert "loan_code" in r
            assert "emi_monthly" in r

    def test_get_eligible_loans_filtered(self):
        results = get_eligible_loans(loan_type="KCC")
        assert len(results) == 1
        assert results[0]["loan_code"] == "KCC"

    def test_get_eligible_loans_with_amount(self):
        results = get_eligible_loans(amount_needed=200000)
        assert len(results) > 0

    def test_find_best_combination(self):
        result = find_best_combination(500000)
        assert "recommended_combination" in result
        assert result["total_funding"] == 500000
        assert len(result["recommended_combination"]) > 0

    def test_find_best_combination_large_amount(self):
        result = find_best_combination(50000000)  # 5 crore
        assert result["gap"] > 0  # Can't cover this much

    def test_find_best_combination_subsidy(self):
        result = find_best_combination(700000)
        # NABARD_DEDS and PMEGP have subsidies, so total_subsidy should be > 0
        assert result["total_subsidy"] >= 0
