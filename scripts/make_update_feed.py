from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.app_updates import parse_update_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an Astra Studio latest.json update manifest")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--notes-url", default="")
    parser.add_argument("--channel", choices=("stable", "test"), default="stable")
    parser.add_argument("--output", type=Path, default=Path("latest.json"))
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    if not artifact.is_file():
        parser.error(f"artifact does not exist: {artifact}")

    manifest = {
        "schema_version": 1,
        "version": args.version,
        "channel": args.channel,
        "published_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "download_url": args.download_url,
        "notes_url": args.notes_url,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "size": artifact.stat().st_size,
    }
    parse_update_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
