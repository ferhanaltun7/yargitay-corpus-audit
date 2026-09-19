import json
import duckdb
from common import shard_glob, AUDIT, MANIFEST


def main():
    con = duckdb.connect()
    g = shard_glob()
    query = f"""
    SELECT
      count(*) AS rows,
      count(*) FILTER (WHERE text IS NULL OR length(trim(text)) = 0) AS empty_text,
      count(*) FILTER (WHERE id IS NULL OR length(trim(id)) = 0) AS empty_id,
      count(*) FILTER (WHERE karar_tarihi IS NULL OR length(trim(karar_tarihi)) = 0) AS empty_date,
      count(*) FILTER (WHERE esas_no IS NULL OR length(trim(esas_no)) = 0) AS empty_esas,
      count(*) FILTER (WHERE karar_no IS NULL OR length(trim(karar_no)) = 0) AS empty_karar,
      min(text_len) AS min_text_len,
      max(text_len) AS max_text_len,
      avg(text_len) AS avg_text_len,
      min(year) AS min_year,
      max(year) AS max_year,
      count(*) FILTER (WHERE source <> 'yargitay') AS wrong_source
    FROM read_parquet('{g}')
    """
    row = con.execute(query).fetchdf().iloc[0].to_dict()
    row["expected_rows"] = MANIFEST["expected_rows"]
    row["row_count_matches_full_corpus"] = int(row["rows"]) == MANIFEST["expected_rows"]
    (AUDIT / "structural_audit.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(row, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
