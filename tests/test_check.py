"""Suite for check.py's brief mode (DECISION-2 §C, §E lessons).

Real subprocess runs, tmp_path fixtures filled at run time from the SHIPPED
declarations/brief-skeleton.md - no skeleton text copied here, so a skeleton edit
cannot strand a fixture. No test pins wording beyond the VERDICT/HARVEST prefixes.
Coverage: one pass case, one refusal per clause, F4/F5/F8/F13/F19.
"""
import json, os, shlex, subprocess, sys, time
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parent.parent / "check.py"
SKELETON = CHECK.parent / "declarations" / "brief-skeleton.md"
SESSION = "ses_check_test"
UNSET = "<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"
PAIR = ["=== begin design ===", "=== end design ==="]
WINDOW = "6\u201310"  # en dash, as the skeleton's <N-M> slot expects


def run(tmp_path, args, session=SESSION, mode="brief"):
    env = dict(os.environ)
    env.pop("OPENCODE_SESSION_ID", None)
    if session is not None:
        env["OPENCODE_SESSION_ID"] = session
    cmd = [sys.executable, str(CHECK)] + ([mode] if mode else []) + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, env=env, timeout=120, cwd=str(tmp_path))


def filled_brief(dir_path, name="2-foo.md", marker=True):
    """Every slot filled in place; marker=False: a no-artifact contract."""
    text = SKELETON.read_text(encoding="utf-8")
    for old, new in [
        ("<one or two sentences; less is better>", "Shape the gate."),
        ("<each with its path or source>", "- DECISION-2 §C"),
        ("<...>", "- none"),
        ("<files whole or in generous excerpts>", "- declarations/brief-skeleton.md"),
        ("<what to return, in what order>", "the design"),
        ("<LINES>", "350"),
        ("<N\u2013M>", WINDOW),
        ("`reply <n>-<slug>`", "`reply %s`" % Path(name).stem),
        ("=== begin <name> ===", PAIR[0]),
        ("<the artifact, ONE <BREAK>-joined line>", "the artifact, one line"),
        ("=== end <name> ===", PAIR[1]),
    ]:
        assert old in text, "skeleton changed: %r" % old
        text = text.replace(old, new)
    if not marker:
        text = "\n".join(l for l in text.split("\n") if l not in PAIR and not l.startswith("the artifact, one line"))
    path = dir_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def good(tmp_path):
    return filled_brief(tmp_path)


def argv_of(proc):  # the HARVEST argv after the prefix, parsed the way sh would
    return shlex.split(proc.stdout.decode("utf-8").splitlines()[1][9:])


# --- the pass case: two lines, the profile, the harvest


