from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


CLEAN_MARKERS = {"", " ", "."}


@dataclass(slots=True)
class GitStatusEntry:
    path: str
    index_status: str = "."
    worktree_status: str = "."
    original_path: str = ""
    kind: str = "ordinary"
    submodule: str = "N..."

    @property
    def staged(self) -> bool:
        return self.index_status not in CLEAN_MARKERS and self.index_status != "?"

    @property
    def unstaged(self) -> bool:
        return self.worktree_status not in CLEAN_MARKERS and self.worktree_status != "?"

    @property
    def untracked(self) -> bool:
        return self.index_status == "?" or self.worktree_status == "?"

    @property
    def conflicted(self) -> bool:
        return self.kind == "unmerged" or "U" in {self.index_status, self.worktree_status}


@dataclass(slots=True)
class GitRepositoryState:
    root: Path
    branch: str = ""
    oid: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    detached: bool = False
    entries: tuple[GitStatusEntry, ...] = ()

    @property
    def dirty(self) -> bool:
        return bool(self.entries)

    @property
    def staged_count(self) -> int:
        return sum(1 for item in self.entries if item.staged)

    @property
    def unstaged_count(self) -> int:
        return sum(1 for item in self.entries if item.unstaged or item.untracked)

    @property
    def conflicted_count(self) -> int:
        return sum(1 for item in self.entries if item.conflicted)


@dataclass(slots=True)
class GitCommand:
    program: str
    arguments: tuple[str, ...]
    workdir: Path
    display_name: str


def git_executable() -> str | None:
    names = ("git.exe", "git") if os.name == "nt" else ("git",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def parse_repo_root(stdout: str) -> Path | None:
    value = (stdout or "").strip().splitlines()
    if not value:
        return None
    try:
        return Path(value[-1]).expanduser().resolve()
    except OSError:
        return Path(value[-1]).expanduser()


def parse_porcelain_v2_z(payload: str | bytes, root: Path) -> GitRepositoryState:
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="surrogateescape")
    else:
        text = str(payload or "")

    records = text.split("\0")
    branch = ""
    oid = ""
    upstream = ""
    ahead = 0
    behind = 0
    detached = False
    entries: list[GitStatusEntry] = []

    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith("# "):
            key, _, value = record[2:].partition(" ")
            if key == "branch.oid":
                oid = value.strip()
            elif key == "branch.head":
                branch = value.strip()
                detached = branch in {"(detached)", "(unknown)"}
            elif key == "branch.upstream":
                upstream = value.strip()
            elif key == "branch.ab":
                parts = value.split()
                for part in parts:
                    if part.startswith("+"):
                        try:
                            ahead = int(part[1:])
                        except ValueError:
                            ahead = 0
                    elif part.startswith("-"):
                        try:
                            behind = int(part[1:])
                        except ValueError:
                            behind = 0
            continue

        tag = record[0]
        if tag == "1":
            parts = record.split(" ", 8)
            if len(parts) < 9:
                continue
            _, xy, sub, *_meta, path = parts
            entries.append(GitStatusEntry(
                path=path,
                index_status=xy[0] if len(xy) > 0 else ".",
                worktree_status=xy[1] if len(xy) > 1 else ".",
                kind="ordinary",
                submodule=sub,
            ))
        elif tag == "2":
            parts = record.split(" ", 9)
            if len(parts) < 10:
                continue
            _, xy, sub, *_meta, path = parts
            original_path = records[index] if index < len(records) else ""
            if index < len(records):
                index += 1
            entries.append(GitStatusEntry(
                path=path,
                index_status=xy[0] if len(xy) > 0 else ".",
                worktree_status=xy[1] if len(xy) > 1 else ".",
                original_path=original_path,
                kind="rename_copy",
                submodule=sub,
            ))
        elif tag == "u":
            parts = record.split(" ", 10)
            if len(parts) < 11:
                continue
            _, xy, sub, *_meta, path = parts
            entries.append(GitStatusEntry(
                path=path,
                index_status=xy[0] if len(xy) > 0 else "U",
                worktree_status=xy[1] if len(xy) > 1 else "U",
                kind="unmerged",
                submodule=sub,
            ))
        elif tag == "?":
            path = record[2:] if record.startswith("? ") else record[1:].lstrip()
            entries.append(GitStatusEntry(path=path, index_status="?", worktree_status="?", kind="untracked"))
        elif tag == "!":
            # Ignored records are normally absent because Astra does not request
            # --ignored. Keep the parser tolerant if a custom Git config adds them.
            continue

    return GitRepositoryState(
        root=Path(root),
        branch=branch,
        oid=oid,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        detached=detached,
        entries=tuple(entries),
    )


def _require_git(program: str | None = None) -> str:
    resolved = program or git_executable()
    if not resolved:
        raise RuntimeError("Git CLI not found")
    return str(resolved)


def probe_repository_command(project_root: Path, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(project_root)
    return GitCommand(git, ("-C", str(root), "rev-parse", "--show-toplevel"), root, "Detect Git repository")


def status_command(repo_root: Path, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    return GitCommand(
        git,
        ("-C", str(root), "status", "--porcelain=v2", "-z", "--branch", "--untracked-files=all"),
        root,
        "Git status",
    )


def diff_command(
    repo_root: Path,
    path: str,
    staged: bool = False,
    program: str | None = None,
    original_path: str = "",
) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    args = ["-C", str(root), "diff", "--no-ext-diff", "--no-color", "--unified=3"]
    if staged:
        args.append("--cached")
    args.append("--")
    if original_path:
        args.append(str(original_path))
    args.append(str(path))
    return GitCommand(git, tuple(args), root, "Git staged diff" if staged else "Git working diff")


def stage_command(repo_root: Path, path: str | None = None, all_files: bool = False, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    if all_files:
        args = ("-C", str(root), "add", "-A")
        label = "Stage all changes"
    elif path:
        args = ("-C", str(root), "add", "--", str(path))
        label = f"Stage {path}"
    else:
        raise ValueError("path is required unless all_files=True")
    return GitCommand(git, args, root, label)


def unstage_command(
    repo_root: Path,
    path: str | None = None,
    all_files: bool = False,
    program: str | None = None,
    original_path: str = "",
) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    # `git reset` works on older Git versions and handles both modified and newly
    # added index entries. It only resets the index; the working tree is preserved.
    if all_files:
        args = ("-C", str(root), "reset")
        label = "Unstage all changes"
    elif path:
        paths = [str(path)]
        if original_path and original_path != path:
            paths.append(str(original_path))
        args = ("-C", str(root), "reset", "--", *paths)
        label = f"Unstage {path}"
    else:
        raise ValueError("path is required unless all_files=True")
    return GitCommand(git, args, root, label)


def commit_command(repo_root: Path, message: str, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    clean_message = str(message or "").strip()
    if not clean_message:
        raise ValueError("commit message is empty")
    return GitCommand(git, ("-C", str(root), "commit", "-m", clean_message), root, "Git commit")


def pull_command(repo_root: Path, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    # Avoid surprise merge commits from a GUI button. Diverged histories are
    # reported to the user and must be resolved explicitly.
    return GitCommand(git, ("-C", str(root), "pull", "--ff-only"), root, "Git pull --ff-only")


def push_command(repo_root: Path, program: str | None = None) -> GitCommand:
    git = _require_git(program)
    root = Path(repo_root)
    return GitCommand(git, ("-C", str(root), "push"), root, "Git push")
