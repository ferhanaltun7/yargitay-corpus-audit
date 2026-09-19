import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "audit" / "cross_source_metadata"
MANIFEST = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cand_glob = (RAW / "yargitay" / "train" / "*.parquet").as_posix()
    ext_glob = (RAW / "external_muhammedturan" / "*.parquet").as_posix()

    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='5GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_cross_source_duckdb'")

    con.execute(f"""
      CREATE TEMP VIEW cand AS
      SELECT
        document_id,
        court,
        esas_no,
        karar_no,
        year,
        karar_tarihi
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
        try_cast(substr(karar_tarihi, 7, 4) AS INTEGER) AS decision_year
      FROM read_parquet('{ext_glob}')
    """)

    # Exact normalized metadata key. trim/lower only; no fuzzy matching.
    con.execute("""
      CREATE TEMP VIEW cand_key AS
      SELECT
        document_id,
        lower(trim(court)) AS court_n,
        trim(esas_no) AS esas_n,
        trim(karar_no) AS karar_n,
        year
      FROM cand
    """)
    con.execute("""
      CREATE TEMP VIEW ext_key AS
      SELECT
        document_id,
        lower(trim(daire)) AS court_n,
        trim(esas_no) AS esas_n,
        trim(karar_no) AS karar_n,
        decision_year
      FROM ext
    """)

    summary = {}

    summary["candidate_rows"] = con.execute("SELECT count(*) FROM cand").fetchone()[0]
    summary["external_rows"] = con.execute("SELECT count(*) FROM ext").fetchone()[0]
    summary["candidate_distinct_document_id"] = con.execute(
        "SELECT count(DISTINCT document_id) FROM cand"
    ).fetchone()[0]
    summary["external_distinct_document_id"] = con.execute(
        "SELECT count(DISTINCT document_id) FROM ext"
    ).fetchone()[0]

    summary["candidate_distinct_metadata_key"] = con.execute("""
      SELECT count(*) FROM (
        SELECT court_n, esas_n, karar_n FROM cand_key GROUP BY ALL
      )
    """).fetchone()[0]
    summary["external_distinct_metadata_key"] = con.execute("""
      SELECT count(*) FROM (
        SELECT court_n, esas_n, karar_n FROM ext_key GROUP BY ALL
      )
    """).fetchone()[0]
    summary["external_metadata_duplicate_excess"] = (
        summary["external_rows"] - summary["external_distinct_metadata_key"]
    )

    # Document-ID overlap. Candidate Yargitay IDs are numeric strings; TRY_CAST
    # keeps the audit robust if an unexpected non-numeric ID exists.
    summary["candidate_non_numeric_document_id"] = con.execute("""
      SELECT count(*) FROM cand WHERE try_cast(document_id AS BIGINT) IS NULL
    """).fetchone()[0]

    summary["exact_document_id_overlap"] = con.execute("""
      SELECT count(*)
      FROM ext e
      JOIN cand c
        ON e.document_id = try_cast(c.document_id AS BIGINT)
    """).fetchone()[0]

    # External rows absent by document_id: separate rows whose decision key is
    # already represented in candidate from rows whose decision key is absent.
    con.execute("""
      CREATE TEMP TABLE ext_not_doc AS
      SELECT e.*
      FROM ext_key e
      LEFT JOIN cand_key c
        ON e.document_id = try_cast(c.document_id AS BIGINT)
      WHERE c.document_id IS NULL
    """)

    summary["external_document_ids_not_in_candidate"] = con.execute(
        "SELECT count(*) FROM ext_not_doc"
    ).fetchone()[0]

    summary["external_missing_docid_but_metadata_key_present"] = con.execute("""
      SELECT count(*)
      FROM ext_not_doc e
      WHERE EXISTS (
        SELECT 1 FROM cand_key c
        WHERE c.court_n = e.court_n
          AND c.esas_n = e.esas_n
          AND c.karar_n = e.karar_n
      )
    """).fetchone()[0]

    summary["external_metadata_keys_absent_from_candidate"] = con.execute("""
      SELECT count(*)
      FROM ext_not_doc e
      WHERE NOT EXISTS (
        SELECT 1 FROM cand_key c
        WHERE c.court_n = e.court_n
          AND c.esas_n = e.esas_n
          AND c.karar_n = e.karar_n
      )
    """).fetchone()[0]

    # Reverse direction.
    summary["candidate_document_ids_not_in_external"] = con.execute("""
      SELECT count(*)
      FROM cand c
      LEFT JOIN ext e
        ON e.document_id = try_cast(c.document_id AS BIGINT)
      WHERE e.document_id IS NULL
    """).fetchone()[0]

    summary["candidate_metadata_keys_absent_from_external"] = con.execute("""
      SELECT count(*)
      FROM cand_key c
      WHERE NOT EXISTS (
        SELECT 1 FROM ext_key e
        WHERE e.court_n = c.court_n
          AND e.esas_n = c.esas_n
          AND e.karar_n = c.karar_n
      )
    """).fetchone()[0]

    # Year-level comparison for target window; external raw and distinct-key counts.
    rows = con.execute("""
      WITH ey AS (
        SELECT decision_year AS year,
               count(*) AS external_rows,
               count(DISTINCT (court_n, esas_n, karar_n)) AS external_unique_keys
        FROM ext_key
        WHERE decision_year BETWEEN 2016 AND 2026
        GROUP BY decision_year
      ),
      cy AS (
        SELECT year, count(*) AS candidate_rows
        FROM cand_key
        WHERE year BETWEEN 2016 AND 2026
        GROUP BY year
      )
      SELECT
        coalesce(cy.year, ey.year) AS year,
        coalesce(candidate_rows,0) AS candidate_rows,
        coalesce(external_rows,0) AS external_rows,
        coalesce(external_unique_keys,0) AS external_unique_keys
      FROM cy FULL OUTER JOIN ey USING (year)
      ORDER BY year
    """).fetchall()

    by_year = [
        {
          "year": r[0],
          "candidate_rows": r[1],
          "external_rows": r[2],
          "external_unique_metadata_keys": r[3],
          "candidate_minus_external_unique_keys": r[1]-r[3],
        }
        for r in rows
    ]

    result = {
      "audit_version": "cross_source_metadata_v1",
      "candidate": "hamzabagirsakci/turkish-court-decisions:yargitay",
      "candidate_revision": MANIFEST["revision"],
      "external": "muhammedturan/turk-ictihat-kararlari-fulltext",
      "method": "exact document_id + normalized exact (court, esas_no, karar_no) metadata keys",
      "summary": summary,
      "by_year_2016_2026": by_year,
      "limitations": [
        "External dataset is document-id oriented and may retain multiple IDs for the same legal decision.",
        "Exact court-name normalization is trim+lower only; aliases/renames are not fuzzy-matched.",
        "A metadata-key mismatch is a candidate for investigation, not automatically a missing legal decision."
      ],
    }

    (OUT / "cross_source_summary.json").write_text(
      json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    md = [
      "# Cross-source Yargıtay Metadata Audit",
      "",
      f"- Candidate rows: **{summary['candidate_rows']:,}**",
      f"- External metadata rows: **{summary['external_rows']:,}**",
      f"- Exact document_id overlap: **{summary['exact_document_id_overlap']:,}**",
      f"- External document_ids absent from candidate: **{summary['external_document_ids_not_in_candidate']:,}**",
      f"- Of those, same metadata key already present in candidate: **{summary['external_missing_docid_but_metadata_key_present']:,}**",
      f"- External rows whose exact metadata key is absent from candidate: **{summary['external_metadata_keys_absent_from_candidate']:,}**",
      f"- External metadata duplicate excess: **{summary['external_metadata_duplicate_excess']:,}**",
      f"- Candidate metadata keys absent from external: **{summary['candidate_metadata_keys_absent_from_external']:,}**",
      "",
      "This audit separates document-ID differences from decision-level metadata-key differences.",
    ]
    (OUT / "README.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__ == "__main__":
    main()
