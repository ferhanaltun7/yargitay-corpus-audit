from pathlib import Path
import hashlib
import json
from common import RAW, MANIFEST, AUDIT


def sha256_file(path: Path, chunk_size=8 * 1024 * 1024):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def main():
    item = MANIFEST["pinned_example_shard"]
    p = RAW / item["path"]
    result = {
        "revision": MANIFEST["revision"],
        "path": item["path"],
        "exists": p.exists(),
    }
    if p.exists():
        result["size_bytes"] = p.stat().st_size
        result["size_matches"] = result["size_bytes"] == item["size_bytes"]
        result["sha256"] = sha256_file(p)
        result["sha256_matches"] = result["sha256"] == item["lfs_sha256"]

    (AUDIT / "source_verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
