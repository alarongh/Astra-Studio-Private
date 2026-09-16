from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import shutil
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class LspServerCandidate:
    command: str
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LspServerConfig:
    language: str
    language_id: str
    candidates: tuple[LspServerCandidate, ...] = ()
    transport: str = "stdio"
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int | None = None
    restart_enabled: bool = True
    max_restarts: int = 3
    restart_base_delay_ms: int = 500
    initialization_options: dict[str, Any] = field(default_factory=dict)
    notes: str = ""




@dataclass(frozen=True, slots=True)
class LspInstallPlan:
    language: str
    title: str
    kind: str
    packages: tuple[str, ...] = ()
    package_id: str = ""
    safe: bool = False
    notes: str = ""


SAFE_LSP_INSTALL_PLANS: dict[str, LspInstallPlan] = {
    "Python": LspInstallPlan(
        language="Python", title="BasedPyright", kind="python_tool",
        packages=("basedpyright",), safe=True,
        notes="Устанавливается в Python-окружение проекта; при наличии uv может использоваться uv tool.",
    ),
    "JavaScript": LspInstallPlan(
        language="JavaScript", title="TypeScript Language Server", kind="npm_global",
        packages=("typescript", "typescript-language-server"), safe=True,
        notes="Latest supported plan requires Node.js 22.22.2 or newer; Astra preflights the active Node runtime.",
    ),
    "TypeScript": LspInstallPlan(
        language="TypeScript", title="TypeScript Language Server", kind="npm_global",
        packages=("typescript", "typescript-language-server"), safe=True,
        notes="Latest supported plan requires Node.js 22.22.2 or newer; Astra preflights the active Node runtime.",
    ),
    "HTML": LspInstallPlan(
        language="HTML", title="VS Code HTML/CSS/JSON language servers", kind="npm_global",
        packages=("vscode-langservers-extracted",), safe=True,
    ),
    "CSS": LspInstallPlan(
        language="CSS", title="VS Code HTML/CSS/JSON language servers", kind="npm_global",
        packages=("vscode-langservers-extracted",), safe=True,
    ),
    "JSON": LspInstallPlan(
        language="JSON", title="VS Code HTML/CSS/JSON language servers", kind="npm_global",
        packages=("vscode-langservers-extracted",), safe=True,
    ),
    "YAML": LspInstallPlan(
        language="YAML", title="YAML Language Server", kind="npm_global",
        packages=("yaml-language-server",), safe=True,
    ),
    "Shell": LspInstallPlan(
        language="Shell", title="Bash Language Server", kind="npm_global",
        packages=("bash-language-server",), safe=True,
    ),
    "PHP": LspInstallPlan(
        language="PHP", title="Intelephense", kind="npm_global",
        packages=("intelephense",), safe=True,
    ),
    "C++": LspInstallPlan(
        language="C++", title="clangd (LLVM)", kind="winget",
        package_id="LLVM.LLVM", safe=True,
        notes="Установка LLVM через WinGet. clangd входит в LLVM toolchain.",
    ),
    "C#": LspInstallPlan(
        language="C#", title="csharp-ls", kind="dotnet_tool",
        packages=("csharp-ls",), safe=True,
        notes="Требуется .NET 10 SDK или новее; устанавливается как глобальный dotnet tool.",
    ),
    "GDScript": LspInstallPlan(
        language="GDScript", title="Godot built-in LSP", kind="external", safe=False,
        notes="Отдельная установка LSP не нужна: запусти Godot с открытым проектом.",
    ),
}


def install_plan_for_language(language: str) -> LspInstallPlan | None:
    return SAFE_LSP_INSTALL_PLANS.get(language)


@dataclass(frozen=True, slots=True)
class ResolvedLspServer:
    language: str
    language_id: str
    executable: str
    arguments: tuple[str, ...]
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int | None = None
    restart_enabled: bool = True
    max_restarts: int = 3
    restart_base_delay_ms: int = 500
    initialization_options: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


