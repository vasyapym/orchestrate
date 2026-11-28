"""Fixture suite for brief-check.py — the brief refusals, the profile write, the two hand-over lines.

Style follows tests/test_extract_reply.py: the CLI always runs as a real
subprocess (sys.executable, capture_output), fixtures are disposable tmp_path
trees, and the host tree is never written by a test — the only files a run
touches are the round folder, profile and reply paths inside the tmp tree.

The fixtures fill the CURRENT declarations/brief-skeleton.md in place: every
<…> slot, the backticked reply template, and the contract's standalone marker
template block (=== begin <name> === / <the artifact, ONE ⏎-joined line> /
=== end <name> ===) are filled where they stand; nothing is appended that the
skeleton does not carry.
"""

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "brief-check.py"
SKELETON = SCRIPT.parent / "declarations" / "brief-skeleton.md"

SESSION = "ses_test_brief_check"
WINDOW = "6\u201310"  # en dash, as the skeleton's <N–M> slot expects
SESSION_UNSET = "<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"
DESIGN_PAIR = ["=== begin design ===", "=== end design ==="]


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


def make_good_brief(dir_path, name="2-foo.md", artifact=True):
    """The skeleton with every slot filled in place. artifact=False drops the
    contract's marker template block: an explicitly no-artifact contract."""
    stem = Path(name).stem
    text = skeleton_text()
    fills = [
        ("<one or two sentences; less is better>", "Shape the declarations layout."),
        ("<each with its path or source>", "- DECISION-1.md, adopted design part C"),
        ("<...>", "- none"),  # Assumptions and Open questions
        ("<files whole or in generous excerpts>", "- declarations/brief-skeleton.md, whole"),
        ("<what to return, in what order>", "the recommended design"),
        ("<LINES>", "350"),
        ("<N\u2013M>", WINDOW),  # the time-limit paragraph and the contract restatement
        ("`reply <n>-<slug>`", f"`reply {stem}`"),  # the concrete phrase, in the contract
        ("=== begin <name> ===", "=== begin design ==="),  # the marker block, in place
        ("<the artifact, ONE <BREAK>-joined line>", "the design, one physical line, breaks as U+23CE"),
        ("=== end <name> ===", "=== end design ==="),
    ]
    for old, new in fills:
        assert old in text, f"skeleton changed: {old!r} missing"
        text = text.replace(old, new)
    if not artifact:
        lines = text.split("\n")
        drop = {
            i
            for i, line in enumerate(lines)
            if line in DESIGN_PAIR or line.startswith("the design, one physical line")
        }
        text = "\n".join(line for i, line in enumerate(lines) if i not in drop)
    path = dir_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def good(tmp_path):
    """A good brief; the tool creates its round folder itself (finding 4)."""
    return make_good_brief(tmp_path)


def stat_state(path):
    st = path.stat()
    return {"mtime_ns": st.st_mtime_ns, "bytes": path.read_bytes()}


def harvest_tokens(harvest_line):
    """The HARVEST command's argv after the HARVEST: prefix, parsed the way sh would."""
    return shlex.split(harvest_line.split("HARVEST: ", 1)[1])


# ---------------------------------------------------------------------------
# the good brief


