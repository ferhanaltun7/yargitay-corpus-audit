import argparse
from huggingface_hub import hf_hub_download, snapshot_download
from common import RAW, MANIFEST


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one-shard", action="store_true", help="Download only pinned shard 0000 (~203 MB)")
    args = ap.parse_args()

    repo_id = MANIFEST["dataset_id"]
    rev = MANIFEST["revision"]

    if args.one_shard:
        path = MANIFEST["pinned_example_shard"]["path"]
        out = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=rev,
            filename=path,
            local_dir=RAW,
        )
    else:
        out = snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=rev,
            allow_patterns=["yargitay/train/*.parquet"],
            local_dir=RAW,
        )
    print(out)


if __name__ == "__main__":
    main()
