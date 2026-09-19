import duckdb
from common import shard_glob, AUDIT


def main():
    con = duckdb.connect()
    base = f"read_parquet('{shard_glob()}')"
    by_year = (AUDIT / "coverage_by_year.csv").as_posix()
    by_court = (AUDIT / "coverage_year_court.csv").as_posix()

    con.execute(f"""
      COPY (
        SELECT year, count(*) AS decisions
        FROM {base}
        GROUP BY year
        ORDER BY year
      ) TO '{by_year}' (HEADER, DELIMITER ',')
    """)

    con.execute(f"""
      COPY (
        SELECT
          year,
          court,
          count(*) AS decisions,
          min(text_len) AS min_text_len,
          approx_quantile(text_len, 0.5) AS median_text_len,
          max(text_len) AS max_text_len
        FROM {base}
        GROUP BY year, court
        ORDER BY year, court
      ) TO '{by_court}' (HEADER, DELIMITER ',')
    """)

    print(by_year)
    print(by_court)


if __name__ == "__main__":
    main()