def test_pass_prints_two_lines_and_writes_profile(tmp_path, good):
    proc = run(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stderr.decode()
    lines = proc.stdout.decode("utf-8").splitlines()
    assert len(lines) == 2 and lines[0].startswith("VERDICT: brief ok ") and lines[1].startswith("HARVEST: ")
    assert lines[0] == "VERDICT: brief ok %s %d window %s" % (good, good.stat().st_size, WINDOW)
    argv, replies = argv_of(proc), tmp_path / "round-1" / "replies"
    profile = replies / "2-foo.md.profile.json"
    assert argv[:4] == ["python3", str(CHECK.parent / "extract-reply.py"), "reply 2-foo", str(profile)]
    assert argv[4:6] == ["--session", SESSION] and argv[6] == "--since" and argv[8] == "--out"
    assert abs(int(argv[7]) - time.time()) < 120 and argv[9] == str(replies / "2-foo.md")
    doc = json.loads(profile.read_text(encoding="utf-8"))
    assert doc == {"version": 1, "required_lines": PAIR, "terminal_line": "COMPLETE"}
    assert (profile.stat().st_mode & 0o777) == 0o600


def test_round_taken_as_given_and_harvest_shell_safe(tmp_path):
    """F4/F5: a $( ) slug and a spaced round dir travel as data as given."""
    brief = filled_brief(tmp_path, name="2-fo$(reboot)o.md")
    round_dir = tmp_path / "TD rounds" / "spares guard round"
    proc = run(tmp_path, [brief, "--round", str(round_dir)])
    assert proc.returncode == 0, proc.stderr.decode()
    argv, stem = argv_of(proc), "2-fo$(reboot)o"
    assert argv[2] == "reply " + stem
    assert argv[3] == str(round_dir / "replies" / (stem + ".md.profile.json"))
    assert argv[9] == str(round_dir / "replies" / (stem + ".md"))
    assert list(tmp_path.glob("round-*")) == []  # sh re-parses the HARVEST line the same way (shlex round-trip)


def test_unset_session_is_named_never_empty(tmp_path, good):
    proc = run(tmp_path, [good, "--round", "round-1"], session=None)
    assert proc.returncode == 0
    assert argv_of(proc)[4:6] == ["--session", UNSET]


def test_profile_never_rewritten_since_is_its_mtime(tmp_path, good):
    """F19: a rerun rewrites nothing; --since is the profile's mtime."""
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    first = run(tmp_path, [good, "--round", "round-1"])
    assert first.returncode == 0
    since, before = argv_of(first)[7], (profile.stat().st_mtime_ns, profile.read_bytes())
    time.sleep(1.1)
    second = run(tmp_path, [good, "--round", "round-1"])
    assert second.returncode == 0, second.stderr.decode()
    assert argv_of(second)[7] == since  # the first hand-over time, not a re-stamp
    assert (profile.stat().st_mtime_ns, profile.read_bytes()) == before
    assert int(profile.stat().st_mtime) == int(since)  # --since IS the mtime


def test_zero_marker_pairs_is_legal(tmp_path):
    """F8: an explicitly no-artifact contract passes (required_lines [])."""
    brief = filled_brief(tmp_path, marker=False)
    proc = run(tmp_path, [brief, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    doc = json.loads((tmp_path / "round-1" / "replies" / "2-foo.md.profile.json").read_text(encoding="utf-8"))
    assert doc["required_lines"] == [] and doc["terminal_line"] == "COMPLETE"


def test_crlf_lines_pass_with_bytes_untouched(tmp_path):
    """F13: CRLF is a line terminator; the bytes stay untouched."""
    brief = filled_brief(tmp_path, name="3-crlf.md")
    brief.write_bytes(brief.read_bytes().replace(b"\n", b"\r\n"))
    proc = run(tmp_path, [brief, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    assert proc.stdout.decode("utf-8").splitlines()[0] == \
        "VERDICT: brief ok %s %d window %s" % (brief, brief.stat().st_size, WINDOW)


# --- one refusal per clause: one miss line each, check and path


MUTATIONS = [
    (1, 1, lambda t: t.replace("no agentic operations", "no agent-ic operations")),
    (2, 2, lambda t: t.replace(WINDOW, "<N\u2013M>", 1)),  # the unfilled slot is also a placeholder
    (3, 1, lambda t: t + "\npull the roster from <project> first.\n"),
    (5, 1, lambda t: t.replace("hard stop at %s minutes" % WINDOW, "hard stop at 99 minutes")),
    (6, 1, lambda t: t.replace(PAIR[1] + "\n", "")),
    (7, 1, lambda t: t.replace("COMPLETE", "DONE")),
]


@pytest.mark.parametrize("number,clauses,mutate", MUTATIONS)
def test_refusal_names_the_check_and_the_path(tmp_path, good, number, clauses, mutate):
    good.write_text(mutate(good.read_text(encoding="utf-8")), encoding="utf-8")
    proc = run(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode("utf-8")
    assert out.startswith("FAIL %d %s:" % (number, good))  # check and path, never contents
    assert out.count("\n") == clauses  # one clause per missed check


def test_refusal_phrase_not_named_after_rename(tmp_path, good):
    renamed = good.with_name("3-bar.md")
    good.rename(renamed)  # the contract still says reply 2-foo
    proc = run(tmp_path, [renamed, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode("utf-8")
    assert out.startswith("FAIL 4 %s:" % renamed) and "reply 3-bar" in out and out.count("\n") == 1


def test_argv_dispatch(tmp_path):
    assert run(tmp_path, [], mode=None).returncode == 2
    assert run(tmp_path, ["reply", "x"], mode=None).returncode == 2
