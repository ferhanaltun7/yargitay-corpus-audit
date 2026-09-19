import json
from pathlib import Path
import duckdb
from common import RAW, AUDIT, MANIFEST

PATTERNS = [
    ("IBAN", r"(?i)(^|[^A-Z0-9])TR[0-9]{24}([^A-Z0-9]|$)"),
    ("EPOSTA", r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"),
    ("TELEFON", r"(?i)(^|[^0-9])(?:\+?90[ .-]?)?0?5[0-9]{2}[ .-]?[0-9]{3}[ .-]?[0-9]{2}[ .-]?[0-9]{2}([^0-9]|$)"),
    ("TCKN", r"(?i)(?:t\.?c\.?|tc|türkiye cumhuriyeti)[ ]*(?:kimlik)?[ ]*(?:no|numarası|numaralı|numara)?[^0-9]{0,12}[1-9][0-9]{10}"),
    ("KART", r"(?i)(?:kart|kredi kartı|banka kartı)[^0-9]{0,20}[0-9][0-9 .-]{11,25}[0-9]"),
]

def esc(s):
    return s.replace("'", "''")

def main():
    out=AUDIT/"pii_sanitization"
    out.mkdir(parents=True,exist_ok=True)
    glob=(RAW/"yargitay"/"train"/"*.parquet").as_posix()
    con=duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='/tmp/yargitay_pii_sanitize'")

    expr="text"
    for label,pat in PATTERNS:
        expr=f"regexp_replace({expr}, '{esc(pat)}', '[{label}]', 'g')"

    residual_parts=[]
    before_parts=[]
    for label,pat in PATTERNS:
        alias=label.lower()
        before_parts.append(
            f"count(*) FILTER (WHERE regexp_matches(text, '{esc(pat)}')) AS before_{alias}"
        )
        residual_parts.append(
            f"count(*) FILTER (WHERE regexp_matches(sanitized, '{esc(pat)}')) AS residual_{alias}"
        )

    q=f"""
      WITH s AS (
        SELECT text, {expr} AS sanitized
        FROM read_parquet('{glob}')
      )
      SELECT
        count(*) AS rows,
        count(*) FILTER (WHERE text <> sanitized) AS rows_changed,
        {", ".join(before_parts)},
        {", ".join(residual_parts)}
      FROM s
    """
    row=con.execute(q).fetchdf().iloc[0].to_dict()
    result={
      "audit_version":"direct_identifier_sanitization_v1",
      "source_revision":MANIFEST["revision"],
      "raw_immutable":True,
      "method":"sequential regex masking; validation-only, no sanitized text persisted",
      "result":row,
      "remaining_scope":"Contextual PII (names, addresses, health/minor/victim/suspect identifiers) requires NER/manual policy."
    }
    (out/"sanitization_validation.json").write_text(
      json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8"
    )
    residual=sum(int(row[k]) for k in row if k.startswith("residual_"))
    md=[
      "# Direct-Identifier Sanitization Validation",
      "",
      f"- Rows scanned: **{int(row['rows']):,}**",
      f"- Rows changed by direct-identifier masking: **{int(row['rows_changed']):,}**",
      f"- Residual direct-pattern row-count sum after masking: **{residual:,}**",
      "",
      "RAW input is never overwritten. This validates only the direct-identifier layer.",
      "Contextual PII still requires a separate NER/manual audit and policy."
    ]
    (out/"README.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    if residual != 0:
        raise SystemExit(f"Residual direct-identifier patterns remain: {residual}")

if __name__=="__main__":
    main()