DEFAULT_LSP_SERVER_CONFIGS: dict[str, LspServerConfig] = {
    "Python": LspServerConfig(
        language="Python",
        language_id="python",
        candidates=(
            LspServerCandidate("basedpyright-langserver", ("--stdio",)),
            LspServerCandidate("pyright-langserver", ("--stdio",)),
        ),
        notes="Pyright-compatible stdio server.",
    ),
    "C++": LspServerConfig(
        language="C++",
        language_id="cpp",
        candidates=(LspServerCandidate("clangd"),),
        notes="clangd communicates over stdio by default.",
    ),
    "JavaScript": LspServerConfig(
        language="JavaScript",
        language_id="javascript",
        candidates=(LspServerCandidate("typescript-language-server", ("--stdio",)),),
    ),
    "TypeScript": LspServerConfig(
        language="TypeScript",
        language_id="typescript",
        candidates=(LspServerCandidate("typescript-language-server", ("--stdio",)),),
    ),
    "HTML": LspServerConfig(
        language="HTML",
        language_id="html",
        candidates=(LspServerCandidate("vscode-html-language-server", ("--stdio",)),),
    ),
    "CSS": LspServerConfig(
        language="CSS",
        language_id="css",
        candidates=(LspServerCandidate("vscode-css-language-server", ("--stdio",)),),
    ),
    "JSON": LspServerConfig(
        language="JSON",
        language_id="json",
        candidates=(LspServerCandidate("vscode-json-language-server", ("--stdio",)),),
    ),
    "YAML": LspServerConfig(
        language="YAML",
        language_id="yaml",
        candidates=(LspServerCandidate("yaml-language-server", ("--stdio",)),),
    ),
    "Luau": LspServerConfig(
        language="Luau",
        language_id="luau",
        candidates=(LspServerCandidate("luau-lsp", ("lsp",)),),
        notes="Luau LSP speaks standard LSP over stdin/stdout in `luau-lsp lsp` mode.",
    ),
    "PHP": LspServerConfig(
        language="PHP",
        language_id="php",
        candidates=(LspServerCandidate("intelephense", ("--stdio",)),),
    ),
    "C#": LspServerConfig(
        language="C#",
        language_id="csharp",
        candidates=(LspServerCandidate("csharp-ls"),),
    ),
    "Java": LspServerConfig(
        language="Java",
        language_id="java",
        candidates=(LspServerCandidate("jdtls"),),
        notes="Requires a working jdtls installation/wrapper on PATH.",
    ),
    "Markdown": LspServerConfig(
        language="Markdown",
        language_id="markdown",
        candidates=(LspServerCandidate("marksman", ("server",)),),
    ),
    "Shell": LspServerConfig(
        language="Shell",
        language_id="shellscript",
        candidates=(LspServerCandidate("bash-language-server", ("start",)),),
    ),
    "SQL": LspServerConfig(
        language="SQL",
        language_id="sql",
        candidates=(LspServerCandidate("sqls"),),
        notes="sqls requires database/project configuration for its richest features.",
    ),
    "Dockerfile": LspServerConfig(
        language="Dockerfile",
        language_id="dockerfile",
        candidates=(
            LspServerCandidate("docker-language-server", ("start", "--stdio")),
            LspServerCandidate("docker-langserver", ("--stdio",)),
        ),
    ),
    "TOML": LspServerConfig(
        language="TOML",
        language_id="toml",
        candidates=(LspServerCandidate("taplo", ("lsp", "stdio")),),
    ),
    "XML": LspServerConfig(
        language="XML",
        language_id="xml",
        candidates=(),
        enabled=False,
        restart_enabled=False,
        notes="No default standalone XML server is assumed; configure one in lsp_servers.json if needed.",
    ),
    # Godot owns the GDScript LSP process and exposes it over TCP (6005 by default).
    # Astra connects to this endpoint through the dedicated TCP transport instead
    # of trying to launch GDScript as a fake stdio language server.
    "GDScript": LspServerConfig(
        language="GDScript",
        language_id="gdscript",
        transport="external_tcp",
        candidates=(),
        host="127.0.0.1",
        port=6005,
        restart_enabled=False,
        notes="Godot must be running; its built-in LSP listens on TCP port 6005 by default.",
    ),
    # PowerShell Editor Services needs a dedicated launch/bootstrap sequence rather
    # than a stable one-command stdio entrypoint. Keep it explicit instead of guessing.
    "PowerShell": LspServerConfig(
        language="PowerShell",
        language_id="powershell",
        transport="external",
        candidates=(),
        enabled=False,
        restart_enabled=False,
        notes="PowerShell Editor Services bootstrap will be added after the generic stdio transport is stable.",
    ),
}


def _is_executable_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    if os.name == "nt":
        return path.suffix.lower() in {".exe", ".cmd", ".bat", ".com", ""}
    return os.access(path, os.X_OK)


def _candidate_names(command: str) -> tuple[str, ...]:
    if os.name != "nt" or Path(command).suffix:
        return (command,)
    return (command, f"{command}.exe", f"{command}.cmd", f"{command}.bat")


def project_tool_search_dirs(project_root: Path | str | None) -> list[Path]:
    if not project_root:
        return []
    root = Path(project_root)
    dirs = [root / "node_modules" / ".bin"]
    if os.name == "nt":
        dirs.extend([root / ".venv" / "Scripts", root / "venv" / "Scripts"])
    else:
        dirs.extend([root / ".venv" / "bin", root / "venv" / "bin"])
    return [path for path in dirs if path.exists() and path.is_dir()]


def find_server_executable(command: str, project_root: Path | str | None = None) -> str | None:
    raw = Path(command).expanduser()
    if raw.is_absolute() or raw.parent != Path("."):
        return str(raw) if _is_executable_file(raw) else None

    for folder in project_tool_search_dirs(project_root):
        for name in _candidate_names(command):
            path = folder / name
            if _is_executable_file(path):
                return str(path)

    found = shutil.which(command)
    return found or None


