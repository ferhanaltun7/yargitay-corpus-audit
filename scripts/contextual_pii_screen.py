import json
from pathlib import Path
import duckdb
from common import RAW,AUDIT,MANIFEST

OUT=AUDIT/"contextual_pii"
PATTERNS={
  "party_role_label":r"(?i)\b(sanık|mağdur|müşteki|katılan|şüpheli|davacı|davalı|hükümlü|suça sürüklenen çocuk)\b",
  "address_signal":r"(?i)\b(adres|ikametg[aâ]h|mahallesi|mah\.|sokak|sok\.|cadde|cad\.)\b",
  "health_sensitive_signal":r"(?i)\b(hiv|aids|kanser|şizofren|bipolar|epilepsi|gebelik|hamile|psikiyatr|engelli|özürlü)\b",
  "minor_signal":r"(?i)\b(çocuk|küçük|reşit olmayan|suça sürüklenen çocuk)\b",
  "victim_signal":r"(?i)\b(mağdur|müşteki|katılan)\b",
  "name_like_after_role":r"(?i)\b(sanık|mağdur|müşteki|katılan|şüpheli|davacı|davalı)\s*[:\-]?\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,3}\b"
}

def esc(s):return s.replace("'","''")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    glob=(RAW/"yargitay"/"train"/"*.parquet").as_posix()
    con=duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_contextual_pii'")

    # Deterministic 50k sample, stratified by target-window vs historical.
    con.execute(f"""
      CREATE TEMP TABLE sample AS
      WITH ranked AS (
        SELECT text,year,id,
               row_number() OVER (
                 PARTITION BY CASE WHEN year BETWEEN 2016 AND 2026 THEN 1 ELSE 0 END
                 ORDER BY hash(id)
               ) rn,
               CASE WHEN year BETWEEN 2016 AND 2026 THEN 1 ELSE 0 END modern
        FROM read_parquet('{glob}')
      )
      SELECT text,year,id,modern
      FROM ranked
      WHERE (modern=1 AND rn<=40000) OR (modern=0 AND rn<=10000)
    """)
    rows=con.execute("SELECT count(*) FROM sample").fetchone()[0]
    res={"rows_sampled":rows,"modern_rows":con.execute("SELECT count(*) FROM sample WHERE modern=1").fetchone()[0]}
    counts={}
    for name,pat in PATTERNS.items():
        counts[name]=con.execute(
          f"SELECT count(*) FROM sample WHERE regexp_matches(text,'{esc(pat)}')"
        ).fetchone()[0]
    res["row_counts"]=counts
    res["rates"]={k:(v/rows if rows else 0) for k,v in counts.items()}

    result={
      "audit_version":"contextual_pii_screen_v1",
      "source_revision":MANIFEST["revision"],
      "sample_design":"deterministic 50k: 40k from 2016-2026 + 10k historical",
      "result":res,
      "raw_matches_committed":False,
      "interpretation":"Signals quantify contextual-PII exposure risk; regex hits are not adjudicated personal-data findings.",
      "next_gate":"NER/manual review sample required before broad public-facing indexing."
    }
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    md=["# Contextual PII Screening","",f"- Rows sampled: **{rows:,}**"]
    for k,v in counts.items():md.append(f"- {k}: **{v:,} ({100*v/rows:.3f}%)**")
    md += ["","No matched snippets or personal identifiers are committed.","This is a screening gate, not a legal classification."]
    (OUT/"README.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
