import pandas as pd
import pytest

from mcp.disaster_service import (
    DisasterDataService
)


@pytest.fixture
def sample_csv(tmp_path):

    df = pd.DataFrame([
        {
            "Disaster Type": "Earthquake",
            "Country": "Japan",
            "Year": 2020,
            "Total Deaths": 100
        },
        {
            "Disaster Type": "Flood",
            "Country": "India",
            "Year": 2021,
            "Total Deaths": 50
        },
        {
            "Disaster Type": "Earthquake",
            "Country": "India",
            "Year": 2020,
            "Total Deaths": 200
        }
    ])

    csv_path = (
        tmp_path / "disasters.csv"
    )

    df.to_csv(
        csv_path,
        index=False
    )

    return str(csv_path)


@pytest.fixture
def service(sample_csv):

    return DisasterDataService(
        csv_path=sample_csv
    )


# ============================================================
# Column normalization
# ============================================================

def test_column_normalization(
    service
):

    assert (
        "disaster_type"
        in service.df.columns
    )

    assert (
        "total_deaths"
        in service.df.columns
    )


# ============================================================
# Disaster type filtering
# ============================================================

def test_filter_by_disaster_type(
    service
):

    result = service.query(
        "Show earthquake disasters"
    )

    assert result["matches"] == 2

    assert all(
        r["disaster_type"] == "Earthquake"
        for r in result["results"]
    )


# ============================================================
# Country filtering
# ============================================================

def test_filter_by_country(
    service
):

    result = service.query(
        "Show disasters in India"
    )

    assert result["matches"] == 2

    assert all(
        r["country"] == "India"
        for r in result["results"]
    )


# ============================================================
# Year filtering
# ============================================================

def test_filter_by_year(
    service
):

    result = service.query(
        "Show disasters in 2021"
    )

    assert result["matches"] == 1

    assert (
        result["results"][0]["year"]
        == 2021
    )


# ============================================================
# Count aggregation
# ============================================================

def test_count_query(
    service
):

    result = service.query(
        "How many earthquake disasters?"
    )

    assert (
        result["count"] == 2
    )


# ============================================================
# Total deaths aggregation
# ============================================================

def test_total_deaths_query(
    service
):

    result = service.query(
        "Total deaths from earthquake"
    )

    assert (
        result["total_deaths"]
        == 300
    )


# ============================================================
# Combined filtering
# ============================================================

def test_combined_filters(
    service
):

    result = service.query(
        "Earthquake disasters in India in 2020"
    )

    assert (
        result["matches"]
        == 1
    )

    row = result["results"][0]

    assert (
        row["country"]
        == "India"
    )

    assert (
        row["year"]
        == 2020
    )

# ============================================================
# Default response shape
# ============================================================

def test_default_response_structure(
    service
):

    result = service.query(
        "Show disasters"
    )

    assert (
        "matches"
        in result
    )

    assert (
        "results"
        in result
    )

    assert (
        "query"
        in result
    )
