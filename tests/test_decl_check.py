"""Fixture suite for decl-check.py — the six declaration checks over disposable fake roots.

Style follows tests/test_brief_check.py: the CLI always runs as a real
subprocess (sys.executable, capture_output), fixtures are disposable tmp_path
trees, and the host tree is never written by a test. HOME is always pointed
inside the tmp tree, so the host's ~/.config/orchestrate/declarations.md can
never leak into a run; the machine-side check is exercised by building a
config root there, or skipped with --no-machine.

make_root lays out the minimal good tree in the adopted shapes: the
time-limit paragraph sits in the skeleton's prose head — the lines before the
first "## " heading, a blank line before it (position-free slot — the
finding-17 repro baked in) — and every command file's `!` lines are
well-formed directives (counts vary per command by design) whose cat paths
name tree files, and core.md keeps a hard-lines block whose bullets all
carry well-formed " — home: <part>" tails. Each test mutates exactly one
thing. broken_command=True points the second command file's third directive
at a non-resolving tree path.
"""

import os
import shutil
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
CONTRACT = "In this order: <what to return, in what order>. Cap: \u2264<LINES> lines."

SKELETON_TEXT = "\n".join([
    OPENER,
    "",
    PARAGRAPH,  # the prose head: opener, then the window paragraph, before any heading
    "",
    "## The task",
    "<one or two sentences; less is better>",
    "",
    "## Output contract",
    CONTRACT,
    "",
    "End with COMPLETE on its own line.",
    "",
])


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
        "- self-rescue: before compose/reply/job without that part in recent messages"
        " \u2014 read it whole now (paths above).\n"
        "\n"
        "- hard lines, each \"<imperative> \u2014 home: <part>\":\n"
        "  - every brief is the skeleton, copied by command"
        " \u2014 home: briefs.md and brief-skeleton.md\n"
        "  - a reply is harvested by command, never retyped \u2014 home: reply.md\n"
        "  - commit and push follow the project block \u2014 home: projects/<project>.md\n"
        "\n"
        "### 1.5 Conduct\n"
        "- simple questions: answer briefly and superficially.\n",
        encoding="utf-8",
    )
    for name in ("briefs.md", "reply.md", "roster.md", "jobs.md"):
        (decl / name).write_text(f"# {name} (fake)\n", encoding="utf-8")
    (decl / "brief-skeleton.md").write_text(SKELETON_TEXT, encoding="utf-8")
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

    def directives(*parts):
        body = "---\ndescription: fake\n---\n"
        body += "\n\n".join("!`cat " + part + "`" for part in parts)
        return body + "\n"

    (commands / "o-open.md").write_text(directives(
        root_str + "/declarations/core.md",
        root_str + "/declarations/roster.md",
        root_str + "/declarations/machines/new-mac.md",
    ), encoding="utf-8")
    third = (root_str + "/declarations/missing-part.md" if broken_command
             else root_str + "/declarations/roster.md")
    (commands / "o-brief.md").write_text(directives(
        root_str + "/declarations/core.md",
        root_str + "/declarations/briefs.md",
        third,
    ), encoding="utf-8")
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


def config_root(tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "orchestrate"
    config_dir.mkdir(parents=True)
    return home, config_dir / "declarations.md"


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
    # without touching the skeleton's opener and contract slot or any checked token
    target.write_bytes(target.read_bytes() + b"x" * (cap + 1))
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "cap", f"declarations/{name}", f"{cap:,}")
    if note:
        assert note in out


def test_cap_core_md_breach(tmp_path):
    over_cap(tmp_path, "core.md", 3800, note="freeze line")


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
# check 2: directives and path resolution


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
    root_str = str(root)
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n"
        "!`cat " + root_str + "/declarations/core.md`\n\n"
        "!`cat " + root_str + "/declarations/roster.md`\n\n"
        "!`cat " + root_str + "/declarations/projects/$1.md 2>/dev/null"
        " || echo \"(no block for '$1' \u2014 say so and ask)\"`\n",
        encoding="utf-8",
    )
    out = run_ok(root, tmp_path / "home")
    assert "$1" not in out and "<project>" not in out  # skipped, not reported


def test_directive_lost_bang_fails(tmp_path):
    root = make_root(tmp_path)
    o_open = root / "commands" / "o-open.md"
    # the reviewed case: a dropped ! degrades the directive to plain prompt text
    o_open.write_text(o_open.read_text(encoding="utf-8")
                      .replace("!`cat " + str(root) + "/declarations/roster.md`",
                               "`cat " + str(root) + "/declarations/roster.md`"),
                      encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "directive", "commands/o-open.md", "lost its leading !")


