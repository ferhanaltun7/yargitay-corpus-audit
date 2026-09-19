import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "audit" / "cross_source_reconcile_v2"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cand_glob=(RAW/"yargitay"/"train"/"*.parquet").as_posix()
    ext_glob=(RAW/"external_muhammedturan"/"*.parquet").as_posix()

    con=duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='5GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_reconcile_v2'")

    # Numeric decision-key parsing removes whitespace/zero-padding differences.
    # Court canonicalization removes punctuation/spacing differences before fuzzy fallback.
    con.execute(f"""
      CREATE TEMP VIEW cand AS
      SELECT
        document_id,
        court,
        esas_no,
        karar_no,
        karar_tarihi,
        year,
        lower(trim(court)) AS court_exact,
        regexp_replace(lower(trim(court)), '[^0-9a-zçğıöşü]+', ' ', 'g') AS court_canon,
        try_cast(regexp_extract(esas_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 1) AS INTEGER) AS ey,
        try_cast(regexp_extract(esas_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 2) AS BIGINT) AS en,
        try_cast(regexp_extract(karar_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 1) AS INTEGER) AS ky,
        try_cast(regexp_extract(karar_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 2) AS BIGINT) AS kn
      FROM read_parquet('{cand_glob}')
    """)

    con.execute(f"""
      CREATE TEMP VIEW ext AS
      SELECT
        document_id,
        daire,
        esas_no,
        karar_no,
        karar_tarihi,
        lower(trim(daire)) AS court_exact,
        regexp_replace(lower(trim(daire)), '[^0-9a-zçğıöşü]+', ' ', 'g') AS court_canon,
        try_cast(regexp_extract(esas_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 1) AS INTEGER) AS ey,
        try_cast(regexp_extract(esas_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 2) AS BIGINT) AS en,
        try_cast(regexp_extract(karar_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 1) AS INTEGER) AS ky,
        try_cast(regexp_extract(karar_no, '([0-9]{{4}})\s*/\s*0*([0-9]+)', 2) AS BIGINT) AS kn
      FROM read_parquet('{ext_glob}')
    """)

    # External rows whose trim+lower exact metadata key is absent from candidate.
    con.execute("""
      CREATE TEMP TABLE ext_residual AS
      SELECT e.*
      FROM ext e
      WHERE NOT EXISTS (
        SELECT 1 FROM cand c
        WHERE c.court_exact=e.court_exact
          AND trim(c.esas_no)=trim(e.esas_no)
          AND trim(c.karar_no)=trim(e.karar_no)
      )
    """)

    summary={}
    summary["external_residual_exact_key"]=con.execute("SELECT count(*) FROM ext_residual").fetchone()[0]
    summary["residual_numeric_key_parseable"]=con.execute("""
      SELECT count(*) FROM ext_residual
      WHERE ey IS NOT NULL AND en IS NOT NULL AND ky IS NOT NULL AND kn IS NOT NULL
    """).fetchone()[0]

    con.execute("""
      CREATE TEMP TABLE numeric_matches AS
      SELECT
        e.document_id AS ext_document_id,
        e.daire AS ext_court,
        e.esas_no AS ext_esas_no,
        e.karar_no AS ext_karar_no,
        e.karar_tarihi AS ext_date,
        c.document_id AS cand_document_id,
        c.court AS cand_court,
        c.karar_tarihi AS cand_date,
        e.court_canon AS ext_court_canon,
        c.court_canon AS cand_court_canon,
        jaro_winkler_similarity(e.court_canon,c.court_canon) AS court_similarity
      FROM ext_residual e
      JOIN cand c
        ON e.ey=c.ey AND e.en=c.en AND e.ky=c.ky AND e.kn=c.kn
      WHERE e.ey IS NOT NULL AND e.en IS NOT NULL AND e.ky IS NOT NULL AND e.kn IS NOT NULL
    """)

    summary["residual_rows_with_any_same_numeric_decision_key"]=con.execute(
      "SELECT count(DISTINCT ext_document_id) FROM numeric_matches"
    ).fetchone()[0]
    summary["residual_rows_with_court_canon_exact"]=con.execute("""
      SELECT count(DISTINCT ext_document_id)
      FROM numeric_matches
      WHERE ext_court_canon=cand_court_canon
    """).fetchone()[0]
    summary["residual_rows_with_court_similarity_ge_095"]=con.execute("""
      SELECT count(DISTINCT ext_document_id)
      FROM numeric_matches
      WHERE court_similarity>=0.95
    """).fetchone()[0]
    summary["residual_rows_with_court_similarity_ge_090"]=con.execute("""
      SELECT count(DISTINCT ext_document_id)
      FROM numeric_matches
      WHERE court_similarity>=0.90
    """).fetchone()[0]
    summary["residual_rows_same_numeric_key_and_exact_date"]=con.execute("""
      SELECT count(DISTINCT ext_document_id)
      FROM numeric_matches
      WHERE ext_date=cand_date
    """).fetchone()[0]

    # External residuals still unmatched after numeric key + >=.90 court similarity.
    summary["external_residual_after_numeric_fuzzy_court"]=con.execute("""
      SELECT count(*)
      FROM ext_residual e
      WHERE NOT EXISTS (
        SELECT 1 FROM numeric_matches m
        WHERE m.ext_document_id=e.document_id
          AND m.court_similarity>=0.90
      )
    """).fetchone()[0]

    aliases=con.execute("""
      SELECT ext_court,cand_court,count(*) AS n,
             round(max(court_similarity),4) AS similarity
      FROM numeric_matches
      WHERE ext_court_canon<>cand_court_canon AND court_similarity>=0.90
      GROUP BY ext_court,cand_court
      ORDER BY n DESC, similarity DESC
      LIMIT 50
    """).fetchall()

    result={
      "audit_version":"cross_source_reconcile_v2",
      "method":"exact residual -> numeric (esas_year,esas_seq,karar_year,karar_seq) -> court canonical/fuzzy reconciliation",
      "summary":summary,
      "top_court_alias_pairs":[
        {"external_court":r[0],"candidate_court":r[1],"rows":r[2],"similarity":r[3]}
        for r in aliases
      ],
      "limitations":[
        "Fuzzy reconciliation is metadata-only and does not prove text identity.",
        "Same numeric decision key can theoretically collide across courts; court similarity/date are used as safeguards.",
        "Residual rows remain investigation candidates, not automatically proven missing decisions."
      ]
    }
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[
      "# Cross-source Reconciliation V2",
      "",
      f"- Exact-key residual external rows: **{summary['external_residual_exact_key']:,}**",
      f"- Same numeric decision key found: **{summary['residual_rows_with_any_same_numeric_decision_key']:,}**",
      f"- Court canonical exact: **{summary['residual_rows_with_court_canon_exact']:,}**",
      f"- Court similarity >=0.95: **{summary['residual_rows_with_court_similarity_ge_095']:,}**",
      f"- Court similarity >=0.90: **{summary['residual_rows_with_court_similarity_ge_090']:,}**",
      f"- Residual after numeric + fuzzy-court reconciliation: **{summary['external_residual_after_numeric_fuzzy_court']:,}**",
    ]
    (OUT/"README.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
