from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.git_tools import (
    commit_command,
    diff_command,
    parse_porcelain_v2_z,
    parse_repo_root,
    probe_repository_command,
    pull_command,
    push_command,
    stage_command,
    status_command,
    unstage_command,
)


def _run(command, *, text: bool = True):
    return subprocess.run(
        [command.program, *command.arguments],
        cwd=command.workdir,
        capture_output=True,
        text=text,
        check=False,
        timeout=15,
    )


@unittest.skipUnless(shutil.which("git"), "git CLI not installed")
class GitIntegrationTests(unittest.TestCase):
    def _repo(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "astra@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Astra Test"], check=True)
        return tmp, root

    def _initial_commit(self, root: Path):
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "initial"], check=True)

    def test_repository_probe_from_nested_directory(self):
        tmp, root = self._repo()
        with tmp:
            nested = root / "src" / "nested"
            nested.mkdir(parents=True)
            proc = _run(probe_repository_command(nested, "git"))
            self.assertEqual(proc.returncode, 0)
            parsed = parse_repo_root(proc.stdout)
            self.assertEqual(parsed, root.resolve())

    def test_status_parser_handles_staged_unstaged_untracked_and_unicode_paths(self):
        tmp, root = self._repo()
        with tmp:
            self._initial_commit(root)
            (root / "tracked.txt").write_text("one\ntwo\n", encoding="utf-8")
            (root / "staged space.txt").write_text("staged\n", encoding="utf-8")
            (root / "новый файл.txt").write_text("new\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "staged space.txt"], check=True)
            proc = _run(status_command(root, "git"), text=False)
            self.assertEqual(proc.returncode, 0)
            state = parse_porcelain_v2_z(proc.stdout, root)
            by_path = {item.path: item for item in state.entries}
            self.assertTrue(by_path["tracked.txt"].unstaged)
            self.assertTrue(by_path["staged space.txt"].staged)
            self.assertTrue(by_path["новый файл.txt"].untracked)
            self.assertGreaterEqual(state.staged_count, 1)
            self.assertGreaterEqual(state.unstaged_count, 2)

    def test_status_parser_handles_rename_original_path(self):
        tmp, root = self._repo()
        with tmp:
            self._initial_commit(root)
            subprocess.run(["git", "-C", str(root), "mv", "tracked.txt", "renamed.txt"], check=True)
            proc = _run(status_command(root, "git"), text=False)
            state = parse_porcelain_v2_z(proc.stdout, root)
            renamed = next(item for item in state.entries if item.kind == "rename_copy")
            self.assertEqual(renamed.path, "renamed.txt")
            self.assertEqual(renamed.original_path, "tracked.txt")
            self.assertTrue(renamed.staged)

    def test_rename_diff_and_unstage_include_both_paths(self):
        tmp, root = self._repo()
        with tmp:
            self._initial_commit(root)
            subprocess.run(["git", "-C", str(root), "mv", "tracked.txt", "renamed.txt"], check=True)
            diff = _run(diff_command(root, "renamed.txt", True, "git", original_path="tracked.txt"))
            self.assertIn("rename from tracked.txt", diff.stdout)
            self.assertIn("rename to renamed.txt", diff.stdout)
            result = _run(unstage_command(root, "renamed.txt", program="git", original_path="tracked.txt"))
            self.assertEqual(result.returncode, 0)
            short = subprocess.run(["git", "-C", str(root), "status", "--short"], capture_output=True, text=True, check=True).stdout
            self.assertIn(" D tracked.txt", short)
            self.assertIn("?? renamed.txt", short)
            self.assertNotIn("D  tracked.txt", short)

    def test_stage_unstage_diff_and_commit_commands_change_only_expected_git_state(self):
        tmp, root = self._repo()
        with tmp:
            self._initial_commit(root)
            (root / "tracked.txt").write_text("one\nchanged\n", encoding="utf-8")

            working_diff = _run(diff_command(root, "tracked.txt", False, "git"))
            self.assertEqual(working_diff.returncode, 0)
            self.assertIn("+changed", working_diff.stdout)

            staged = _run(stage_command(root, "tracked.txt", program="git"))
            self.assertEqual(staged.returncode, 0)
            staged_diff = _run(diff_command(root, "tracked.txt", True, "git"))
            self.assertIn("+changed", staged_diff.stdout)

            unstaged = _run(unstage_command(root, "tracked.txt", program="git"))
            self.assertEqual(unstaged.returncode, 0)
            self.assertEqual(_run(diff_command(root, "tracked.txt", True, "git")).stdout, "")
            self.assertIn("+changed", _run(diff_command(root, "tracked.txt", False, "git")).stdout)

            self.assertEqual(_run(stage_command(root, "tracked.txt", program="git")).returncode, 0)
            committed = _run(commit_command(root, "C3 test commit", "git"))
            self.assertEqual(committed.returncode, 0)
            state_proc = _run(status_command(root, "git"), text=False)
            state = parse_porcelain_v2_z(state_proc.stdout, root)
            self.assertFalse(state.dirty)

    def test_unstage_works_before_first_commit(self):
        tmp, root = self._repo()
        with tmp:
            (root / "first.txt").write_text("first\n", encoding="utf-8")
            self.assertEqual(_run(stage_command(root, "first.txt", program="git")).returncode, 0)
            state = parse_porcelain_v2_z(_run(status_command(root, "git"), text=False).stdout, root)
            self.assertEqual(state.oid, "(initial)")
            self.assertEqual(state.staged_count, 1)
            self.assertEqual(_run(unstage_command(root, "first.txt", program="git")).returncode, 0)
            state = parse_porcelain_v2_z(_run(status_command(root, "git"), text=False).stdout, root)
            self.assertEqual(state.staged_count, 0)
            self.assertTrue(state.entries[0].untracked)

    def test_stage_all_and_unstage_all_preserve_worktree(self):
        tmp, root = self._repo()
        with tmp:
            self._initial_commit(root)
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            (root / "new.txt").write_text("new\n", encoding="utf-8")
            self.assertEqual(_run(stage_command(root, all_files=True, program="git")).returncode, 0)
            self.assertTrue(parse_porcelain_v2_z(_run(status_command(root, "git"), text=False).stdout, root).staged_count >= 2)
            self.assertEqual(_run(unstage_command(root, all_files=True, program="git")).returncode, 0)
            state = parse_porcelain_v2_z(_run(status_command(root, "git"), text=False).stdout, root)
            self.assertEqual(state.staged_count, 0)
            self.assertTrue((root / "tracked.txt").exists())
            self.assertTrue((root / "new.txt").exists())

    def test_branch_upstream_ahead_behind_headers_parse(self):
        payload = (
            "# branch.oid deadbeef\0"
            "# branch.head main\0"
            "# branch.upstream origin/main\0"
            "# branch.ab +3 -2\0"
        )
        state = parse_porcelain_v2_z(payload, Path("/repo"))
        self.assertEqual(state.branch, "main")
        self.assertEqual(state.upstream, "origin/main")
        self.assertEqual(state.ahead, 3)
        self.assertEqual(state.behind, 2)

    def test_local_bare_remote_pull_and_push_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "remote.git"
            first = base / "first"
            second = base / "second"
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            subprocess.run(["git", "clone", "-q", str(remote), str(first)], check=True)
            for repo in (first,):
                subprocess.run(["git", "-C", str(repo), "config", "user.email", "astra@example.invalid"], check=True)
                subprocess.run(["git", "-C", str(repo), "config", "user.name", "Astra Test"], check=True)
            (first / "shared.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "shared.txt"], check=True)
            subprocess.run(["git", "-C", str(first), "commit", "-qm", "initial"], check=True)
            subprocess.run(["git", "-C", str(first), "push", "-qu", "origin", "HEAD"], check=True)

            subprocess.run(["git", "clone", "-q", str(remote), str(second)], check=True)
            subprocess.run(["git", "-C", str(second), "config", "user.email", "astra@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(second), "config", "user.name", "Astra Test"], check=True)
            (second / "shared.txt").write_text("one\ntwo\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(second), "add", "shared.txt"], check=True)
            subprocess.run(["git", "-C", str(second), "commit", "-qm", "remote change"], check=True)
            subprocess.run(["git", "-C", str(second), "push", "-q"], check=True)

            pulled = _run(pull_command(first, "git"))
            self.assertEqual(pulled.returncode, 0, pulled.stderr)
            self.assertEqual((first / "shared.txt").read_text(encoding="utf-8"), "one\ntwo\n")

            (first / "local.txt").write_text("local\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "local.txt"], check=True)
            subprocess.run(["git", "-C", str(first), "commit", "-qm", "local change"], check=True)
            pushed = _run(push_command(first, "git"))
            self.assertEqual(pushed.returncode, 0, pushed.stderr)
            subprocess.run(["git", "-C", str(second), "pull", "-q", "--ff-only"], check=True)
            self.assertTrue((second / "local.txt").is_file())

    def test_pull_ff_only_refuses_diverged_history_without_merge_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "remote.git"
            first = base / "first"
            second = base / "second"
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            subprocess.run(["git", "clone", "-q", str(remote), str(first)], check=True)
            subprocess.run(["git", "-C", str(first), "config", "user.email", "astra@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(first), "config", "user.name", "Astra Test"], check=True)
            (first / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "base.txt"], check=True)
            subprocess.run(["git", "-C", str(first), "commit", "-qm", "base"], check=True)
            subprocess.run(["git", "-C", str(first), "push", "-qu", "origin", "HEAD"], check=True)
            subprocess.run(["git", "clone", "-q", str(remote), str(second)], check=True)
            subprocess.run(["git", "-C", str(second), "config", "user.email", "astra@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(second), "config", "user.name", "Astra Test"], check=True)

            (first / "first.txt").write_text("first\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(first), "add", "first.txt"], check=True)
            subprocess.run(["git", "-C", str(first), "commit", "-qm", "first diverges"], check=True)

            (second / "second.txt").write_text("second\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(second), "add", "second.txt"], check=True)
            subprocess.run(["git", "-C", str(second), "commit", "-qm", "second diverges"], check=True)
            subprocess.run(["git", "-C", str(second), "push", "-q"], check=True)

            before = subprocess.run(["git", "-C", str(first), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            pulled = _run(pull_command(first, "git"))
            after = subprocess.run(["git", "-C", str(first), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            self.assertNotEqual(pulled.returncode, 0)
            self.assertEqual(before, after)
            parents = subprocess.run(["git", "-C", str(first), "rev-list", "--parents", "-n", "1", "HEAD"], capture_output=True, text=True, check=True).stdout.split()
            self.assertEqual(len(parents), 2)


class GitCommandSafetyTests(unittest.TestCase):
    def test_commit_rejects_empty_message(self):
        with self.assertRaises(ValueError):
            commit_command(Path("/repo"), "   ", "git")

    def test_pull_is_fast_forward_only(self):
        command = pull_command(Path("/repo"), "git")
        self.assertEqual(command.arguments[-2:], ("pull", "--ff-only"))

    def test_push_has_no_force_flags(self):
        command = push_command(Path("/repo"), "git")
        self.assertEqual(command.arguments[-1], "push")
        self.assertNotIn("--force", command.arguments)
        self.assertNotIn("-f", command.arguments)

    def test_paths_are_passed_after_double_dash_without_shell(self):
        weird = "folder/a file --danger.txt"
        stage = stage_command(Path("/repo"), weird, program="git")
        diff = diff_command(Path("/repo"), weird, program="git")
        self.assertIn("--", stage.arguments)
        self.assertEqual(stage.arguments[-1], weird)
        self.assertEqual(diff.arguments[-1], weird)


if __name__ == "__main__":
    unittest.main()

class MainGitIntegrationStaticTests(unittest.TestCase):
    def test_git_source_control_ui_and_actions_are_wired(self):
        main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        required = [
            "btn_git_source_control", "git_tree", "git_diff_view", "git_commit_message",
            "refresh_git_status", "show_selected_git_diff", "git_stage_selected",
            "git_unstage_selected", "git_commit", "git_pull", "git_push",
        ]
        for token in required:
            self.assertIn(token, main_source)

    def test_git_network_actions_disable_terminal_prompt_and_never_force_push(self):
        main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        git_source = (Path(__file__).resolve().parents[1] / "core" / "git_tools.py").read_text(encoding="utf-8")
        self.assertIn('"GIT_TERMINAL_PROMPT": "0"', main_source)
        self.assertIn('("-C", str(root), "push")', git_source)
        self.assertNotIn('"--force"', git_source)
        self.assertNotIn('"--force-with-lease"', git_source)

    def test_pull_guard_requires_clean_tree_and_upstream(self):
        main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("if not self.git_state.upstream:", main_source)
        self.assertIn("if self.git_state.dirty:", main_source)
        self.assertIn("pull --ff-only", main_source)