def test_directive_bang_without_backtick_fails(tmp_path):
    root = make_root(tmp_path)
    o_open = root / "commands" / "o-open.md"
    # a ! that is not immediately followed by a backtick block is not a directive
    o_open.write_text(o_open.read_text(encoding="utf-8")
                      .replace("!`cat " + str(root) + "/declarations/roster.md`",
                               "! cat " + str(root) + "/declarations/roster.md"),
                      encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "directive", "commands/o-open.md", "not a well-formed directive")


def test_command_directive_counts_vary(tmp_path):
    # the invariant is well-formedness, not a count: o-open's real 4-directive
    # shape and o-reply's real 2-directive shape both pass
    root = make_root(tmp_path)
    root_str = str(root)

    def directives(*parts):
        body = "---\ndescription: fake\n---\n"
        body += "\n\n".join("!`cat " + part + "`" for part in parts)
        return body + "\n"

    commands = root / "commands"
    (commands / "o-open.md").write_text(directives(
        root_str + "/declarations/core.md",
        root_str + "/declarations/roster.md",
        root_str + "/declarations/machines/new-mac.md",
        root_str + "/declarations/projects/demo.md",
    ), encoding="utf-8")
    (commands / "o-reply.md").write_text(directives(
        root_str + "/declarations/core.md",
        root_str + "/declarations/reply.md",
    ), encoding="utf-8")
    out = run_ok(root, tmp_path / "home")
    assert "decl-check: PASS 0 miss(es)" in out


def test_commands_dir_missing_fails(tmp_path):
    root = make_root(tmp_path)
    shutil.rmtree(root / "commands")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "directive", "commands", "missing")


def test_non_tree_cat_path_not_checked(tmp_path):
    root = make_root(tmp_path)
    home = tmp_path / "home"  # notes.md exists nowhere
    root_str = str(root)
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n"
        "!`cat " + root_str + "/declarations/core.md`\n\n"
        "!`cat " + root_str + "/declarations/roster.md`\n\n"
        "!`cat ~/.config/orchestrate/notes.md`\n",  # no declarations/ or commands/ segment
        encoding="utf-8",
    )
    out = run_ok(root, home)  # only the config-root check touches the live home
    assert "notes.md" not in out


def test_glob_cat_path_resolves(tmp_path):
    root = make_root(tmp_path)
    # the adopted whole-projects inline: the glob matches the tree's project
    # blocks (declarations/projects/demo.md exists), so the directive resolves
    root_str = str(root)
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n"
        "!`cat " + root_str + "/declarations/core.md`\n\n"
        "!`cat " + root_str + "/declarations/roster.md`\n\n"
        "!`cat ~/.config/opencode/skills/orchestrate/declarations/projects/*.md`\n",
        encoding="utf-8",
    )
    out = run_ok(root, tmp_path / "home")
    assert "*.md" not in out  # the glob matched projects/demo.md: no miss


def test_glob_cat_path_matching_nothing_fails(tmp_path):
    root = make_root(tmp_path)
    root_str = str(root)
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n"
        "!`cat " + root_str + "/declarations/core.md`\n\n"
        "!`cat " + root_str + "/declarations/roster.md`\n\n"
        "!`cat " + root_str + "/declarations/projects/none-*.md`\n",
        encoding="utf-8",
    )
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "path", "commands/o-open.md",
                       "declarations/projects/none-*.md", "matched 0 files")


