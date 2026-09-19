import csv
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "audit" / "full_corpus" / "coverage_by_year.csv"
OUT = ROOT / "audit" / "bedesten_year_totals"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
CADENCE_SECONDS = 3.6

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

def official_total(year, phrase=""):
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
        raise ValueError(f"No data in response: {payload}")
    return int(data.get("total", 0)), len(data.get("emsalKararList") or [])

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    corpus = {}
    with COVERAGE.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            corpus[int(row["year"])] = int(row["decisions"])

    results = []
    for i, year in enumerate(range(1997, 2027)):
        if i:
            time.sleep(CADENCE_SECONDS)
        rec = {"year": year, "corpus_rows": corpus.get(year, 0)}
        try:
            total, returned = official_total(year, phrase="")
            rec.update({
                "status": "ok",
                "query_phrase": "",
                "official_total": total,
                "returned_rows": returned,
                "difference_official_minus_corpus": total - rec["corpus_rows"],
                "corpus_over_official_ratio": (
                    rec["corpus_rows"] / total if total else None
                ),
            })
        except HTTPError as e:
            rec.update({"status": "http_error", "error": f"HTTP {e.code}: {e.reason}"})
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            rec.update({"status": "error", "error": repr(e)})
        results.append(rec)
        print(json.dumps(rec, ensure_ascii=False))

    ok = [x for x in results if x["status"] == "ok"]
    modern = [x for x in ok if 2016 <= x["year"] <= 2025]
    summary = {
        "endpoint": ENDPOINT,
        "court_type": "YARGITAYKARARI",
        "phrase": "",
        "date_range": "1997-2026 year-by-year",
        "cadence_seconds": CADENCE_SECONDS,
        "years_requested": 30,
        "years_retrieved": len(ok),
        "modern_2016_2025": {
            "years_retrieved": len(modern),
            "corpus_rows": sum(x["corpus_rows"] for x in modern),
            "official_total": sum(x["official_total"] for x in modern),
            "difference_official_minus_corpus": sum(
                x["official_total"] - x["corpus_rows"] for x in modern
            ),
        },
        "results": results,
    }
    m = summary["modern_2016_2025"]
    m["corpus_over_official_ratio"] = (
        m["corpus_rows"] / m["official_total"] if m["official_total"] else None
    )

    (OUT / "year_totals.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT / "year_totals.csv").open("w", encoding="utf-8", newline="") as f:
        fields = sorted({k for r in results for k in r.keys()})
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    md = [
        "# Bedesten Year-Total Census Probe",
        "",
        f"- Years requested: **30**",
        f"- Years retrieved: **{len(ok)}**",
        f"- Query phrase: **empty string**",
        f"- Court type: **YARGITAYKARARI**",
        "",
        "## 2016–2025 aggregate",
        "",
        f"- Corpus rows: **{m['corpus_rows']:,}**",
        f"- Official Bedesten total: **{m['official_total']:,}**",
        f"- Difference (official - corpus): **{m['difference_official_minus_corpus']:,}**",
        f"- Corpus / official: **{m['corpus_over_official_ratio']:.6f}**" if m["corpus_over_official_ratio"] is not None else "- Corpus / official: n/a",
        "",
        "This probe tests searchable Bedesten totals, not all possible unpublished/non-searchable decisions.",
    ]
    (OUT / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if len(ok) < 25:
        raise SystemExit(f"Too few year totals retrieved: {len(ok)}/30")

if __name__ == "__main__":
    main()
