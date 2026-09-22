from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.python_library_registry import PYTHON_LIBRARY_REGISTRY, validate_library_registry  # noqa: E402


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _fetch_project(pip_name: str, timeout: float, attempts: int) -> tuple[str, str]:
    url = f"https://pypi.org/pypi/{quote(pip_name, safe='')}/json"
    last_error: Exception | None = None
    payload = None
    for _attempt in range(max(1, attempts)):
        request = Request(url, headers={"User-Agent": "Astra-Studio-PyPI-Audit/3.13", "Connection": "close"})
        try:
            with urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                payload = json.load(response)
            break
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            last_error = exc
    if payload is None:
        raise RuntimeError(str(last_error or "PyPI request failed"))
    published_name = str(payload.get("info", {}).get("name") or "")
    version = str(payload.get("info", {}).get("version") or "")
    if _canonical(published_name) != _canonical(pip_name):
        raise ValueError(f"PyPI canonical name is {published_name!r}")
    if not version:
        raise ValueError("PyPI latest version is missing")
    return pip_name, version


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only PyPI audit for Astra Studio's Python registry")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args()
    errors = validate_library_registry()
    projects: dict[str, list[str]] = {}
    for item in PYTHON_LIBRARY_REGISTRY:
        projects.setdefault(item["pip_name"], []).append(item["import_name"])

    verified = 0
    workers = max(1, min(16, args.workers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_project, name, args.timeout, args.attempts): name for name in projects}
        results: list[tuple[str, str]] = []
        for future in as_completed(futures):
            pip_name = futures[future]
            try:
                results.append(future.result())
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                errors.append(f"{pip_name}: {exc}")
        for pip_name, version in sorted(results, key=lambda value: value[0].casefold()):
            verified += 1
            print(f"OK {pip_name} {version} <- {', '.join(projects[pip_name])}")

    print(f"Verified {verified}/{len(projects)} PyPI projects for {len(PYTHON_LIBRARY_REGISTRY)} imports")
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