def _as_candidate(value: Any) -> LspServerCandidate | None:
    if isinstance(value, str) and value.strip():
        return LspServerCandidate(value.strip())
    if not isinstance(value, dict):
        return None
    command = str(value.get("command") or "").strip()
    if not command:
        return None
    arguments = value.get("arguments", value.get("args", []))
    if not isinstance(arguments, list):
        arguments = []
    return LspServerCandidate(command, tuple(str(item) for item in arguments))


def _merge_config(base: LspServerConfig, override: dict[str, Any]) -> LspServerConfig:
    values: dict[str, Any] = {}

    language_id = override.get("language_id")
    if isinstance(language_id, str) and language_id.strip():
        values["language_id"] = language_id.strip()

    transport = override.get("transport")
    if isinstance(transport, str) and transport in {"stdio", "external", "external_tcp"}:
        values["transport"] = transport

    for key in ("enabled", "restart_enabled"):
        if isinstance(override.get(key), bool):
            values[key] = override[key]

    host = override.get("host")
    if isinstance(host, str) and host.strip():
        values["host"] = host.strip()

    if "port" in override:
        raw_port = override.get("port")
        if raw_port is None:
            values["port"] = None
        elif isinstance(raw_port, int) and not isinstance(raw_port, bool) and 1 <= raw_port <= 65535:
            values["port"] = raw_port

    raw_restarts = override.get("max_restarts")
    if isinstance(raw_restarts, int) and not isinstance(raw_restarts, bool):
        values["max_restarts"] = max(0, raw_restarts)

    raw_delay = override.get("restart_base_delay_ms")
    if isinstance(raw_delay, int) and not isinstance(raw_delay, bool):
        values["restart_base_delay_ms"] = max(0, raw_delay)

    init_options = override.get("initialization_options")
    if isinstance(init_options, dict):
        values["initialization_options"] = dict(init_options)

    notes = override.get("notes")
    if isinstance(notes, str):
        values["notes"] = notes

    if "candidates" in override and isinstance(override["candidates"], list):
        candidates = tuple(candidate for item in override["candidates"] if (candidate := _as_candidate(item)))
        values["candidates"] = candidates

    return replace(base, **values)


class LspServerRegistry:
    """Default LSP server catalog plus optional per-user overrides.

    User overrides are configuration-only. Release 3.1 B3 exposes a separate
    curated safe-install catalog; registry overrides never execute commands.
    """

    def __init__(self, user_config_path: Path | str | None = None):
        self.user_config_path = Path(user_config_path) if user_config_path else None
        self.configs = dict(DEFAULT_LSP_SERVER_CONFIGS)
        self.reload()

    def reload(self):
        self.configs = dict(DEFAULT_LSP_SERVER_CONFIGS)
        path = self.user_config_path
        if not path or not path.exists() or not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        servers = payload.get("servers", payload) if isinstance(payload, dict) else {}
        if not isinstance(servers, dict):
            return
        for language, raw_override in servers.items():
            if not isinstance(raw_override, dict):
                continue
            base = self.configs.get(str(language))
            if base is None:
                language_id = str(raw_override.get("language_id") or str(language).lower())
                base = LspServerConfig(language=str(language), language_id=language_id)
            self.configs[str(language)] = _merge_config(base, raw_override)

    def config_for_language(self, language: str) -> LspServerConfig | None:
        return self.configs.get(language)

    def supported_languages(self) -> tuple[str, ...]:
        return tuple(sorted(self.configs))

    def resolve(self, language: str, project_root: Path | str | None = None) -> ResolvedLspServer | None:
        config = self.config_for_language(language)
        if config is None or not config.enabled:
            return None
        if config.transport == "external_tcp":
            if not config.host or config.port is None:
                return None
            return ResolvedLspServer(
                language=config.language,
                language_id=config.language_id,
                executable="",
                arguments=(),
                transport=config.transport,
                host=config.host,
                port=config.port,
                restart_enabled=config.restart_enabled,
                max_restarts=config.max_restarts,
                restart_base_delay_ms=config.restart_base_delay_ms,
                initialization_options=dict(config.initialization_options),
                notes=config.notes,
            )
        if config.transport != "stdio":
            return None
        for candidate in config.candidates:
            executable = find_server_executable(candidate.command, project_root)
            if not executable:
                continue
            return ResolvedLspServer(
                language=config.language,
                language_id=config.language_id,
                executable=executable,
                arguments=candidate.arguments,
                transport=config.transport,
                host=config.host,
                port=config.port,
                restart_enabled=config.restart_enabled,
                max_restarts=config.max_restarts,
                restart_base_delay_ms=config.restart_base_delay_ms,
                initialization_options=dict(config.initialization_options),
                notes=config.notes,
            )
        return None

    def availability(self, project_root: Path | str | None = None) -> dict[str, bool]:
        return {
            language: self.resolve(language, project_root) is not None
            for language, config in self.configs.items()
            if config.transport == "stdio" and config.enabled
        }

    def external_configs(self) -> Iterable[LspServerConfig]:
        return (
            config for config in self.configs.values()
            if config.enabled and config.transport != "stdio"
        )
