"""Fixture suite for brief-check.py — the brief refusals, the profile write, the two hand-over lines.

Style follows tests/test_extract_reply.py: the CLI always runs as a real
subprocess (sys.executable, capture_output), fixtures are disposable tmp_path
trees, and the host tree is never written by a test — the only files a run
touches are the profile and reply paths inside the tmp tree.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "brief-check.py"
SKELETON = SCRIPT.parent / "declarations" / "brief-skeleton.md"

SESSION = "ses_test_brief_check"
WINDOW = "6\u201310"  # en dash, as the skeleton's <N–M> slot expects


# ---------------------------------------------------------------------------
# fixtures and helpers


def skeleton_text():
    return SKELETON.read_text(encoding="utf-8")


def run_cli(tmp_path, args, session=SESSION):
    """Real subprocess; OPENCODE_SESSION_ID controlled; cwd is the tmp tree."""
    env = dict(os.environ)
    env.pop("OPENCODE_SESSION_ID", None)
    if session is not None:
        env["OPENCODE_SESSION_ID"] = session
    cmd = [sys.executable, str(SCRIPT)] + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, env=env, timeout=120, cwd=str(tmp_path))


def make_good_brief(dir_path, name="2-foo.md"):
    """The skeleton, every placeholder filled minimally, one begin/end marker pair,
    the phrase named per the filename, COMPLETE last. The contract's backticked
    template markers (`reply <n>-<slug>`, `=== begin <name> ===`) stay as they are."""
    text = skeleton_text()
    text = text.replace("<one or two sentences; less is better>", "Shape the declarations layout.")
    text = text.replace("<each with its path or source>", "- DECISION-1.md, adopted design part C")
    text = text.replace("<...>", "- none")  # Assumptions and Open questions
    text = text.replace("<files whole or in generous excerpts>", "- declarations/brief-skeleton.md, whole")
    text = text.replace("<what to return, in what order>", "the recommended design")
    text = text.replace("<LINES>", "350")
    text = text.replace("<N\u2013M>", WINDOW)  # the time-limit paragraph and the contract restatement
    assert "reply <n>-<slug>" in text and "=== begin <name> ===" in text  # templates survive
    text += (
        "\nStage 1 of 1: the design block travels between its marker lines:\n"
        "\n=== begin design ===\n"
        "the design, one physical line, breaks as U+23CE\n"
        "=== end design ===\n"
        "\nFirst line of the reply, verbatim: reply 2-foo\n"
        "\nCOMPLETE\n"
    )
    path = dir_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def good(tmp_path):
    """A good brief in a brief folder with an existing round-1; returns its path."""
    (tmp_path / "round-1").mkdir()
    return make_good_brief(tmp_path)


def stat_state(path):
    st = path.stat()
    return {"mtime_ns": st.st_mtime_ns, "bytes": path.read_bytes()}


# ---------------------------------------------------------------------------
# the good brief


def test_good_brief_exit0_two_lines_and_profile(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stderr.decode()
    out = proc.stdout.decode("utf-8")
    lines = out.split("\n")
    assert len(lines) == 3 and lines[2] == ""  # exactly two lines, nothing else
    verdict, harvest = lines[0], lines[1]
    assert verdict == f"VERDICT: brief ok {good} {good.stat().st_size} window {WINDOW}"
    assert harvest.startswith("HARVEST: python3 ")
    assert '/extract-reply.py "reply 2-foo"' in harvest
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    assert str(profile) in harvest
    assert "--out " + str(tmp_path / "round-1" / "replies" / "2-foo.md") in harvest
    assert f"--session {SESSION}" in harvest
    since = int(harvest.split("--since ")[1].split(" ")[0])
    assert abs(since - time.time()) < 120
    # the profile: 0600, right required_lines, right terminal
    doc = json.loads(profile.read_text(encoding="utf-8"))
    assert doc == {
        "version": 1,
        "required_lines": ["=== begin design ===", "=== end design ==="],
        "terminal_line": "COMPLETE",
    }
    assert (profile.stat().st_mode & 0o777) == 0o600


def test_harvest_session_default_is_literal(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-1"], session=None)
    assert proc.returncode == 0
    harvest = proc.stdout.decode("utf-8").split("\n")[1]
    assert "--session $OPENCODE_SESSION_ID " in harvest


def test_json_success(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-1", "--json"])
    assert proc.returncode == 0, proc.stderr.decode()
    doc = json.loads(proc.stdout.decode("utf-8"))  # one JSON document, nothing else
    assert doc["ok"] is True
    assert doc["bytes"] == good.stat().st_size
    assert doc["window"] == WINDOW
    assert doc["phrase"] == "reply 2-foo"
    assert doc["profile_status"] == "written"
    assert doc["required_lines"] == ["=== begin design ===", "=== end design ==="]
    assert doc["verdict_line"].startswith("VERDICT: brief ok ")
    assert doc["harvest_line"].startswith("HARVEST: python3 ")


def test_backticked_templates_are_not_placeholders(tmp_path, good):
    # The contract's backticked `reply <n>-<slug>` / `=== begin <name> ===` markers are
    # not unfilled slots when the real phrase is present elsewhere: exit 0.
    text = good.read_text(encoding="utf-8")
    assert "`reply <n>-<slug>`" in text and "`=== begin <name> ===`" in text
    assert "reply 2-foo" in text
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


def test_round_auto_resolves_highest(tmp_path, good):
    (tmp_path / "round-3").mkdir()  # round-1 comes from the fixture
    proc = run_cli(tmp_path, [good])
    assert proc.returncode == 0, proc.stderr.decode()
    assert (tmp_path / "round-3" / "replies" / "2-foo.md.profile.json").is_file()
    assert not (tmp_path / "round-1" / "replies").exists()


def test_profile_noop_on_rerun(tmp_path, good):
    assert run_cli(tmp_path, [good, "--round", "round-1"]).returncode == 0
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    before = stat_state(profile)
    time.sleep(0.02)  # a coarse fs clock needs a gap to make an mtime touch visible
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stderr.decode()
    assert len(proc.stdout.decode().strip().split("\n")) == 2
    assert stat_state(profile) == before  # mtime untouched, bytes untouched


def test_profile_noop_on_identical_hand_formatted_profile(tmp_path, good):
    """A pre-existing profile holding the identical JSON object is a no-op even
    when its byte layout is the hand-written one."""
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        '{\n  "version": 1,\n  "required_lines": ["=== begin design ===", "=== end design ==="],\n'
        '  "terminal_line": "COMPLETE"\n}\n',
        encoding="utf-8",
    )
    before = stat_state(profile)
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stderr.decode()
    assert stat_state(profile) == before


def test_profile_no_clobber_on_different_profile(tmp_path, good):
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text('{"version": 1, "required_lines": [], "terminal_line": "DONE"}\n', encoding="utf-8")
    before = stat_state(profile)
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 2
    assert "conflict" in proc.stderr.decode()
    assert proc.stdout.decode() == ""
    assert stat_state(profile) == before  # untouched


def test_failed_checks_write_nothing(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("=== end design ===\n", "")
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert not (tmp_path / "round-1" / "replies").exists()


# ---------------------------------------------------------------------------
# one refusal per check — every failed check named by number


def test_check1_opener_altered(tmp_path, good):
    opener = skeleton_text().split("\n")[0]
    text = good.read_text(encoding="utf-8").replace(opener, opener.replace("no agentic", "no agent-ic"))
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 1:" in proc.stdout.decode()
    assert "opener" in proc.stdout.decode()


def test_check1_and_check2_window_slot_unfilled(tmp_path, good):
    para = skeleton_text().split("\n")[2]  # the unfilled time-limit paragraph
    filled = para.replace("<N\u2013M>", WINDOW)
    text = good.read_text(encoding="utf-8").replace(filled, para)
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 1:" in out and "time-limit" in out
    assert "FAIL 2:" in out and "<N\u2013M>" in out  # both failed checks named


def test_check2_leftover_placeholder_outside_backticks(tmp_path, good):
    text = good.read_text(encoding="utf-8") + "\npull the roster from <project> first.\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 2:" in out and "<project>" in out
    assert "FAIL 1:" not in out and "FAIL 3:" not in out  # only the failed check named


def test_check2_tokens_inside_fenced_block_exempt(tmp_path, good):
    """A Context-style fence quoting law files verbatim: bare <...>-shaped
    template tokens inside it are quoted material, not unfilled slots."""
    text = good.read_text(encoding="utf-8") + (
        "\n## Context (quoted verbatim)\n\n"
        "```declarations/jobs.md\n"
        "file the box job as jobs/open/<this-machine>-<project>.md\n"
        "the first line of the reply, verbatim: reply <n>-<slug>\n"
        "```\n"
    )
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


def test_check2_same_token_in_prose_still_fails(tmp_path, good):
    text = good.read_text(encoding="utf-8") + "\nfile the box job as jobs/open/<this-machine>.md\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 2:" in out and "<this-machine>" in out


def test_check2_unclosed_fence_reported(tmp_path, good):
    """An unclosed fence fails check 2 naming the fence; the fenced tail is
    exempt, so a token after the fence adds no second clause."""
    text = good.read_text(encoding="utf-8") + (
        "\n## Context (quoted verbatim)\n\n"
        "```\n"
        "the quoted law carries <project> tokens\n"
    )
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 2:" in out and "never closes" in out
    assert "<project>" not in out  # fenced tail exempt; the fence is the clause


def test_check3_wrong_filename_stem(tmp_path):
    good = make_good_brief(tmp_path, name="foot.md")  # stem "foot" is not <n>-<slug>
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 3:" in proc.stdout.decode() and "<n>-<slug>" in proc.stdout.decode()


def test_check3_phrase_missing(tmp_path):
    good = make_good_brief(tmp_path, name="3-bar.md")  # stem valid, brief names reply 2-foo
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 3:" in out and "reply 3-bar" in out


def test_check4_begin_without_end(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("=== end design ===\n", "")
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 4:" in out and "begin without end" in out


def test_check4_duplicate_marker_line(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace(
        "COMPLETE\n", "=== begin design ===\n=== end design ===\n\nCOMPLETE\n"
    )
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 4:" in out and "occurs 2 times" in out


def test_check5_sentinel_missing(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("COMPLETE", "DONE")  # contract mention too
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 5:" in proc.stdout.decode() and "COMPLETE" in proc.stdout.decode()


# ---------------------------------------------------------------------------
# round folder


def test_round_folder_missing_explicit(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-9"])
    assert proc.returncode == 1
    assert "FAIL round:" in proc.stdout.decode() and "round-9" in proc.stdout.decode()


def test_round_folder_missing_auto(tmp_path):
    solo = tmp_path / "solo"
    solo.mkdir()
    good = make_good_brief(solo)  # a brief folder with no round-<k> beside it
    proc = run_cli(solo, [good])
    assert proc.returncode == 1
    assert "FAIL round:" in proc.stdout.decode() and "no round-<k>" in proc.stdout.decode()
