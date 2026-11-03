"""Download the raw IMF data used in this project.

Re-run this to refresh data/raw/ with the latest IMF releases:

    python src/fetch_data.py

Source: IMF DataMapper API (https://www.imf.org/external/datamapper/api/help)
"""
import json
import pathlib
import urllib.request
from datetime import date

API = "https://www.imf.org/external/datamapper/api/v1"
RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"

WEO_INDICATORS = ["GGXWDG_NGDP", "GGXCNL_NGDP", "NGDP_RPCH", "PCPIPCH", "NGDPD", "LP"]
FPP_INDICATORS = ["rev", "exp", "ie", "pb"]
PEERS = ["NGA", "GHA", "KEN", "EGY", "ZAF", "AGO", "CIV", "SEN"]


def get(indicator: str, countries: list[str]) -> dict:
    url = f"{API}/{indicator}/{'/'.join(countries)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        payload = json.load(resp)
    return payload.get("values", {}).get(indicator, {})


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    weo = {"_meta": {"source": "IMF WEO via DataMapper API", "retrieved": today}}
    for ind in WEO_INDICATORS:
        weo[ind] = get(ind, ["NGA"]).get("NGA", {})
    (RAW / "imf_weo_nga.json").write_text(json.dumps(weo, indent=2))

    fpp = {"_meta": {"source": "IMF Public Finances in Modern History via DataMapper API", "retrieved": today}}
    for ind in FPP_INDICATORS:
        fpp[ind] = get(ind, ["NGA"]).get("NGA", {})
    (RAW / "imf_fpp_nga.json").write_text(json.dumps(fpp, indent=2))

    peers = {"_meta": {"source": "IMF DataMapper API", "retrieved": today}}
    for ind in ["rev", "ie", "GGXWDG_NGDP"]:
        data = get(ind, PEERS)
        peers[ind] = {c: {y: v for y, v in data.get(c, {}).items() if 2010 <= int(y) <= 2024} for c in PEERS}
    (RAW / "imf_peers.json").write_text(json.dumps(peers, indent=2))

    print(f"Saved raw data to {RAW}")


if __name__ == "__main__":
    main()
