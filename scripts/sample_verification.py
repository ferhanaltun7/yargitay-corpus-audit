import argparse
import duckdb
from common import shard_glob, AUDIT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()

    con = duckdb.connect()
    base = f"read_parquet('{shard_glob()}')"
    total = con.execute(f"SELECT count(*) FROM {base}").fetchone()[0]
    step = max(total // args.n, 1)
    out = (AUDIT / f"verification_sample_{args.n}.csv").as_posix()

    con.execute(f"""
      COPY (
        WITH ordered AS (
          SELECT
            *,
            row_number() OVER (
              ORDER BY year, court, coalesce(esas_no, ''), coalesce(karar_no, ''), id
            ) AS rn
          FROM {base}
        )
        SELECT
          id,
          document_id,
          court,
          esas_no,
          karar_no,
          karar_tarihi,
          year,
          text_len,
          raw_sha256,
          '' AS official_source_status,
          '' AS metadata_match,
          '' AS text_match,
          '' AS reviewer_note
        FROM ordered
        WHERE ((rn - 1) % {step}) = 0
        LIMIT {args.n}
      ) TO '{out}' (HEADER, DELIMITER ',')
    """)

    print(out)


if __name__ == "__main__":
    main()
