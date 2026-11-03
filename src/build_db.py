"""Clean the raw IMF JSON files and load them into a SQLite database.

    python src/build_db.py

Output:
    data/processed/fiscal.db           SQLite database (tables: countries, indicators, observations)
    data/processed/observations.csv    the same tidy table as a CSV
"""
import json
import pathlib
import sqlite3

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

# Last year of actual outturns; later WEO years are IMF projections.
LAST_ACTUAL_YEAR = 2024

COUNTRIES = {
    "NGA": "Nigeria", "GHA": "Ghana", "KEN": "Kenya", "EGY": "Egypt",
    "ZAF": "South Africa", "AGO": "Angola", "CIV": "Côte d'Ivoire", "SEN": "Senegal",
}

INDICATORS = [
    # code, name, unit, source
    ("GGXWDG_NGDP", "General government gross debt", "% of GDP", "IMF WEO Oct 2026"),
    ("GGXCNL_NGDP", "General government overall balance", "% of GDP", "IMF WEO Oct 2026"),
    ("NGDP_RPCH", "Real GDP growth", "annual %", "IMF WEO Oct 2026"),
    ("PCPIPCH", "Inflation, average consumer prices", "annual %", "IMF WEO Oct 2026"),
    ("NGDPD", "GDP, current prices", "USD billions", "IMF WEO Oct 2026"),
    ("LP", "Population", "millions", "IMF WEO Oct 2026"),
    ("rev", "Government revenue", "% of GDP", "IMF Public Finances in Modern History, Dec 2025"),
    ("exp", "Government expenditure", "% of GDP", "IMF Public Finances in Modern History, Dec 2025"),
    ("ie", "Interest paid on public debt", "% of GDP", "IMF Public Finances in Modern History, Dec 2025"),
    ("pb", "Government primary balance", "% of GDP", "IMF Public Finances in Modern History, Dec 2025"),
]


def to_rows(series: dict, iso3: str, indicator: str) -> list[dict]:
    return [
        {"iso3": iso3, "indicator": indicator, "year": int(y), "value": float(v)}
        for y, v in series.items()
        if v is not None
    ]


def load_raw() -> pd.DataFrame:
    rows: list[dict] = []
    for fname in ["imf_weo_nga.json", "imf_fpp_nga.json"]:
        data = json.loads((RAW / fname).read_text())
        for ind, series in data.items():
            if ind.startswith("_"):
                continue
            rows += to_rows(series, "NGA", ind)

    peers = json.loads((RAW / "imf_peers.json").read_text())
    for ind, by_country in peers.items():
        if ind.startswith("_"):
            continue
        for iso3, series in by_country.items():
            if iso3 == "NGA":
                continue  # Nigeria already loaded at full length and precision
            rows += to_rows(series, iso3, ind)

    df = pd.DataFrame(rows)
    df["is_projection"] = (df["year"] > LAST_ACTUAL_YEAR).astype(int)
    return df


def validate(df: pd.DataFrame) -> None:
    dupes = df.duplicated(["iso3", "indicator", "year"]).sum()
    assert dupes == 0, f"{dupes} duplicate (country, indicator, year) rows"
    assert df["value"].notna().all(), "missing values slipped through"
    pct = df[df["indicator"].isin(["GGXWDG_NGDP", "rev", "exp", "ie"])]
    assert (pct["value"] >= 0).all(), "negative value in a ratio that cannot be negative"
    assert set(df["indicator"]) <= {c for c, *_ in INDICATORS}, "unknown indicator code"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_raw().sort_values(["iso3", "indicator", "year"]).reset_index(drop=True)
    validate(df)

    db_path = OUT / "fiscal.db"
    db_path.unlink(missing_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE countries (
                iso3 TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE indicators (
                code   TEXT PRIMARY KEY,
                name   TEXT NOT NULL,
                unit   TEXT NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE observations (
                iso3          TEXT    NOT NULL REFERENCES countries(iso3),
                indicator     TEXT    NOT NULL REFERENCES indicators(code),
                year          INTEGER NOT NULL,
                value         REAL    NOT NULL,
                is_projection INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (iso3, indicator, year)
            );
            """
        )
        con.executemany("INSERT INTO countries VALUES (?, ?)", COUNTRIES.items())
        con.executemany("INSERT INTO indicators VALUES (?, ?, ?, ?)", INDICATORS)
        df.to_sql("observations", con, if_exists="append", index=False)

    df.to_csv(OUT / "observations.csv", index=False)
    print(f"Loaded {len(df):,} observations into {db_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
