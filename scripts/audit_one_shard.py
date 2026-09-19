import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

EXPECTED_SIZE = 203262814
EXPECTED_SHA256 = "bf99c9c1b9af7688bc1fc254c8130972a88f0fc66cc796a63f2d3c716f64680d"


def sha256_file(path: Path, chunk_size=8 * 1024 * 1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    path = Path(args.file)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    actual_size = path.stat().st_size
    actual_sha = sha256_file(path)

    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    columns = [f.name for f in schema]
    row_count = pf.metadata.num_rows
    row_groups = pf.metadata.num_row_groups

    con = duckdb.connect()
    src = f"read_parquet('{path.as_posix()}')"

    result = {
        "file": path.name,
        "expected_size_bytes": EXPECTED_SIZE,
        "actual_size_bytes": actual_size,
        "size_match": actual_size == EXPECTED_SIZE,
        "expected_sha256": EXPECTED_SHA256,
        "actual_sha256": actual_sha,
        "sha256_match": actual_sha == EXPECTED_SHA256,
        "parquet_rows": row_count,
        "row_groups": row_groups,
        "columns": columns,
        "schema": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema],
    }

    null_counts = {}
    for c in columns:
        qc = qident(c)
        null_counts[c] = con.execute(f"SELECT count(*) FILTER (WHERE {qc} IS NULL) FROM {src}").fetchone()[0]
    result["null_counts"] = null_counts

    if "text" in columns:
        result["text_stats"] = con.execute(
            f"""SELECT
                    count(*) FILTER (WHERE text IS NULL OR length(trim(text)) = 0) AS empty_text,
                    count(*) FILTER (WHERE length(text) < 100) AS lt_100_chars,
                    count(*) FILTER (WHERE length(text) < 300) AS lt_300_chars,
                    count(*) FILTER (WHERE length(text) < 500) AS lt_500_chars,
                    min(length(text)) AS min_chars,
                    approx_quantile(length(text), 0.01) AS p01_chars,
                    approx_quantile(length(text), 0.5) AS median_chars,
                    approx_quantile(length(text), 0.99) AS p99_chars,
                    max(length(text)) AS max_chars,
                    avg(length(text)) AS avg_chars
                FROM {src}"""
        ).fetchdf().iloc[0].to_dict()

        con.execute(
            f"""COPY (
                    SELECT id, document_id, court, esas_no, karar_no, karar_tarihi,
                           year, length(text) AS chars, text
                    FROM {src}
                    WHERE length(text) < 300
                    ORDER BY chars ASC, id
                    LIMIT 200
                ) TO '{(out / "short_text_examples.csv").as_posix()}'
                (HEADER, DELIMITER ',')"""
        )

        result["decision_marker_stats"] = con.execute(
            f"""SELECT
                    count(*) FILTER (WHERE lower(text) LIKE '%yargıtay%' OR lower(text) LIKE '%yargitay%') AS has_yargitay,
                    count(*) FILTER (WHERE lower(text) LIKE '%karar%') AS has_karar,
                    count(*) FILTER (WHERE lower(text) LIKE '%esas%') AS has_esas,
                    count(*) FILTER (WHERE lower(text) LIKE '%sonuç%' OR lower(text) LIKE '%sonuc%' OR lower(text) LIKE '%hüküm%' OR lower(text) LIKE '%hukum%') AS has_terminal_marker
                FROM {src}"""
        ).fetchdf().iloc[0].to_dict()

    for key in ("id", "document_id", "raw_sha256"):
        if key in columns:
            qk = qident(key)
            nonnull, distinct = con.execute(
                f"SELECT count({qk}), count(DISTINCT {qk}) FROM {src}"
            ).fetchone()
            result[f"{key}_uniqueness"] = {
                "nonnull": nonnull,
                "distinct": distinct,
                "duplicate_excess": nonnull - distinct,
            }

    metadata_keys = [k for k in ("source", "court", "esas_no", "karar_no") if k in columns]
    if len(metadata_keys) == 4:
        result["metadata_duplicate_excess"] = con.execute(
            f"""SELECT coalesce(sum(n - 1), 0)
                FROM (
                    SELECT source, court, esas_no, karar_no, count(*) AS n
                    FROM {src}
                    GROUP BY source, court, esas_no, karar_no
                    HAVING count(*) > 1
                )"""
        ).fetchone()[0]

    if "year" in columns:
        con.execute(
            f"""COPY (
                    SELECT year, count(*) AS decisions
                    FROM {src}
                    GROUP BY year
                    ORDER BY year
                ) TO '{(out / "coverage_by_year.csv").as_posix()}'
                (HEADER, DELIMITER ',')"""
        )
        result["year_min_max"] = con.execute(
            f"SELECT min(year), max(year) FROM {src}"
        ).fetchone()

    if "court" in columns:
        con.execute(
            f"""COPY (
                    SELECT court, count(*) AS decisions
                    FROM {src}
                    GROUP BY court
                    ORDER BY decisions DESC, court
                ) TO '{(out / "coverage_by_court.csv").as_posix()}'
                (HEADER, DELIMITER ',')"""
        )

    sample_cols = [c for c in ("id", "document_id", "source", "court", "esas_no", "karar_no", "karar_tarihi", "year", "text_len") if c in columns]
    if sample_cols:
        projection = ", ".join(qident(c) for c in sample_cols)
        con.execute(
            f"""COPY (
                    SELECT {projection}
                    FROM {src}
                    USING SAMPLE 100 ROWS (reservoir, 20260919)
                ) TO '{(out / "sample_100.csv").as_posix()}'
                (HEADER, DELIMITER ',')"""
        )

    (out / "phase0_phase1_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    md = [
        "# Phase 0–1 Audit — Yargıtay shard 0000",
        "",
        f"- File size match: **{result['size_match']}**",
        f"- SHA-256 match: **{result['sha256_match']}**",
        f"- Rows: **{row_count:,}**",
        f"- Row groups: **{row_groups}**",
        f"- Columns: **{len(columns)}**",
    ]
    if "text_stats" in result:
        ts = result["text_stats"]
        md += [
            f"- Empty text rows: **{int(ts['empty_text']):,}**",
            f"- Text <100 chars: **{int(ts['lt_100_chars']):,}**",
            f"- Text <300 chars: **{int(ts['lt_300_chars']):,}**",
            f"- Text <500 chars: **{int(ts['lt_500_chars']):,}**",
            f"- Median text chars: **{float(ts['median_chars']):,.0f}**",
            f"- Min / max text chars: **{int(ts['min_chars']):,} / {int(ts['max_chars']):,}**",
        ]
    for key in ("id", "document_id", "raw_sha256"):
        u = result.get(f"{key}_uniqueness")
        if u:
            md.append(f"- {key} duplicate excess: **{u['duplicate_excess']:,}**")
    if "metadata_duplicate_excess" in result:
        md.append(f"- Metadata-key duplicate excess: **{result['metadata_duplicate_excess']:,}**")

    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not result["size_match"] or not result["sha256_match"]:
        raise SystemExit("Pinned source verification failed")


if __name__ == "__main__":
    main()
