from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from core.language_completion import completion_query
from core.python_library_registry import (
    LIBRARY_BUNDLES,
    PYTHON_LIBRARY_REGISTRY,
    package_record,
    validate_library_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def _items(text: str):
    query = completion_query("C++", text, len(text))
    return {item.label: item for item in query.items} if query else {}


def test_cpp_completion_covers_cpp20_keywords_standard_symbols_and_includes():
    assert "co_await" in _items("co_a")
    assert "consteval" in _items("conste")
    vector = _items("int main() { std::vec")["vector"]
    assert vector.insert_text == "vector"
    assert vector.additional_edits[0].new_text == "#include <vector>\n\n"

    unqualified = _items("int main() { vec")["vector"]
    assert unqualified.insert_text == "std::vector"
    with_using = _items("using namespace std;\nint main() { vec")["vector"]
    assert with_using.insert_text == "vector"


def test_cpp_completion_does_not_duplicate_existing_include():
    item = _items("#include <vector>\nint main() { std::vec")["vector"]
    assert item.additional_edits == ()


def test_cpp_completion_infers_container_stream_and_smart_pointer_members():
    assert {"push_back()", "reserve()", "size()"}.issubset(
        _items("std::vector<int> values; values.")
    )
    assert {"contains()", "insert_or_assign()", "try_emplace()"}.issubset(
        _items("std::unordered_map<std::string, int> scores; scores.")
    )
    assert {"append()", "substr()", "starts_with()"}.issubset(
        _items("std::string name; name.")
    )
    assert {"get()", "release()", "reset()"}.issubset(
        _items("auto user = std::make_unique<User>(); user->")
    )
    assert {"flush()", "write()"}.issubset(_items("std::cout."))


def test_cpp_completion_is_suppressed_in_comments_and_strings():
    assert completion_query("C++", "// std::vec", len("// std::vec")) is None
    assert completion_query("C++", 'std::string s = "std::vec', len('std::string s = "std::vec')) is None


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is not installed")
def test_cpp23_representative_standard_library_program_compiles_and_runs(tmp_path: Path):
    source = tmp_path / "completion_gate.cpp"
    binary = tmp_path / ("completion_gate.exe" if os.name == "nt" else "completion_gate")
    source.write_text(
        """#include <algorithm>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <string>
#include <vector>

int main() {
    std::vector<int> values{3, 1, 2};
    std::sort(values.begin(), values.end());
    std::map<std::string, int> counts;
    counts.insert_or_assign("sum", std::accumulate(values.begin(), values.end(), 0));
    auto answer = std::make_unique<int>(counts.at("sum"));
    std::cout << "ASTRA_CPP_OK=" << *answer << '\\n';
    return *answer == 6 ? 0 : 2;
}
""",
        encoding="utf-8",
    )
    compile_result = subprocess.run(
        [shutil.which("g++"), "-std=c++23", "-Wall", "-Wextra", str(source), "-o", str(binary)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(binary)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert run_result.stdout.strip() == "ASTRA_CPP_OK=6"


def test_python_registry_quality_and_curated_growth():
    assert validate_library_registry() == []
    assert len(PYTHON_LIBRARY_REGISTRY) == 67
    assert sum(bool(item["safe"]) for item in PYTHON_LIBRARY_REGISTRY) == 61
    expected = {
        "httpx": "httpx",
        "pydantic": "pydantic",
        "pypdf": "pypdf",
        "xlsxwriter": "XlsxWriter",
        "pytest_cov": "pytest-cov",
        "bson": "pymongo",
        "openai": "openai",
    }
    for import_name, pip_name in expected.items():
        assert package_record(import_name)["pip_name"] == pip_name


def test_python_browser_automation_is_visible_but_never_auto_installed():
    for import_name in ("selenium", "playwright"):
        record = package_record(import_name)
        assert record is not None
        assert record["safe"] is False
        assert record["experimental"] is True
        assert record["warning"]
    for entries in LIBRARY_BUNDLES.values():
        assert "selenium" not in entries
        assert "playwright" not in entries


def test_python_registry_json_and_exporter_match_runtime_registry():
    payload = json.loads((ROOT / "data" / "python_libraries.json").read_text(encoding="utf-8"))
    assert payload["libraries"] == PYTHON_LIBRARY_REGISTRY
    assert payload["bundles"] == LIBRARY_BUNDLES
    exporter = (ROOT / "scripts" / "export_python_library_registry.py").read_text(encoding="utf-8")
    assert "validate_library_registry()" in exporter
    auditor = (ROOT / "scripts" / "audit_python_registry_pypi.py").read_text(encoding="utf-8")
    assert "https://pypi.org/pypi/" in auditor
    assert "urlopen(request" in auditor
