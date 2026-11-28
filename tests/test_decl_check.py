"""Fixture suite for decl-check.py — the six declaration checks over disposable fake roots.

Style follows tests/test_brief_check.py: the CLI always runs as a real
subprocess (sys.executable, capture_output), fixtures are disposable tmp_path
trees, and the host tree is never written by a test. HOME is always pointed
inside the tmp tree, so the host's ~/.config/orchestrate/declarations.md can
never leak into a run; the machine-side check is exercised by building a
config root there, or skipped with --no-machine.

make_root lays out the minimal good tree (small valid declarations, a
SKILL.md with the chat-model line, an empty-ish bytecheck.md, commands/ with
valid cat commands); each test mutates exactly one thing. broken_command=True
swaps the second command file's cat argument for a non-resolving path — the
fixture's "one valid and one broken command file" form.
"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "decl-check.py"

# The fake opener starts with the tool's locator prefix and extends it, so the
# locator match and the byte-equal comparison are both exercised.
OPENER = ("Answer as a chat model \u2014 no agentic operations. "
          "Do not run tools; a fake opener for tests.")
PARAGRAPH = ("There's a <N\u2013M>-minute time limit for you to output your answer. "
             "A fake paragraph for tests.")


# ---------------------------------------------------------------------------
# fixtures and helpers


def make_root(base, broken_command=False):
    """The minimal good tree. Returns its root."""
    root = base / "root"
    decl = root / "declarations"
    decl.mkdir(parents=True)
    root_str = str(root)
    (decl / "core.md").write_text(
        "# core (fake)\n"
        f"map: {root_str}/declarations/roster.md"
        f" + {root_str}/declarations/projects/<project>.md \u2014 inlined by /o-open\n"
        "\n"
        "hard lines:\n"
        "  - every brief is the skeleton, copied by command"
        " \u2014 home: briefs.md and brief-skeleton.md\n"
        "  - a reply is harvested by command, never retyped \u2014 home: reply.md\n"
        "  - commit and push follow the project block \u2014 home: projects/<project>.md\n",
        encoding="utf-8",
    )
    for name in ("briefs.md", "reply.md", "roster.md", "jobs.md"):
        (decl / name).write_text(f"# {name} (fake)\n", encoding="utf-8")
    (decl / "brief-skeleton.md").write_text(
        OPENER + "\n\n" + PARAGRAPH + "\n\n## The task\n", encoding="utf-8"
    )
    (decl / "machines").mkdir()
    (decl / "machines" / "new-mac.md").write_text("# machine (fake)\n", encoding="utf-8")
    (decl / "projects").mkdir()
    (decl / "projects" / "demo.md").write_text("# project (fake)\n", encoding="utf-8")
    (root / "SKILL.md").write_text(
        "# skill (fake)\n\n> " + OPENER + "\n", encoding="utf-8"
    )
    (root / "bytecheck.md").write_text("# bytecheck (fake)\n", encoding="utf-8")
    commands = root / "commands"
    commands.mkdir()
    (commands / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n!`cat " + root_str + "/declarations/roster.md`\n",
        encoding="utf-8",
    )
    cat_arg = (root_str + "/declarations/missing-part.md" if broken_command
               else root_str + "/declarations/briefs.md")
    (commands / "o-brief.md").write_text(
        "---\ndescription: fake brief\n---\n!`cat " + cat_arg + "`\n",
        encoding="utf-8",
    )
    return root


def run_cli(root, args, home):
    """Real subprocess; HOME is forced inside the tmp tree; cwd is the tmp tree."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    cmd = [sys.executable, str(SCRIPT)] + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, env=env, timeout=120, cwd=str(root))


def run_ok(root, home):
    proc = run_cli(root, [root, "--no-machine"], home)
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    assert proc.stderr == b""
    return proc.stdout.decode("utf-8")


def run_fail(root, home):
    proc = run_cli(root, [root, "--no-machine"], home)
    assert proc.returncode == 1, proc.stdout.decode() + proc.stderr.decode()
    return proc.stdout.decode("utf-8")


