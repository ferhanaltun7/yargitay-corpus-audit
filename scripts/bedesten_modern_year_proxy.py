import csv
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "audit" / "full_corpus" / "coverage_by_year.csv"
OUT = ROOT / "audit" / "bedesten_modern_year_proxy"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments"
CADENCE_SECONDS = 5.0
PHRASE = "karar"

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

def official_total(year):
    body = json.dumps({
        "data": {
            "pageSize": 1,
            "pageNumber": 1,
            "itemTypeList": ["YARGITAYKARARI"],
            "phrase": PHRASE,
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
    return int(data.get("total", 0))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = {}
    with COVERAGE.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            corpus[int(row["year"])] = int(row["decisions"])

    results = []
    for i, year in enumerate(range(2016, 2027)):
        if i:
            time.sleep(CADENCE_SECONDS)
        rec = {"year": year, "corpus_rows": corpus[year], "phrase": PHRASE}
        try:
            total = official_total(year)
            rec.update({
                "status": "ok",
                "bedesten_query_total": total,
                "difference_bedesten_minus_corpus": total - rec["corpus_rows"],
                "corpus_over_bedesten_ratio": rec["corpus_rows"] / total if total else None,
            })
        except HTTPError as e:
            rec.update({"status":"http_error","error":f"HTTP {e.code}: {e.reason}"})
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            rec.update({"status":"error","error":repr(e)})
        results.append(rec)
        print(json.dumps(rec, ensure_ascii=False))

    ok=[x for x in results if x["status"]=="ok"]
    complete=[x for x in ok if x["year"]<=2025]
    corpus_sum=sum(x["corpus_rows"] for x in complete)
    bedesten_sum=sum(x["bedesten_query_total"] for x in complete)
    summary={
        "method":"Bedesten generic-term year-total proxy; not asserted as exhaustive census",
        "phrase":PHRASE,
        "years":"2016-2026",
        "years_retrieved":len(ok),
        "complete_years_2016_2025":{
            "corpus_rows":corpus_sum,
            "bedesten_query_total":bedesten_sum,
            "difference":bedesten_sum-corpus_sum,
            "ratio":corpus_sum/bedesten_sum if bedesten_sum else None,
        },
        "results":results,
    }
    (OUT/"proxy_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    with (OUT/"proxy_by_year.csv").open("w",encoding="utf-8",newline="") as f:
        fields=sorted({k for r in results for k in r})
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader(); w.writerows(results)

    if len(ok)<10:
        raise SystemExit(f"Too few successful year queries: {len(ok)}/11")

if __name__=="__main__":
    main()