def test_prose_slash_words_are_not_paths(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    # the reviewed false positive: "compose/reply/job" glued to a word is prose,
    # not an absolute path - deepening it must not create a path miss
    text = core.read_text(encoding="utf-8")
    assert "compose/reply/job" in text
    core.write_text(text.replace("before compose/reply/job without",
                                 "before compose/reply/job/executor without"), encoding="utf-8")
    out = run_ok(root, tmp_path / "home")
    assert "/reply/" not in out


def test_installed_path_cannot_mask_missing_tree_file(tmp_path):
    root = make_root(tmp_path)
    home = tmp_path / "home"
    # a live installation that HAS the file the checked tree lacks
    master = home / ".config" / "opencode" / "skills" / "orchestrate" / "declarations"
    master.mkdir(parents=True)
    (master / "gone.md").write_text("# gone in the tree, present in the install\n",
                                    encoding="utf-8")
    (root / "commands" / "o-open.md").write_text(
        "---\ndescription: fake open\n---\n"
        "!`cat " + str(root) + "/declarations/core.md`\n\n"
        "!`cat " + str(root) + "/declarations/roster.md`\n\n"
        "!`cat ~/.config/opencode/skills/orchestrate/declarations/gone.md`\n",
        encoding="utf-8",
    )
    out = run_fail(root, home)
    # resolved tree-relative: declarations/gone.md under --root, not the live install
    assert_single_miss(out, "path", "commands/o-open.md", "declarations/gone.md")


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
# check 4: the time-limit paragraph (contract-section slot, live homes)


def test_paragraph_duplicated_in_project_block(tmp_path):
    root = make_root(tmp_path)
    (root / "declarations" / "projects" / "demo.md").write_text(
        "# project (fake)\n" + PARAGRAPH + "\n", encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "paragraph", "2 files", "brief-skeleton.md", "projects/demo.md")


def test_paragraph_duplicated_in_command(tmp_path):
    root = make_root(tmp_path)
    o_brief = root / "commands" / "o-brief.md"
    o_brief.write_text(o_brief.read_text(encoding="utf-8") + "\n" + PARAGRAPH + "\n",
                       encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "paragraph", "2 files", "brief-skeleton.md", "commands/o-brief.md")


def test_paragraph_absent(tmp_path):
    root = make_root(tmp_path)
    skeleton = root / "declarations" / "brief-skeleton.md"
    text = skeleton.read_text(encoding="utf-8")
    assert "\n\n" + PARAGRAPH in text
    skeleton.write_text(text.replace("\n\n" + PARAGRAPH, ""), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "paragraph", "not in the skeleton's prose head")


# ---------------------------------------------------------------------------
# check 5: the hard-lines block and its homes


def test_hard_line_without_valid_home(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert text.count("\u2014 home: reply.md") == 1
    core.write_text(text.replace("\u2014 home: reply.md", "\u2014 home: nowhere.md"),
                    encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "nowhere.md")


def test_hard_line_missing_separator_fails(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    # the reviewed PASS bug: the tail deleted, the bullet must still be found
    assert text.count(" \u2014 home: reply.md") == 1
    core.write_text(text.replace(" \u2014 home: reply.md", ""), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "malformed")


def test_hard_line_malformed_separator_no_crash(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    # the reviewed crash: the space before the dash removed — the old regex still
    # matched the bullet while its rsplit raised IndexError
    assert text.count("retyped \u2014 home: reply.md") == 1
    core.write_text(text.replace("retyped \u2014 home: reply.md", "retyped\u2014 home: reply.md"),
                    encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "malformed")


def test_hard_lines_block_missing_fails(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    start = text.index("- hard lines")
    end = text.index("\n\n### 1.5")
    core.write_text(text[:start] + text[end + 2:], encoding="utf-8")  # the block dropped
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md", "no hard-lines block")


def test_hard_line_home_section_qualifier_passes(tmp_path):
    # form (c), the owner's settled shape: "file §section" - the qualifier is
    # decoration, the file part must exist
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert text.count("\u2014 home: reply.md") == 1
    core.write_text(text.replace("\u2014 home: reply.md",
                                 "\u2014 home: reply.md \u00a71.3"), encoding="utf-8")
    out = run_ok(root, tmp_path / "home")
    assert "reply.md \u00a71.3" not in out  # the qualified home is not a miss


def test_hard_line_home_section_missing_file_fails(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert text.count("\u2014 home: reply.md") == 1
    core.write_text(text.replace("\u2014 home: reply.md",
                                 "\u2014 home: nosuch.md \u00a71.6"), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "nosuch.md")


def test_hard_line_home_empty_qualifier_fails(tmp_path):
    root = make_root(tmp_path)
    core = root / "declarations" / "core.md"
    text = core.read_text(encoding="utf-8")
    assert text.count("\u2014 home: reply.md") == 1
    core.write_text(text.replace("\u2014 home: reply.md",
                                 "\u2014 home: reply.md \u00a7"), encoding="utf-8")
    out = run_fail(root, tmp_path / "home")
    assert_single_miss(out, "home", "core.md:", "empty \u00a7qualifier")


# ---------------------------------------------------------------------------
# check 6: the machine-side config root (HOME-scoped; --no-machine coverage)


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
