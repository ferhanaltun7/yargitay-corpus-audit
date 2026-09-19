from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
AUDIT = ROOT / "audit"
REPORTS = ROOT / "reports"
MANIFEST = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))

for p in (RAW, AUDIT, REPORTS):
    p.mkdir(parents=True, exist_ok=True)


def shard_glob():
    return (RAW / "yargitay" / "train" / "*.parquet").as_posix()