def assert_single_miss(out, rule, *fragments):
    lines = out.splitlines()
    assert len(lines) == 2, out  # one miss line + the summary, last
    miss, summary = lines
    assert miss.startswith("! ") and f" {rule} " in miss
    for fragment in fragments:
        assert fragment in miss, miss
    assert summary.startswith("decl-check: FAIL 1 miss(es)")


# ---------------------------------------------------------------------------
# the good tree


def test_all_pass_on_good_tree(tmp_path):
    root = make_root(tmp_path)
    out = run_ok(root, tmp_path / "home")
    lines = out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("decl-check: PASS 0 miss(es) -> exit 0")


def test_machine_and_project_blocks_have_no_cap(tmp_path):
    root = make_root(tmp_path)
    big = "#" + "x" * 5000  # over every cap; machines and projects carry none
    (root / "declarations" / "machines" / "new-mac.md").write_text(big, encoding="utf-8")
    (root / "declarations" / "projects" / "demo.md").write_text(big, encoding="utf-8")
    out = run_ok(root, tmp_path / "home")
    assert "decl-check: PASS 0 miss(es)" in out


# ---------------------------------------------------------------------------
# check 1: byte caps, one test per part


def over_cap(tmp_path, name, cap, note=""):
    root = make_root(tmp_path)
    target = root / "declarations" / name
    # cap-sized filler appended to the last line: pushes the file past its cap
    # without touching the skeleton's line 1 and line 3 or any checked token
    target.write_bytes(target.read_bytes() + b"x" * (cap + 1))
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "cap", f"declarations/{name}", f"{cap:,}")
    if note:
        assert note in out


def test_cap_core_md_breach(tmp_path):
    over_cap(tmp_path, "core.md", 3500, note="amendment 5")


def test_cap_briefs_md_breach(tmp_path):
    over_cap(tmp_path, "briefs.md", 4000)


def test_cap_reply_md_breach(tmp_path):
    over_cap(tmp_path, "reply.md", 4000)


def test_cap_roster_md_breach(tmp_path):
    over_cap(tmp_path, "roster.md", 2000)


def test_cap_brief_skeleton_md_breach(tmp_path):
    over_cap(tmp_path, "brief-skeleton.md", 2200)


def test_cap_jobs_md_breach(tmp_path):
    over_cap(tmp_path, "jobs.md", 2800)


# ---------------------------------------------------------------------------
# check 2: path resolution


def test_resolving_path_in_core_passes(tmp_path):
    root = make_root(tmp_path)
    out = run_ok(root, tmp_path / "home")
    assert "! " not in out  # the good map path resolves: no path miss at all


def test_non_resolving_path_in_core_fails(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert f"{root}/declarations/roster.md" in text
    core.write_text(text.replace(f"{root}/declarations/roster.md",
                                 f"{root}/declarations/gone.md"), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "path", "core.md:", f"{root}/declarations/gone.md")


def test_broken_command_cat_path_fails(tmp_path):
    root = make_root(tmp_path, broken_command=True)
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "path", "commands/o-brief.md", "declarations/missing-part.md")


def test_template_tokens_dollar_and_angle_skipped(tmp_path):
    root = make_root(tmp_path)
    # the real o-open.md shape: a $1 template cat with 2>/dev/null and || echo tails
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n!`cat " + str(root)
        + "/declarations/projects/$1.md 2>/dev/null"
        " || echo \"(no block for '$1' \u2014 say so and ask)\"`\n",
        encoding="utf-8",
    )
    out = run_ok(root, tmp_path / "home")
    assert "$1" not in out and "<project>" not in out  # skipped, not reported


# ---------------------------------------------------------------------------
# check 3: the opener


def test_opener_mismatch_skill_line_altered(tmp_path):
    root = make_root(tmp_path)
    skill = root / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    skill.write_text(text.replace("no agentic operations", "no agentic ops"), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "opener", "SKILL.md")


def test_opener_mismatch_skeleton_line_altered(tmp_path):
    root = make_root(tmp_path)
    skeleton = root / "declarations" / "brief-skeleton.md"
    text = skeleton.read_text(encoding="utf-8")
    skeleton.write_text(text.replace("no agentic operations", "no agentic ops"), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "opener", "brief-skeleton.md:1", "differs")


