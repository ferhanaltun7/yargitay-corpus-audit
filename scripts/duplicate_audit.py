import json
import duckdb
from common import shard_glob, AUDIT


def main():
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order=false")
    base = f"read_parquet('{shard_glob()}')"

    metrics = {
        "rows": con.execute(f"SELECT count(*) FROM {base}").fetchone()[0],
        "duplicate_id_excess_rows": con.execute(
            f"SELECT count(*) - count(DISTINCT id) FROM {base}"
        ).fetchone()[0],
        "duplicate_raw_sha256_excess_rows": con.execute(
            f"""SELECT count(*) - count(DISTINCT raw_sha256)
                FROM {base} WHERE raw_sha256 IS NOT NULL"""
        ).fetchone()[0],
        "metadata_duplicate_excess_rows": con.execute(
            f"""SELECT coalesce(sum(n - 1), 0)
                FROM (
                    SELECT source, court, esas_no, karar_no, count(*) AS n
                    FROM {base}
                    GROUP BY source, court, esas_no, karar_no
                    HAVING count(*) > 1
                )"""
        ).fetchone()[0],
    }

    (AUDIT / "duplicate_audit.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
