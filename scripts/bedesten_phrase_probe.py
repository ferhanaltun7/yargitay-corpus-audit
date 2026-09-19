import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "bedesten_phrase_probe"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
CADENCE_SECONDS = 5.0

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "AdaletApplicationName": "UyapMevzuat",
    "Content-Type": "application/json; charset=utf-8",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 Chrome/137.0.0.0 Safari/537.36",
}

def query(year, phrase):
    body = json.dumps({
        "data": {
            "pageSize": 1,
            "pageNumber": 1,
            "itemTypeList": ["YARGITAYKARARI"],
            "phrase": phrase,
            "kararTarihiStart": f"{year}-01-01T00:00:00.000Z",
            "kararTarihiEnd": f"{year}-12-31T23:59:59.999Z",
            "sortFields": ["KARAR_TARIHI"],
            "sortDirection": "desc",
        },
        "applicationName": "UyapMevzuat",
        "paging": True,
    }).encode("utf-8")
    req = Request(ENDPOINT, data=body, headers=HEADERS, method="POST")
    with urlopen(req, timeout=90) as r:
        payload = json.load(r)
    data = payload.get("data")
    if not data:
        return {
            "status": "api_error",
            "metadata": payload.get("metadata"),
        }
    return {
        "status": "ok",
        "total": int(data.get("total", 0)),
        "returned": len(data.get("emsalKararList") or []),
    }

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Two distant modern years; enough to learn query semantics without
    # pretending this is a census.
    corpus_totals = {2016: 654309, 2025: 313478}
    phrases = [
        "karar",
        "esas",
        "mahkeme",
        "karar OR esas",
        "karar OR esas OR mahkeme",
        "dosya",
    ]

    results = []
    first = True
    for year in [2016, 2025]:
        for phrase in phrases:
            if not first:
                time.sleep(CADENCE_SECONDS)
            first = False
            rec = {
                "year": year,
                "phrase": phrase,
                "corpus_rows": corpus_totals[year],
            }
            try:
                rec.update(query(year, phrase))
            except HTTPError as e:
                rec.update({"status": "http_error", "error": f"HTTP {e.code}: {e.reason}"})
            except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
                rec.update({"status": "error", "error": repr(e)})
            if rec.get("status") == "ok":
                rec["corpus_over_query_total"] = (
                    rec["corpus_rows"] / rec["total"] if rec["total"] else None
                )
            results.append(rec)
            print(json.dumps(rec, ensure_ascii=False))

    summary = {
        "purpose": "learn Bedesten broad-query semantics; NOT a census",
        "endpoint": ENDPOINT,
        "cadence_seconds": CADENCE_SECONDS,
        "results": results,
    }
    (OUT / "phrase_probe.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok = [x for x in results if x.get("status") == "ok"]
    if not ok:
        raise SystemExit("No Bedesten phrase probe succeeded")

if __name__ == "__main__":
    main()
