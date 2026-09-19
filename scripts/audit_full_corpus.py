import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from common import RAW, AUDIT, MANIFEST


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def main():
    out = AUDIT / "full_corpus"
    out.mkdir(parents=True, exist_ok=True)

    files = sorted((RAW / "yargitay" / "train").glob("*.parquet"))
    expected_files = MANIFEST["expected_shard_count"]
    if len(files) != expected_files:
        raise SystemExit(f"Expected {expected_files} parquet files, found {len(files)}")

    schemas = []
    parquet_rows = 0
    row_groups = 0
    file_rows = []
    for p in files:
        pf = pq.ParquetFile(p)
        parquet_rows += pf.metadata.num_rows
        row_groups += pf.metadata.num_row_groups
        schemas.append(str(pf.schema_arrow))
        file_rows.append({
            "file": p.name,
            "rows": pf.metadata.num_rows,
            "row_groups": pf.metadata.num_row_groups,
            "size_bytes": p.stat().st_size,
        })

    schema_identical = len(set(schemas)) == 1
    glob = (RAW / "yargitay" / "train" / "*.parquet").as_posix()

    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_duckdb_temp'")
    src = f"read_parquet('{glob}')"

    structural = con.execute(
        f"""
        SELECT
          count(*) AS rows,
          count(*) FILTER (WHERE id IS NULL OR length(trim(id))=0) AS empty_id,
          count(*) FILTER (WHERE source IS NULL OR length(trim(source))=0) AS empty_source,
          count(*) FILTER (WHERE document_id IS NULL OR length(trim(document_id))=0) AS empty_document_id,
          count(*) FILTER (WHERE court IS NULL OR length(trim(court))=0) AS empty_court,
          count(*) FILTER (WHERE esas_no IS NULL OR length(trim(esas_no))=0) AS empty_esas,
          count(*) FILTER (WHERE karar_no IS NULL OR length(trim(karar_no))=0) AS empty_karar,
          count(*) FILTER (WHERE karar_tarihi IS NULL OR length(trim(karar_tarihi))=0) AS empty_date,
          count(*) FILTER (WHERE year IS NULL) AS empty_year,
          count(*) FILTER (WHERE month IS NULL) AS empty_month,
          count(*) FILTER (WHERE text IS NULL OR length(trim(text))=0) AS empty_text,
          count(*) FILTER (WHERE text_len IS NULL) AS empty_text_len,
          count(*) FILTER (WHERE raw_sha256 IS NULL OR length(trim(raw_sha256))=0) AS empty_raw_sha256,
          count(*) FILTER (WHERE source <> 'yargitay') AS wrong_source,
          count(*) FILTER (WHERE text_len <> length(text)) AS text_len_mismatch,
          min(year) AS min_year,
          max(year) AS max_year,
          min(length(text)) AS min_chars,
          approx_quantile(length(text), 0.01) AS p01_chars,
          approx_quantile(length(text), 0.5) AS median_chars,
          approx_quantile(length(text), 0.99) AS p99_chars,
          max(length(text)) AS max_chars,
          avg(length(text)) AS avg_chars,
          count(*) FILTER (WHERE length(text) < 100) AS lt_100_chars,
          count(*) FILTER (WHERE length(text) < 300) AS lt_300_chars,
          count(*) FILTER (WHERE length(text) < 500) AS lt_500_chars
        FROM {src}
        """
    ).fetchdf().iloc[0].to_dict()

    duplicate = {
        "id_duplicate_excess": scalar(
            con, f"SELECT count(*) - count(DISTINCT id) FROM {src}"
        ),
        "document_id_duplicate_excess": scalar(
            con, f"SELECT count(*) - count(DISTINCT document_id) FROM {src}"
        ),
        "raw_sha256_duplicate_excess": scalar(
            con, f"SELECT count(*) - count(DISTINCT raw_sha256) FROM {src}"
        ),
        "metadata_duplicate_excess": scalar(
            con,
            f"""
            SELECT coalesce(sum(n - 1), 0)
            FROM (
              SELECT source, court, esas_no, karar_no, count(*) AS n
              FROM {src}
              GROUP BY source, court, esas_no, karar_no
              HAVING count(*) > 1
            )
            """,
        ),
    }

    quality = con.execute(
        f"""
        SELECT
          count(*) FILTER (WHERE lower(text) LIKE '%ilgilicezamahadi%') AS placeholder_ilgili_ceza_mah,
          count(*) FILTER (WHERE lower(text) LIKE '%davaturu%') AS placeholder_dava_turu,
          count(*) FILTER (WHERE lower(text) LIKE '%deneme karar metni%') AS placeholder_deneme,
          count(*) FILTER (
            WHERE lower(text) LIKE '%ilgilicezamahadi%'
               OR lower(text) LIKE '%davaturu%'
               OR lower(text) LIKE '%deneme karar metni%'
          ) AS any_known_placeholder,
          count(*) FILTER (WHERE court = '-' OR length(trim(court)) <= 1) AS suspicious_court,
          count(*) FILTER (WHERE lower(text) LIKE '%karar%') AS has_karar,
          count(*) FILTER (WHERE lower(text) LIKE '%esas%') AS has_esas,
          count(*) FILTER (
            WHERE lower(text) LIKE '%sonuç%'
               OR lower(text) LIKE '%sonuc%'
               OR lower(text) LIKE '%hüküm%'
               OR lower(text) LIKE '%hukum%'
          ) AS has_terminal_marker
        FROM {src}
        """
    ).fetchdf().iloc[0].to_dict()

    # Coverage outputs
    con.execute(
        f"""
        COPY (
          SELECT year, count(*) AS decisions,
                 count(*) FILTER (WHERE length(text) < 300) AS lt_300,
                 count(*) FILTER (
                   WHERE lower(text) LIKE '%ilgilicezamahadi%'
                      OR lower(text) LIKE '%davaturu%'
                      OR lower(text) LIKE '%deneme karar metni%'
                 ) AS known_placeholder
          FROM {src}
          GROUP BY year
          ORDER BY year
        ) TO '{(out / "coverage_by_year.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT court, count(*) AS decisions,
                 count(*) FILTER (WHERE length(text) < 300) AS lt_300
          FROM {src}
          GROUP BY court
          ORDER BY decisions DESC, court
        ) TO '{(out / "coverage_by_court.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT year, court, count(*) AS decisions,
                 approx_quantile(length(text), 0.5) AS median_chars,
                 count(*) FILTER (WHERE length(text) < 300) AS lt_300
          FROM {src}
          GROUP BY year, court
          ORDER BY year, court
        ) TO '{(out / "coverage_year_court.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT id, document_id, court, esas_no, karar_no, karar_tarihi,
                 year, length(text) AS chars, text
          FROM {src}
          WHERE length(text) < 300
             OR lower(text) LIKE '%ilgilicezamahadi%'
             OR lower(text) LIKE '%davaturu%'
             OR lower(text) LIKE '%deneme karar metni%'
             OR court = '-'
          ORDER BY
            CASE
              WHEN lower(text) LIKE '%deneme karar metni%' THEN 0
              WHEN lower(text) LIKE '%ilgilicezamahadi%' THEN 1
              WHEN lower(text) LIKE '%davaturu%' THEN 2
              WHEN length(text) < 100 THEN 3
              ELSE 4
            END,
            length(text),
            id
          LIMIT 1000
        ) TO '{(out / "suspicious_examples_1000.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )


    # Deterministic 1,000-row official-verification sample:
    # 770 rows from 2016-2026 (70/year), 190 from 2006-2015 (19/year),
    # plus 40 from pre-2006. hash(id) provides deterministic within-stratum selection.
    con.execute(
        f"""
        COPY (
          WITH ranked AS (
            SELECT *,
                   row_number() OVER (
                     PARTITION BY year
                     ORDER BY hash(id), id
                   ) AS year_rn
            FROM {src}
          ),
          old_ranked AS (
            SELECT *,
                   row_number() OVER (ORDER BY hash(id), id) AS old_rn
            FROM {src}
            WHERE year < 2006
          ),
          selected AS (
            SELECT id, document_id, source, court, esas_no, karar_no, karar_tarihi,
                   year, month, text_len, masked_count, raw_sha256, text,
                   'modern_2016_2026' AS stratum
            FROM ranked
            WHERE year BETWEEN 2016 AND 2026 AND year_rn <= 70

            UNION ALL

            SELECT id, document_id, source, court, esas_no, karar_no, karar_tarihi,
                   year, month, text_len, masked_count, raw_sha256, text,
                   'mid_2006_2015' AS stratum
            FROM ranked
            WHERE year BETWEEN 2006 AND 2015 AND year_rn <= 19

            UNION ALL

            SELECT id, document_id, source, court, esas_no, karar_no, karar_tarihi,
                   year, month, text_len, masked_count, raw_sha256, text,
                   'old_pre_2006' AS stratum
            FROM old_ranked
            WHERE old_rn <= 40
          )
          SELECT *,
                 CASE
                   WHEN lower(court) LIKE '%ceza%' THEN 'ceza'
                   WHEN lower(court) LIKE '%hukuk%' THEN 'hukuk'
                   ELSE 'other'
                 END AS court_group
          FROM selected
          ORDER BY stratum, year, hash(id), id
        ) TO '{(out / "verification_sample_1000.csv").as_posix()}'
        (HEADER, DELIMITER ',')
        """
    )

    result = {
        "source_manifest_revision": MANIFEST["revision"],
        "files_found": len(files),
        "files_expected": expected_files,
        "schema_identical_across_files": schema_identical,
        "parquet_metadata_rows": parquet_rows,
        "expected_rows": MANIFEST["expected_rows"],
        "row_count_match": parquet_rows == MANIFEST["expected_rows"],
        "row_groups": row_groups,
        "file_rows": file_rows,
        "structural": structural,
        "duplicates": duplicate,
        "quality_flags": quality,
    }

    (out / "full_corpus_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    rows = int(structural["rows"])
    def pct(v):
        return 100.0 * float(v) / rows if rows else 0.0

    md = [
        "# Full Yargıtay Structural Audit",
        "",
        f"- Shards: **{len(files)}/{expected_files}**",
        f"- Rows: **{rows:,}** / expected **{MANIFEST['expected_rows']:,}**",
        f"- Row count match: **{result['row_count_match']}**",
        f"- Schema identical across 17 shards: **{schema_identical}**",
        f"- Empty text: **{int(structural['empty_text']):,}**",
        f"- Text length mismatch: **{int(structural['text_len_mismatch']):,}**",
        f"- Text <100 chars: **{int(structural['lt_100_chars']):,} ({pct(structural['lt_100_chars']):.4f}%)**",
        f"- Text <300 chars: **{int(structural['lt_300_chars']):,} ({pct(structural['lt_300_chars']):.4f}%)**",
        f"- Text <500 chars: **{int(structural['lt_500_chars']):,} ({pct(structural['lt_500_chars']):.4f}%)**",
        f"- Known placeholder rows: **{int(quality['any_known_placeholder']):,} ({pct(quality['any_known_placeholder']):.4f}%)**",
        f"- ID duplicate excess: **{int(duplicate['id_duplicate_excess']):,}**",
        f"- document_id duplicate excess: **{int(duplicate['document_id_duplicate_excess']):,}**",
        f"- raw_sha256 duplicate excess: **{int(duplicate['raw_sha256_duplicate_excess']):,}**",
        f"- metadata duplicate excess: **{int(duplicate['metadata_duplicate_excess']):,}**",
        f"- Year range: **{int(structural['min_year'])}–{int(structural['max_year'])}**",
    ]
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not result["row_count_match"]:
        raise SystemExit("Full corpus row count does not match expected count")


if __name__ == "__main__":
    main()
