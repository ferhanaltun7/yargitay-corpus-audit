import json
from collections import Counter,defaultdict
from pathlib import Path
import duckdb
from transformers import pipeline

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"
OUT=ROOT/"audit"/"pii_ner_pilot"
MODEL_ID="ytu-ce-cosmos/modernbert-tr-pii-ner"
SCORE_THRESHOLDS=(0.80,0.90)

def windows(text):
    text=text or ""
    if len(text)<=1500:return [text]
    # Intro + one later window; avoids committing/processing full long decision in pilot.
    mid=max(0,(len(text)//2)-750)
    return [text[:1500],text[mid:mid+1500]]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    glob=(RAW/"yargitay"/"train"/"*.parquet").as_posix()
    con=duckdb.connect()
    con.execute("SET threads=4")
    rows=con.execute(f"""
      WITH ranked AS (
        SELECT id,year,text,
               row_number() OVER (
                 PARTITION BY CASE WHEN year BETWEEN 2016 AND 2026 THEN 1 ELSE 0 END
                 ORDER BY hash(id)
               ) rn,
               CASE WHEN year BETWEEN 2016 AND 2026 THEN 1 ELSE 0 END modern
        FROM read_parquet('{glob}')
      )
      SELECT id,year,text,modern
      FROM ranked
      WHERE (modern=1 AND rn<=200) OR (modern=0 AND rn<=50)
      ORDER BY modern DESC,year,hash(id)
    """).fetchall()

    ner=pipeline("token-classification",model=MODEL_ID,aggregation_strategy="first",device=-1)
    resolved=getattr(ner.model.config,"_commit_hash",None)
    labels=getattr(ner.model.config,"id2label",{})

    counts={str(t):Counter() for t in SCORE_THRESHOLDS}
    docs_any={str(t):set() for t in SCORE_THRESHOLDS}
    chunks=0
    errors=0

    for doc_id,year,text,modern in rows:
        for chunk in windows(text):
            if not chunk.strip():continue
            chunks+=1
            try:
                ents=ner(chunk,truncation=True,max_length=512)
            except Exception:
                errors+=1
                continue
            for e in ents:
                label=str(e.get("entity_group") or e.get("entity") or "UNKNOWN")
                score=float(e.get("score",0))
                for t in SCORE_THRESHOLDS:
                    if score>=t:
                        counts[str(t)][label]+=1
                        docs_any[str(t)].add(str(doc_id))

    result={
      "audit_version":"pii_ner_pilot_v1",
      "model_id":MODEL_ID,
      "resolved_model_commit":resolved,
      "model_labels":labels,
      "sample_documents":len(rows),
      "modern_documents":sum(int(r[3]) for r in rows),
      "historical_documents":sum(1-int(r[3]) for r in rows),
      "chunks_scanned":chunks,
      "inference_errors":errors,
      "thresholds":{
        str(t):{
          "documents_with_any_entity":len(docs_any[str(t)]),
          "entity_counts":dict(counts[str(t)].most_common())
        } for t in SCORE_THRESHOLDS
      },
      "raw_entity_values_committed":False,
      "scope_note":"Screening pilot only; model performance is not sufficient for a sole legal-safety determination."
    }
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    md=[
      "# Turkish PII-NER Pilot",
      "",
      f"- Model: `{MODEL_ID}`",
      f"- Resolved model commit: `{resolved}`",
      f"- Documents: **{len(rows)}**",
      f"- Chunks: **{chunks}**",
      f"- Inference errors: **{errors}**",
    ]
    for t in SCORE_THRESHOLDS:
        md.append(f"- Threshold {t:.2f}: documents with any detected entity **{len(docs_any[str(t)])}/{len(rows)}**")
    md += ["","No detected entity values or decision text are committed."]
    (OUT/"README.md").write_text("\n".join(md)+"\n",encoding="utf-8")

if __name__=="__main__":main()
