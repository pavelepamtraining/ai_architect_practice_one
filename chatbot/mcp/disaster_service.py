from typing import Dict, Any

import pandas as pd


class DisasterDataService:
    """Structured disaster retrieval using Pandas."""

    def __init__(self, csv_path: str):

        self.df = pd.read_csv(csv_path)

        # Normalize columns
        self.df.columns = (
            self.df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace("/", "_")
            .str.replace("-", "_")
        )

    def query(self, natural_language_query: str) -> Dict[str, Any]:

        query = natural_language_query.lower()

        df = self.df.copy()

        # ----------------------------------------------------
        # Disaster Type Filtering
        # ----------------------------------------------------

        if "disaster_type" in df.columns:

            disaster_types = (
                df["disaster_type"]
                .dropna()
                .astype(str)
                .str.lower()
                .unique()
            )

            for disaster_type in disaster_types:

                if disaster_type in query:

                    df = df[
                        df["disaster_type"]
                        .astype(str)
                        .str.lower()
                        .str.contains(disaster_type, na=False)
                    ]

        # ----------------------------------------------------
        # Country Filtering
        # ----------------------------------------------------

        country_columns = [
            "country",
            "country_name"
        ]

        for column in country_columns:

            if column in df.columns:

                countries = (
                    df[column]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                for country in countries:

                    if country.lower() in query:

                        df = df[
                            df[column]
                            .astype(str)
                            .str.lower() == country.lower()
                        ]

                        break

        # ----------------------------------------------------
        # Year Filtering
        # ----------------------------------------------------

        year_columns = [
            "year",
            "start_year"
        ]

        for column in year_columns:

            if column in df.columns:

                years = (
                    df[column]
                    .dropna()
                    .astype(int)
                    .astype(str)
                    .unique()
                )

                for year in years:

                    if year in query:

                        df = df[
                            df[column].astype(str) == year
                        ]

                        break

        # ----------------------------------------------------
        # Aggregation Queries
        # ----------------------------------------------------

        if "how many" in query or "count" in query:

            return {
                "count": int(len(df)),
                "query": natural_language_query
            }

        # ----------------------------------------------------
        # Total Deaths
        # ----------------------------------------------------

        if "total deaths" in query:

            death_columns = [
                "total_deaths",
                "deaths"
            ]

            for column in death_columns:

                if column in df.columns:

                    total_deaths = int(
                        pd.to_numeric(
                            df[column],
                            errors="coerce"
                        )
                        .fillna(0)
                        .sum()
                    )

                    return {
                        "total_deaths": total_deaths,
                        "query": natural_language_query
                    }

        # ----------------------------------------------------
        # Default Response
        # ----------------------------------------------------

        records = (
            df.head(5)
            .fillna("")
            .to_dict(orient="records")
        )

        return {
            "matches": int(len(df)),
            "results": records,
            "query": natural_language_query
        }
