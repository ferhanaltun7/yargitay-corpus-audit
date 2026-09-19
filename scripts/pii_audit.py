import json
from pathlib import Path

import duckdb

from common import RAW, AUDIT, MANIFEST


def main():
    out = AUDIT / "pii"
    out.mkdir(parents=True, exist_ok=True)

    glob = (RAW / "yargitay" / "train" / "*.parquet").as_posix()
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_pii_duckdb_temp'")
    src = f"read_parquet('{glob}')"

    # Deliberately conservative direct-identifier patterns.
    # Results are aggregate counts only; no matched personal data is written.
    patterns = {
        "iban_tr_unmasked": r"(?i)(^|[^A-Z0-9])TR[0-9]{24}([^A-Z0-9]|$)",
        "email_unmasked": r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}",
        "turkish_mobile_unmasked": r"(?i)(^|[^0-9])(?:\\+?90[ .-]?)?0?5[0-9]{2}[ .-]?[0-9]{3}[ .-]?[0-9]{2}[ .-]?[0-9]{2}([^0-9]|$)",
        "tckn_labeled_11_digits": r"(?i)(?:t\\.?c\\.?|tc|türkiye cumhuriyeti)[ ]*(?:kimlik)?[ ]*(?:no|numarası|numaralı|numara)?[^0-9]{0,12}[1-9][0-9]{10}",
        "card_labeled_13_19_digits": r"(?i)(?:kart|kredi kartı|banka kartı)[^0-9]{0,20}[0-9][0-9 .-]{11,25}[0-9]",
    }

    select_parts = [
        "count(*) AS rows",
        "count(*) FILTER (WHERE coalesce(masked_count, 0) > 0) AS rows_with_dataset_masking",
        "coalesce(sum(masked_count), 0) AS total_dataset_masked_count",
    ]
    for name, pat in patterns.items():
        escaped = pat.replace("'", "''")
        select_parts.append(
            f"count(*) FILTER (WHERE regexp_matches(text, '{escaped}')) AS {name}_rows"
        )

    masks = {
        "mask_tckn_rows": r"\\[TCKN\\]",
        "mask_iban_rows": r"\\[IBAN\\]",
        "mask_telefon_rows": r"\\[TELEFON\\]",
        "mask_eposta_rows": r"\\[EPOSTA\\]",
        "mask_kart_rows": r"\\[KART\\]",
    }
    for name, pat in masks.items():
        select_parts.append(
            f"count(*) FILTER (WHERE regexp_matches(text, '{pat}')) AS {name}"
        )

    query = "SELECT\n  " + ",\n  ".join(select_parts) + f"\nFROM {src}"
    row = con.execute(query).fetchdf().iloc[0].to_dict()

    # Year-level aggregate only; never emit matched values/snippets.
    year_flags = []
    for year, rows, masked_rows, iban, email, phone, tckn, card in con.execute(
        f"""
        SELECT
          year,
          count(*) AS rows,
          count(*) FILTER (WHERE coalesce(masked_count,0)>0) AS masked_rows,
          count(*) FILTER (WHERE regexp_matches(text, '{patterns["iban_tr_unmasked"].replace("'", "''")}')) AS iban,
          count(*) FILTER (WHERE regexp_matches(text, '{patterns["email_unmasked"].replace("'", "''")}')) AS email,
          count(*) FILTER (WHERE regexp_matches(text, '{patterns["turkish_mobile_unmasked"].replace("'", "''")}')) AS phone,
          count(*) FILTER (WHERE regexp_matches(text, '{patterns["tckn_labeled_11_digits"].replace("'", "''")}')) AS tckn,
          count(*) FILTER (WHERE regexp_matches(text, '{patterns["card_labeled_13_19_digits"].replace("'", "''")}')) AS card
        FROM {src}
        GROUP BY year
        ORDER BY year
        """
    ).fetchall():
        year_flags.append({
            "year": year,
            "rows": rows,
            "rows_with_dataset_masking": masked_rows,
            "iban_unmasked_rows": iban,
            "email_unmasked_rows": email,
            "phone_unmasked_rows": phone,
            "tckn_labeled_rows": tckn,
            "card_labeled_rows": card,
        })

    result = {
        "audit_version": "pii_direct_identifier_gate_v1",
        "source_revision": MANIFEST["revision"],
        "scope": "aggregate counts only; no matched PII values or snippets persisted",
        "caveat": (
            "Regex flags are screening signals, not a legal conclusion. "
            "Names, addresses, health data and contextual identifiers require a separate NER/manual audit."
        ),
        "totals": row,
        "by_year": year_flags,
    }

    (out / "pii_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    rows = int(row["rows"])
    def pct(v):
        return 100.0 * float(v) / rows if rows else 0.0

    md = [
        "# PII / KVKK Direct-Identifier Screening",
        "",
        f"- Rows scanned: **{rows:,}**",
        f"- Rows with dataset-provided masking: **{int(row['rows_with_dataset_masking']):,} ({pct(row['rows_with_dataset_masking']):.4f}%)**",
        f"- Dataset masked occurrences (sum masked_count): **{int(row['total_dataset_masked_count']):,}**",
        f"- Unmasked TR IBAN pattern rows: **{int(row['iban_tr_unmasked_rows']):,} ({pct(row['iban_tr_unmasked_rows']):.6f}%)**",
        f"- Unmasked email pattern rows: **{int(row['email_unmasked_rows']):,} ({pct(row['email_unmasked_rows']):.6f}%)**",
        f"- Unmasked Turkish mobile pattern rows: **{int(row['turkish_mobile_unmasked_rows']):,} ({pct(row['turkish_mobile_unmasked_rows']):.6f}%)**",
        f"- Labeled TCKN-like 11-digit rows: **{int(row['tckn_labeled_11_digits_rows']):,} ({pct(row['tckn_labeled_11_digits_rows']):.6f}%)**",
        f"- Labeled card-number-like rows: **{int(row['card_labeled_13_19_digits_rows']):,} ({pct(row['card_labeled_13_19_digits_rows']):.6f}%)**",
        "",
        "No matched identifier values or text snippets are committed to this public repository.",
        "",
        "This is a screening gate, not a complete KVKK determination. A separate NER/manual audit is still required for names, addresses, health data and context-dependent identifiers.",
    ]
    (out / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
