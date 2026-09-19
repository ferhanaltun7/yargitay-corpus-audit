import csv
import json
import math
import re
import sys
import time
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import base64

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "audit" / "full_corpus" / "verification_sample_1000.csv"
OUT = ROOT / "audit" / "phase2_stratified_100"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"
CADENCE_SECONDS = 3.6
csv.field_size_limit(min(sys.maxsize, 10_000_000))

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

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def text(self):
        return unescape("\n".join(self.parts))

def html_to_text(html):
    p = TextExtractor()
    p.feed(html)
    return p.text()

def normalize(text):
    text = text.casefold().replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^0-9a-zçğıöşü /.:,-]+", "", text)
    return text.strip()

def fetch_document(document_id):
    body = json.dumps({
        "data": {"documentId": str(document_id)},
        "applicationName": "UyapMevzuat",
    }).encode("utf-8")
    req = Request(ENDPOINT, data=body, headers=HEADERS, method="POST")
    with urlopen(req, timeout=90) as r:
        payload = json.load(r)
    data = payload.get("data") or {}
    mime = data.get("mimeType")
    content = data.get("content")
    if not content:
        raise ValueError("No content returned")
    raw = base64.b64decode(content)
    if mime == "text/html":
        text = html_to_text(raw.decode("utf-8", errors="replace"))
    elif mime and "text" in mime:
        text = raw.decode("utf-8", errors="replace")
    else:
        text = ""
    return mime, text, len(raw)

def evenly_pick(rows, n):
    if len(rows) <= n:
        return list(rows)
    if n == 1:
        return [rows[len(rows)//2]]
    idxs = [round(i * (len(rows)-1) / (n-1)) for i in range(n)]
    return [rows[i] for i in idxs]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with INPUT.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    by = {}
    for row in rows:
        by.setdefault(row["stratum"], []).append(row)

    sample = []
    sample += evenly_pick(by.get("modern_2016_2026", []), 70)
    sample += evenly_pick(by.get("mid_2006_2015", []), 20)
    sample += evenly_pick(by.get("old_pre_2006", []), 10)

    if len(sample) != 100:
        raise SystemExit(f"Expected 100 sampled rows, got {len(sample)}")

    results = []
    for i, row in enumerate(sample):
        if i:
            time.sleep(CADENCE_SECONDS)
        corpus_text = row["text"]
        rec = {
            "sample_index": i + 1,
            "stratum": row["stratum"],
            "court_group": row.get("court_group", ""),
            "document_id": row["document_id"],
            "court": row["court"],
            "esas_no": row["esas_no"],
            "karar_no": row["karar_no"],
            "karar_tarihi": row["karar_tarihi"],
            "year": int(row["year"]),
            "corpus_chars": len(corpus_text),
        }
        try:
            mime, official_text, raw_bytes = fetch_document(row["document_id"])
            c = normalize(corpus_text)
            o = normalize(official_text)
            ratio = SequenceMatcher(None, c, o, autojunk=False).ratio()
            min_len = min(len(c), len(o))
            max_len = max(len(c), len(o))
            rec.update({
                "status": "ok",
                "official_mime_type": mime,
                "official_raw_bytes": raw_bytes,
                "official_chars": len(official_text),
                "court_present": normalize(row["court"]) in o,
                "esas_present": normalize(row["esas_no"]) in o,
                "karar_present": normalize(row["karar_no"]) in o,
                "corpus_in_official": bool(c) and c in o,
                "official_in_corpus": bool(o) and o in c,
                "sequence_ratio": round(ratio, 6),
                "normalized_length_ratio": round(min_len / max_len, 6) if max_len else 1.0,
                "text_match_ge_0_98": ratio >= 0.98,
                "text_match_ge_0_95": ratio >= 0.95,
            })
        except HTTPError as e:
            rec.update({"status": "http_error", "error": f"HTTP {e.code}: {e.reason}"})
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            rec.update({"status": "error", "error": repr(e)})
        results.append(rec)
        print(json.dumps(rec, ensure_ascii=False))

    ok = [x for x in results if x["status"] == "ok"]
    metadata_ok = [x for x in ok if x.get("court_present") and x.get("esas_present") and x.get("karar_present")]
    sim98 = [x for x in ok if x.get("text_match_ge_0_98")]
    sim95 = [x for x in ok if x.get("text_match_ge_0_95")]

    ratios = sorted(float(x["sequence_ratio"]) for x in ok if "sequence_ratio" in x)
    def pctile(vals, p):
        if not vals:
            return None
        k = (len(vals)-1) * p
        lo, hi = math.floor(k), math.ceil(k)
        if lo == hi:
            return vals[lo]
        return vals[lo] * (hi-k) + vals[hi] * (k-lo)

    summary = {
        "endpoint": ENDPOINT,
        "cadence_seconds": CADENCE_SECONDS,
        "sample_type": "deterministic stratified 100 from verification_sample_1000",
        "allocation": {"modern_2016_2026": 70, "mid_2006_2015": 20, "old_pre_2006": 10},
        "requested": len(results),
        "official_retrieved": len(ok),
        "metadata_all_three_present": len(metadata_ok),
        "metadata_match_rate_over_retrieved": len(metadata_ok)/len(ok) if ok else None,
        "sequence_ratio_ge_0_98": len(sim98),
        "sequence_ratio_ge_0_95": len(sim95),
        "sequence_ratio_min": min(ratios) if ratios else None,
        "sequence_ratio_median": pctile(ratios, 0.5),
        "sequence_ratio_p05": pctile(ratios, 0.05),
        "sequence_ratio_p95": pctile(ratios, 0.95),
        "results": results,
    }

    (OUT / "probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT / "probe_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = sorted({k for r in results for k in r.keys()})
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    md = [
        "# Phase 2B — Stratified Official Bedesten Verification",
        "",
        f"- Requested: **{len(results)}**",
        f"- Retrieved: **{len(ok)}**",
        f"- Metadata court+esas+karar present: **{len(metadata_ok)}/{len(ok)}**",
        f"- Sequence ratio >= 0.98: **{len(sim98)}/{len(ok)}**",
        f"- Sequence ratio >= 0.95: **{len(sim95)}/{len(ok)}**",
        f"- Median sequence ratio: **{summary['sequence_ratio_median']}**",
        f"- P05 sequence ratio: **{summary['sequence_ratio_p05']}**",
        f"- Minimum sequence ratio: **{summary['sequence_ratio_min']}**",
    ]
    (OUT / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if len(ok) < 95:
        raise SystemExit(f"Official retrieval rate too low: {len(ok)}/100")

if __name__ == "__main__":
    main()
