import base64
import csv
import json
import re
import time
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "audit" / "full_corpus" / "suspicious_examples_1000.csv"
OUT = ROOT / "audit" / "phase2_official_probe"
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"
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
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
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
    text = text.casefold()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^0-9a-zçğıöşü /.:,-]+", "", text)
    return text.strip()


def fetch_document(document_id):
    body = json.dumps(
        {
            "data": {"documentId": str(document_id)},
            "applicationName": "UyapMevzuat",
        }
    ).encode("utf-8")
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with INPUT.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # Purposefully probe the most suspicious rows first.
    sample = rows[:12]
    results = []

    for i, row in enumerate(sample):
        if i:
            time.sleep(CADENCE_SECONDS)
        corpus_text = row["text"]
        rec = {
            "document_id": row["document_id"],
            "court": row["court"],
            "esas_no": row["esas_no"],
            "karar_no": row["karar_no"],
            "karar_tarihi": row["karar_tarihi"],
            "corpus_chars": int(row["chars"]),
            "corpus_has_dava_turu": "davaturu" in corpus_text.casefold(),
            "corpus_has_ilgili_ceza_mah": "ilgilicezamahadi" in corpus_text.casefold(),
            "corpus_has_deneme": "deneme karar metni" in corpus_text.casefold(),
        }
        try:
            mime, official_text, raw_bytes = fetch_document(row["document_id"])
            c = normalize(corpus_text)
            o = normalize(official_text)
            rec.update(
                {
                    "status": "ok",
                    "official_mime_type": mime,
                    "official_raw_bytes": raw_bytes,
                    "official_chars": len(official_text),
                    "official_has_dava_turu": "davaturu" in official_text.casefold(),
                    "official_has_ilgili_ceza_mah": "ilgilicezamahadi" in official_text.casefold(),
                    "official_has_deneme": "deneme karar metni" in official_text.casefold(),
                    "court_present": normalize(row["court"]) in o,
                    "esas_present": normalize(row["esas_no"]) in o,
                    "karar_present": normalize(row["karar_no"]) in o,
                    "corpus_normalized_is_substring": bool(c) and c in o,
                    "official_normalized_is_substring": bool(o) and o in c,
                    "sequence_ratio": round(SequenceMatcher(None, c, o, autojunk=False).ratio(), 6),
                    "official_preview": re.sub(r"\s+", " ", official_text).strip()[:500],
                }
            )
        except HTTPError as e:
            rec.update({"status": "http_error", "error": f"HTTP {e.code}: {e.reason}"})
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            rec.update({"status": "error", "error": repr(e)})
        results.append(rec)
        print(json.dumps(rec, ensure_ascii=False))

    ok = [x for x in results if x["status"] == "ok"]
    summary = {
        "endpoint": ENDPOINT,
        "cadence_seconds": CADENCE_SECONDS,
        "sample_type": "first 12 structurally suspicious corpus rows",
        "requested": len(results),
        "official_retrieved": len(ok),
        "metadata_all_three_present": sum(
            bool(x.get("court_present") and x.get("esas_present") and x.get("karar_present"))
            for x in ok
        ),
        "official_preserves_dava_turu_placeholder": sum(bool(x.get("official_has_dava_turu")) for x in ok),
        "official_preserves_ilgili_ceza_mah_placeholder": sum(bool(x.get("official_has_ilgili_ceza_mah")) for x in ok),
        "official_preserves_deneme_placeholder": sum(bool(x.get("official_has_deneme")) for x in ok),
        "corpus_is_normalized_substring_of_official": sum(bool(x.get("corpus_normalized_is_substring")) for x in ok),
        "results": results,
    }
    (OUT / "probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT / "probe_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = sorted({k for r in results for k in r.keys() if k != "official_preview"}) + ["official_preview"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    md = [
        "# Phase 2 — Official Bedesten Probe",
        "",
        f"- Requested: **{len(results)}**",
        f"- Retrieved from official Bedesten: **{len(ok)}**",
        f"- Court + Esas + Karar all present: **{summary['metadata_all_three_present']} / {len(ok)}**",
        f"- Official source contains `davaTuru`: **{summary['official_preserves_dava_turu_placeholder']}**",
        f"- Official source contains `ilgiliCezaMahAdi`: **{summary['official_preserves_ilgili_ceza_mah_placeholder']}**",
        f"- Official source contains `deneme karar metni`: **{summary['official_preserves_deneme_placeholder']}**",
        f"- Corpus normalized text is substring of official text: **{summary['corpus_is_normalized_substring_of_official']} / {len(ok)}**",
    ]
    (OUT / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if len(ok) == 0:
        raise SystemExit("Official Bedesten probe retrieved zero documents")


if __name__ == "__main__":
    main()
