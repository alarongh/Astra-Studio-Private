from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.python_library_registry import (  # noqa: E402
    EXPLICIT_STDLIB_MODULES,
    LIBRARY_BUNDLES,
    PYTHON_LIBRARY_REGISTRY,
    validate_library_registry,
)


def main() -> int:
    errors = validate_library_registry()
    if errors:
        raise SystemExit("\n".join(errors))
    payload = {
        "libraries": PYTHON_LIBRARY_REGISTRY,
        "bundles": LIBRARY_BUNDLES,
        "stdlib_ignored_modules": sorted(EXPLICIT_STDLIB_MODULES),
    }
    target = ROOT / "data" / "python_libraries.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{target} · {len(PYTHON_LIBRARY_REGISTRY)} libraries · {len(LIBRARY_BUNDLES)} bundles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