# ---------------------------------------------------------------------------
# check 4: the time-limit paragraph


def test_paragraph_duplicated_in_two_files(tmp_path):
    root = make_root(tmp_path)
    (root / "bytecheck.md").write_text("# bytecheck (fake)\n" + PARAGRAPH + "\n",
                                       encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "paragraph", "2 files", "brief-skeleton.md", "bytecheck.md")


def test_paragraph_absent(tmp_path):
    root = make_root(tmp_path)
    skeleton = root / "declarations" / "brief-skeleton.md"
    lines = skeleton.read_text(encoding="utf-8").split("\n")
    assert lines[2] == PARAGRAPH
    lines[2] = "No time limit here."
    skeleton.write_text("\n".join(lines), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "paragraph", "0 files")


# ---------------------------------------------------------------------------
# check 5: hard-line homes


def test_hard_line_without_valid_home(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert text.count("\u2014 home: reply.md") == 1
    core.write_text(text.replace("\u2014 home: reply.md", "\u2014 home: nowhere.md"),
                    encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "nowhere.md")


# ---------------------------------------------------------------------------
# check 6: the machine-side config root (HOME-scoped; --no-machine coverage)


def config_root(tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "orchestrate"
    config_dir.mkdir(parents=True)
    return home, config_dir / "declarations.md"


def test_config_root_symlink_good(tmp_path):
    root = make_root(tmp_path)
    home, declarations_md = config_root(tmp_path)
    declarations_md.symlink_to(root / "declarations" / "core.md")
    proc = run_cli(root, [root], home)
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    assert "decl-check: PASS 0 miss(es)" in proc.stdout.decode()


def test_config_root_symlink_wrong_target(tmp_path):
    root = make_root(tmp_path)
    home, declarations_md = config_root(tmp_path)
    declarations_md.symlink_to(root / "declarations" / "roster.md")
    proc = run_cli(root, [root], home)
    assert proc.returncode == 1
    assert_single_miss(proc.stdout.decode("utf-8"), "config-root", "~/.config/orchestrate")


def test_config_root_missing(tmp_path):
    root = make_root(tmp_path)
    home, _declarations_md = config_root(tmp_path)
    proc = run_cli(root, [root], home)
    assert proc.returncode == 1
    assert_single_miss(proc.stdout.decode("utf-8"), "config-root",
                       "~/.config/orchestrate/declarations.md", "missing")


def test_config_root_regular_file_equal_bytes(tmp_path):
    root = make_root(tmp_path)
    home, declarations_md = config_root(tmp_path)
    declarations_md.write_bytes((root / "declarations" / "core.md").read_bytes())
    proc = run_cli(root, [root], home)
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


def test_config_root_regular_file_unequal_bytes(tmp_path):
    root = make_root(tmp_path)
    home, declarations_md = config_root(tmp_path)
    declarations_md.write_bytes((root / "declarations" / "roster.md").read_bytes())
    proc = run_cli(root, [root], home)
    assert proc.returncode == 1
    assert_single_miss(proc.stdout.decode("utf-8"), "config-root", "byte for byte")


def test_no_machine_skips_config_root(tmp_path):
    root = make_root(tmp_path)
    home, _declarations_md = config_root(tmp_path)  # the config root stays missing
    proc = run_cli(root, [root, "--no-machine"], home)
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


# ---------------------------------------------------------------------------
# exit 2: usage and environment


def test_usage_unknown_flag_exits_2(tmp_path):
    root = make_root(tmp_path)
    proc = run_cli(root, [root, "--bogus"], tmp_path / "home")
    assert proc.returncode == 2
    assert proc.stdout == b""


def test_usage_root_not_a_directory_exits_2(tmp_path):
    root = make_root(tmp_path)
    proc = run_cli(root, [tmp_path / "nope"], tmp_path / "home")
    assert proc.returncode == 2
    assert proc.stdout == b""
    assert b"not a directory" in proc.stderr