def test_good_brief_exit0_two_lines_and_profile(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stderr.decode()
    lines = proc.stdout.decode("utf-8").split("\n")
    assert len(lines) == 3 and lines[2] == ""  # exactly two lines, nothing else
    verdict, harvest = lines[0], lines[1]
    assert verdict == f"VERDICT: brief ok {good} {good.stat().st_size} window {WINDOW}"
    tokens = harvest_tokens(harvest)
    assert tokens[0] == "python3"
    assert tokens[1] == str(SCRIPT.parent / "extract-reply.py")
    assert tokens[2] == "reply 2-foo"
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    assert tokens[3] == str(profile)
    assert tokens[4:6] == ["--session", SESSION]
    assert tokens[8] == "--out" and tokens[9] == str(tmp_path / "round-1" / "replies" / "2-foo.md")
    assert abs(int(tokens[7]) - time.time()) < 120
    # the profile: 0600, right required_lines, right terminal, since recorded
    doc = json.loads(profile.read_text(encoding="utf-8"))
    assert doc == {
        "version": 1,
        "required_lines": DESIGN_PAIR,
        "terminal_line": "COMPLETE",
        "since": int(tokens[7]),
    }
    assert (profile.stat().st_mode & 0o777) == 0o600


def test_harvest_is_sh_safe_with_metachar_slug_and_spaced_round_dir(tmp_path):
    """Finding 5: a slug carrying $( ) and a spaced round dir travel as data —
    proven by shlex round-trip and by a real sh run."""
    good = make_good_brief(tmp_path, name="2-fo$(reboot)o.md")
    round_dir = tmp_path / "TD rounds" / "spares guard round"
    proc = run_cli(tmp_path, [good, "--round", str(round_dir)])
    assert proc.returncode == 0, proc.stderr.decode()
    tokens = harvest_tokens(proc.stdout.decode("utf-8").split("\n")[1])
    assert tokens[2] == "reply 2-fo$(reboot)o"
    assert tokens[3] == str(round_dir / "replies" / "2-fo$(reboot)o.md.profile.json")
    assert tokens[9] == str(round_dir / "replies" / "2-fo$(reboot)o.md")
    # the real shell must see the same argv: echo re-prints its data unchanged
    shell = subprocess.run(
        ["sh", "-c", "echo " + proc.stdout.decode("utf-8").split("\n")[1].split("HARVEST: ", 1)[1]],
        capture_output=True,
        timeout=30,
    )
    assert shell.returncode == 0
    assert shell.stdout.decode().strip() == " ".join(tokens)


def test_harvest_unset_session_named_explicitly(tmp_path, good):
    """Finding 5: never an empty --session; the missing value is named."""
    proc = run_cli(tmp_path, [good, "--round", "round-1"], session=None)
    assert proc.returncode == 0
    tokens = harvest_tokens(proc.stdout.decode("utf-8").split("\n")[1])
    assert tokens[4:6] == ["--session", SESSION_UNSET]


def test_json_success(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-1", "--json"])
    assert proc.returncode == 0, proc.stderr.decode()
    doc = json.loads(proc.stdout.decode("utf-8"))  # one JSON document, nothing else
    assert doc["ok"] is True
    assert doc["bytes"] == good.stat().st_size
    assert doc["window"] == WINDOW
    assert doc["phrase"] == "reply 2-foo"
    assert doc["profile_status"] == "written"
    assert doc["required_lines"] == DESIGN_PAIR
    assert doc["verdict_line"].startswith("VERDICT: brief ok ")
    assert doc["harvest_line"].startswith("HARVEST: python3 ")


def test_backticked_template_not_a_placeholder(tmp_path, good):
    """The contract's backticked `reply <n>-<slug>` template is not an unfilled
    slot when the concrete phrase stands in the contract too: exit 0."""
    text = good.read_text(encoding="utf-8") + "\nif unsure, echo the template `reply <n>-<slug>` back.\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


# ---------------------------------------------------------------------------
# finding 1 + 2: the live contract is the only source; quoted material supplies nothing


def test_quoted_skeleton_marker_pair_ignored(tmp_path, good):
    """A fenced copy of the skeleton carries whole-line <name> markers and its own
    contract heading; required_lines still derive only from the live contract."""
    text = good.read_text(encoding="utf-8") + (
        "\n## Context (the skeleton, quoted verbatim)\n\n"
        "```\n"
        + skeleton_text()
        + "\n```\n"
    )
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1", "--json"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    doc = json.loads(proc.stdout.decode("utf-8"))
    assert doc["required_lines"] == DESIGN_PAIR


def test_quoted_opener_does_not_rescue_dropped_opener(tmp_path, good):
    opener = skeleton_text().split("\n")[0]
    text = good.read_text(encoding="utf-8").replace(opener + "\n", "", 1)
    text += "\n## Context (the skeleton, quoted verbatim)\n\n```\n" + skeleton_text() + "\n```\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 1:" in proc.stdout.decode() and "opener" in proc.stdout.decode()


def test_quoted_phrase_does_not_rescue_contract_phrase(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("`reply 2-foo`", "`reply <n>-<slug>`", 1)
    text += "\n## Context (a prior brief, quoted verbatim)\n\n```\nFirst line, verbatim: reply 2-foo\n```\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 3:" in out and "reply 2-foo" in out and "contract" in out


def test_check4_reversed_pair_is_a_named_miss(tmp_path, good):
    """Finding 1: a begin must precede its end; the reversed pair cannot be cut."""
    lines = good.read_text(encoding="utf-8").split("\n")
    i = lines.index("=== begin design ===")
    lines[i : i + 3] = ["=== end design ===", "=== begin design ==="]  # reversed, artifact line gone
    good.write_text("\n".join(lines), encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 4:" in out and "end before begin" in out


def test_check8_no_artifact_contract_valid(tmp_path):
    """Finding 8: an explicitly no-artifact contract passes with required_lines [];
    the profile then checks phrase + terminal only (terminal_line satisfies
    extract-reply's "a check beyond the phrase" rule)."""
    good = make_good_brief(tmp_path, artifact=False)
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    doc = json.loads(profile.read_text(encoding="utf-8"))
    assert doc["required_lines"] == []
    assert doc["terminal_line"] == "COMPLETE"
    assert doc["since"] >= 0  # the phrase + terminal pair is a real check


def test_missing_contract_section_fails_every_contract_check(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("## Output contract\n", "", 1)
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    for number in (3, 4, 5):
        assert f"FAIL {number}:" in out
    assert out.count("no '## Output contract' section") == 3


# ---------------------------------------------------------------------------
# finding 4: the round folder is selected and created at compose time


def test_round_created_when_missing_explicit(tmp_path, good):
    proc = run_cli(tmp_path, [good, "--round", "round-9"])
    assert proc.returncode == 0, proc.stderr.decode()
    assert (tmp_path / "round-9" / "replies" / "2-foo.md.profile.json").is_file()


def test_round_created_when_missing_auto(tmp_path):
    solo = tmp_path / "solo"
    solo.mkdir()
    good = make_good_brief(solo)  # no round-<k> beside the brief
    proc = run_cli(solo, [good])
    assert proc.returncode == 0, proc.stderr.decode()
    assert (solo / "round-1" / "replies" / "2-foo.md.profile.json").is_file()


def test_round_path_taken_as_given(tmp_path, good):
    """Finding 4: an external directory travels as given — no round- prefixing."""
    external = tmp_path / "TD rounds" / "spares guard round"
    proc = run_cli(tmp_path, [good, "--round", str(external)])
    assert proc.returncode == 0, proc.stderr.decode()
    assert (external / "replies" / "2-foo.md.profile.json").is_file()
    assert list(tmp_path.glob("round-*")) == []  # nothing invented beside the brief


def test_round_auto_resolves_highest(tmp_path, good):
    (tmp_path / "round-1").mkdir()
    (tmp_path / "round-3").mkdir()
    proc = run_cli(tmp_path, [good])
    assert proc.returncode == 0, proc.stderr.decode()
    assert (tmp_path / "round-3" / "replies" / "2-foo.md.profile.json").is_file()
    assert not (tmp_path / "round-1" / "replies").exists()  # only the selected folder is armed


# ---------------------------------------------------------------------------
# finding 19: the profile records the first run's --since; a noop reuses it


def test_profile_noop_on_rerun_reuses_recorded_since(tmp_path, good):
    first = run_cli(tmp_path, [good, "--round", "round-1"])
    assert first.returncode == 0
    since_first = harvest_tokens(first.stdout.decode("utf-8").split("\n")[1])[7]
    profile = tmp_path / "round-1" / "replies" / "2-foo.md.profile.json"
    before = stat_state(profile)
    time.sleep(1.1)  # a re-stamp would advance --since by a visible second
    second = run_cli(tmp_path, [good, "--round", "round-1"])
    assert second.returncode == 0, second.stderr.decode()
    tokens = harvest_tokens(second.stdout.decode("utf-8").split("\n")[1])
    assert tokens[4:6] == ["--session", SESSION]
    assert tokens[7] == since_first  # the recorded hand-over time, not a re-stamp
    assert stat_state(profile) == before  # mtime untouched, bytes untouched


def test_profile_noop_on_identical_hand_formatted_profile(tmp_path, good):
    """A pre-existing profile holding the identical check object (no recorded
    since) is a no-op even when its byte layout is the hand-written one."""
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


def test_failed_checks_create_nothing(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("=== end design ===\n", "")
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert not (tmp_path / "round-1").exists()  # the round folder is armed only after the checks


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


def test_check1_window_must_be_restated_in_contract(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace(f"hard stop at {WINDOW} minutes", "hard stop at 99 minutes")
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 1:" in out and f"window {WINDOW} not restated" in out


def test_check1_blank_line_before_paragraph_passes(tmp_path, good):
    """Finding 17's scenario: a blank line inserted before the time-limit
    paragraph must not break the check - the paragraph is located by prefix."""
    para = next(
        line for line in skeleton_text().split("\n") if line.startswith("There's a")
    )
    text = good.read_text(encoding="utf-8").replace(para + "\n", para + "\n\n", 1)
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()


def test_check1_paragraph_moved_into_contract_is_a_named_miss(tmp_path, good):
    """The prose head is the paragraph's only home: a copy shifted into the
    contract section while the head loses it is the named check-1 miss."""
    para = next(
        line
        for line in good.read_text(encoding="utf-8").split("\n")
        if line.startswith("There's a")
    )
    text = good.read_text(encoding="utf-8").replace(para + "\n", "", 1)
    text += para + "\n"  # EOF is inside the contract section
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 1:" in out and "prose head" in out


def test_skeleton_head_layout_tolerated_by_skeleton_parts():
    """The locator reads the skeleton's prose head, not a fixed index: blank
    lines, reordering within the head and extra prose all resolve; absence
    from the head is a named exit-2 skeleton break."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("brief_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    lines = skeleton_text().split("\n")
    _opener, base_rx = mod.skeleton_parts(skeleton_text())

    shifted = lines[:2] + ["", ""] + lines[2:]  # a blank line before the paragraph
    _opener, rx = mod.skeleton_parts("\n".join(shifted))
    assert rx.pattern == base_rx.pattern

    extra = lines[:1] + ["some extra head prose"] + lines[1:]  # extra prose in the head
    _opener, rx = mod.skeleton_parts("\n".join(extra))
    assert rx.pattern == base_rx.pattern

    demoted = lines[:1] + ["## The task"] + lines[1:]  # the paragraph below the first heading
    try:
        mod.skeleton_parts("\n".join(demoted))
        raise AssertionError("a head without the paragraph must be a named exit-2 break")
    except mod.Fail as exc:
        assert "prose head" in str(exc)


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


def test_check3_phrase_missing_from_contract(tmp_path):
    good = make_good_brief(tmp_path, name="2-foo.md")  # the contract says reply 2-foo
    renamed = good.with_name("3-bar.md")  # the file is renamed after the fill
    good.rename(renamed)
    proc = run_cli(tmp_path, [renamed, "--round", "round-1"])
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
    text = good.read_text(encoding="utf-8") + "\n=== begin design ===\n=== end design ===\n"
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 4:" in out and "occurs 2 times" in out


def test_check5_sentinel_missing(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("COMPLETE", "DONE")  # the contract mention too
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 5:" in proc.stdout.decode() and "COMPLETE" in proc.stdout.decode()


def test_check5_incomplete_does_not_satisfy(tmp_path, good):
    text = good.read_text(encoding="utf-8").replace("End with COMPLETE on its own line", "End with INCOMPLETE on its own line")
    good.write_text(text, encoding="utf-8")
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    out = proc.stdout.decode()
    assert "FAIL 5:" in out and "terminal instruction" in out


# ---------------------------------------------------------------------------
# finding 13: CRLF is a line terminator for every structural check


def test_crlf_brief_passes_with_byte_fidelity(tmp_path):
    good = make_good_brief(tmp_path, name="3-crlf.md")
    good.write_bytes(good.read_bytes().replace(b"\n", b"\r\n"))
    proc = run_cli(tmp_path, [good, "--round", "round-1", "--json"])
    assert proc.returncode == 0, proc.stdout.decode() + proc.stderr.decode()
    doc = json.loads(proc.stdout.decode("utf-8"))
    assert doc["bytes"] == good.stat().st_size  # the original bytes, carriage returns included
    assert doc["required_lines"] == DESIGN_PAIR
    assert doc["phrase"] == "reply 3-crlf"


def test_crlf_still_catches_a_dropped_marker(tmp_path):
    good = make_good_brief(tmp_path, name="3-crlf.md")
    good.write_bytes(good.read_bytes().replace(b"\n", b"\r\n").replace(b"=== end design ===\r\n", b""))
    proc = run_cli(tmp_path, [good, "--round", "round-1"])
    assert proc.returncode == 1
    assert "FAIL 4:" in proc.stdout.decode() and "begin without end" in proc.stdout.decode()
