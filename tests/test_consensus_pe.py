import pytest
from analytics.consensus_pe import extract_consensus_pe_data, format_currency_large
import pandas as pd


def test_format_currency_large():
    assert format_currency_large(1.11e12) == "$1.11T"
    assert format_currency_large(54.91e9) == "$54.91B"
    assert format_currency_large(8.95e9) == "$8.95B"
    assert format_currency_large(None) == "-"
    assert format_currency_large(float('nan')) == "-"
    assert format_currency_large(1500000) == "$1.50M"


def test_extract_consensus_pe_data_mocked():
    mock_info = {
        'shortName': 'Eli Lilly and Company',
        'longName': 'Eli Lilly and Company',
        'trailingEps': 24.21,
        'currentPrice': 1244.0,
        'epsCurrentYear': 36.73,
        'forwardEps': 47.33,
        'pegRatio': 1.61,
        'forwardPE': 26.28,
        'marketCap': 1.11e12,
        'totalDebt': 54.91e9,
        'totalCash': 8.95e9,
        'enterpriseValue': 1.15e12
    }

    data = extract_consensus_pe_data("LLY", info=mock_info, current_price=1244.0)
    assert data["is_valid"] is True
    assert data["ticker"] == "LLY"
    assert len(data["pe_rows"]) >= 3
    assert len(data["growth_rows"]) >= 2
    assert len(data["capital_structure"]) == 5

    # Check PE rows
    actual_row = data["pe_rows"][0]
    assert actual_row["is_actual"] is True
    assert abs(actual_row["pe"] - 51.38) < 0.2

    # Check Capital Structure
    cs = {item["item"]: item["value_str"] for item in data["capital_structure"]}
    assert cs["Market Cap"] == "$1.11T"
    assert cs["Total Debt"] == "$54.91B"
    assert cs["Cash"] == "$8.95B"
    assert cs["Other"] == "-"
    assert cs["Enterprise Value"] == "$1.15T"
