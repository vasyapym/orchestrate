#!/usr/bin/env python3
"""brief-check - refuse a brief that is not the skeleton, then file the harvest profile.

    python3 brief-check.py <brief.md> [--round round-k] [--json]

The brief's own output contract is the single source of the structural checks:
the contract section is the prose after the LAST "## Output contract" heading
(up to the next "##" heading), outside fenced/quoted material - a fenced copy
of the skeleton or of a prior brief is quoted matter and supplies nothing.

Checks (any failure = exit 1; every failed check is named by number and one
clause, never the file's contents):

  1. byte-equal verbatim presence: the skeleton's line 1 (the chat-model
     opener) appears as a whole physical line, byte-equal, and the filled
     time-limit paragraph - the skeleton's prose-head paragraph (located by
     its "There's a" prefix among the lines before the first "## " heading,
     per the design's own order: second verbatim block, right after the
     opener) with the <N-M> slot replaced by filled digits - appears as a
     whole physical line within the brief's own prose head. Blank lines,
     reordering within the head and extra prose do not move it; its absence
     from the head is the named miss. Both scans run on the brief's prose,
     never satisfied by quoted material. The filled digits are echoed on
     the VERDICT line and must be restated in the contract section.
  2. no unfilled placeholders. The rule, precisely: the scan runs on prose
     only - physical lines outside fenced blocks and outside inline-code
     spans. A fenced block opens at a line holding three or more backticks
     or tildes (up to three leading spaces, an optional info string; a
     backtick fence's info string may not hold a backtick) and closes at a
     line of the same character at least as long on its own. Fenced lines
     are quoted material - a law file quoted verbatim legitimately carries
     <...>-shaped template tokens (<this-machine>, <project>) - so they are
     exempt; the skeleton's own fill placeholders all live in prose, so the
     prose-only rule keeps the check's teeth. Within prose, first delete
     every inline-code span - the text between a pair of backticks on that
     line (regex `[^`\\n]*`, applied pairwise left to right; an unmatched
     backtick deletes nothing) - then search the stripped line with the
     regex `<[^>\\n]{1,80}>`. Any match is an unfilled placeholder. The
     contract's backticked template markers (`reply <n>-<slug>`) survive
     because they live inside backticks. A fence that never closes fails
     the check: the rest of the file is treated as fenced, and the unclosed
     fence is named (this decision is brief-check's).
  3. the reply phrase is named: the brief's filename stem is <n>-<slug>
     (digits, one dash, a non-empty slug) and the concrete string
     "reply <n>-<slug>" with the real values occurs in the contract
     section - a mention in quoted material does not count.
  4. markers: the marker template block that stands as whole lines in the
     contract section is the brief's live output contract; required_lines
     are its marker lines in file order, begins and ends. Begin-before-end
     holds: an end must follow its begin, and a reversed or stray pair is a
     named miss; every contract marker line occurs exactly once. Zero pairs
     is a valid explicitly no-artifact contract (required_lines empty; the
     profile then checks phrase + terminal only, which satisfies
     extract-reply's "a check beyond the phrase" rule via terminal_line).
  5. the terminal instruction: the token COMPLETE, word-bounded, occurs in
     the contract section - INCOMPLETE does not satisfy it.

Lines are terminated by LF or CRLF for every structural check (the file's
bytes are never rewritten; byte length is reported as-is).

On success (exit 0) the round folder is selected - --round as given (a
bare round-k or k resolves beside the brief; any path travels as given),
else the highest round-<k> directory numerically beside the brief, else
round-1 - and created when missing: a bare mkdir of the folder and its
replies/, no snapshot machinery. The profile
<round>/replies/<n>-<slug>.md.profile.json is then written (0600,
no-clobber): an existing profile holding the identical check object
(everything but the recorded "since", which is provenance that legitimately
differs per run) is an exit-0 no-op with mtime untouched; an existing
different or unreadable profile is exit 2, untouched. The profile records
the first run's --since as its "since" field; a no-op regeneration reuses
the recorded value in the printed HARVEST line, so recovering a hand-over
after the paste stays in bounds. stdout then carries exactly two lines:

    VERDICT: brief ok <brief-path> <byte-length> window <digits>
    HARVEST: python3 <skill-dir>/extract-reply.py <phrase> <profile> --session <session> --since <epoch-seconds> --out <round>/replies/<n>-<slug>.md

Every variable part of the HARVEST command is rendered through
shlex.quote, so spaces and shell metacharacters travel as data to sh and
python3. <skill-dir> is the directory containing brief-check.py; <session>
is $OPENCODE_SESSION_ID from the environment when set, else the explicit
placeholder "<OPENCODE_SESSION_ID unset - ask the orchestrator>" - never
an empty --session. Profile and --out paths are absolute. With --json, one
JSON document with the same facts is printed instead (on failures too).

Exit codes: 0 ok; 1 a failed check (nothing written); 2 usage, unreadable
input, a broken skeleton, a round folder that cannot be created, or a
profile conflict (nothing written). stdout carries results only; stderr
carries diagnostics only. Single file. Standard library only. Python 3.8+.
"""

import argparse
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_FAIL = 2

PROFILE_VERSION = 1
SKELETON_REL = ("declarations", "brief-skeleton.md")
SLOT = "<N\u2013M>"  # the skeleton's one window slot (en dash)
WINDOW_RE = r"(\d+(?:\s*\u2013\s*\d+)?)"  # the filled slot: digits, optionally digits-en-dash-digits
SENTINEL = "COMPLETE"
HEAD_PARA_PREFIX = "There's a"  # the time-limit paragraph's prefix in the skeleton's prose head
SENTINEL_RE = re.compile(r"\bCOMPLETE\b")  # INCOMPLETE does not satisfy the terminal instruction
MARKER_BEGIN_RE = re.compile(r"^=== begin (.+) ===$")
MARKER_END_RE = re.compile(r"^=== end (.+) ===$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
PLACEHOLDER_RE = re.compile(r"<[^>\n]{1,80}>")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CONTRACT_HEADING_RE = re.compile(r"^## Output contract\s*$")
ANY_H2_RE = re.compile(r"^## ")
STEM_RE = re.compile(r"(\d+)-(.+)")
ROUND_NAME_RE = re.compile(r"round-(\d+)")
SESSION_UNSET = "<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"


class Fail(Exception):
    """Exit 2: a named failure cause (nothing written)."""


class Refused(Exception):
    """Exit 1: failed checks (nothing written)."""

    def __init__(self, failures):
        super().__init__(failures)
        self.failures = failures  # list of (check_id, clause); check_id is a number


# ---------------------------------------------------------------------------
# reading


def read_text(path, what):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise Fail(f"cannot read {what} {path}: {exc}")
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Fail(f"{what} {path} is not valid UTF-8: {exc}")


def split_lines(text):
    """Structural lines: LF or CRLF terminators both; the original bytes stay untouched."""
    return re.split(r"\r\n|\n", text)


def head_lines(lines):
    """The prose head: the lines before the first line starting with "## "."""
    out = []
    for line in lines:
        if ANY_H2_RE.match(line):
            break
        out.append(line)
    return out


def skeleton_parts(skeleton_text):
    """(opener, window_regex) from the skeleton; a broken skeleton is exit 2.
    The window paragraph is located in the skeleton's prose head by its
    "There's a" prefix - blank lines, reordering within the head and extra
    prose do not move it."""
    lines = split_lines(skeleton_text)
    if not lines or not lines[0]:
        raise Fail("skeleton is broken: the first line must be the chat-model opener")
    candidates = [line for line in head_lines(lines) if line.startswith(HEAD_PARA_PREFIX)]
    if len(candidates) != 1 or candidates[0].count(SLOT) != 1:
        raise Fail(
            "skeleton is broken: the prose head must hold exactly one"
            f" {HEAD_PARA_PREFIX!r} time-limit paragraph with exactly one {SLOT} slot"
        )
    left, right = candidates[0].split(SLOT)
    return lines[0], re.compile(re.escape(left) + WINDOW_RE + re.escape(right))


# ---------------------------------------------------------------------------
# prose, fences, contract


def scan_fences(lines):
    """(prose, unclosed): prose is the (number, line) list outside fenced blocks;
    unclosed is (number, fence_char) when a fence opens and never closes."""
    prose = []
    open_number = None
    open_char = open_len = None
    for number, line in enumerate(lines, 1):
        if open_char is None:
            m = FENCE_OPEN_RE.match(line)
            if m and not (m.group(1)[0] == "`" and "`" in line[m.end():]):
                open_number, open_char, open_len = number, m.group(1)[0], len(m.group(1))
            else:
                prose.append((number, line))
        elif re.match(r"^ {0,3}(%s{%d,})\s*$" % (re.escape(open_char), open_len), line):
            open_number = open_char = open_len = None
        # fenced lines are quoted material: skipped
    if open_char is None:
        return prose, None
    return prose, (open_number, open_char)


def contract_section(prose):
    """The brief's own contract: prose lines after the LAST "## Output contract"
    heading, up to the next "##" heading; None when the heading is absent."""
    last = None
    for index, (_number, line) in enumerate(prose):
        if CONTRACT_HEADING_RE.match(line):
            last = index
    if last is None:
        return None
    out = []
    for _number, line in prose[last + 1:]:
        if ANY_H2_RE.match(line):
            break
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# checks


def check_verbatim(prose, contract, opener, window_rx):
    """Check 1. Returns (clause_or_None, window_or_None). Quoted material supplies
    nothing; the filled time-limit paragraph must stand in the brief's prose head."""
    texts = [line for _number, line in prose]
    if opener not in texts:
        return "opener line not present byte-equal in the brief's own prose", None
    head = head_lines(texts)
    windows = [m.group(1) for line in head for m in [window_rx.fullmatch(line)] if m]
    if not windows:
        return "time-limit paragraph missing from the prose head or altered beyond the window slot", None
    window = windows[0]
    if contract is not None and window not in "\n".join(contract):
        return f"window {window} not restated in the contract section", window
    return None, window


def check_placeholders(lines):
    """Check 2. Returns a clause or None; the scan runs on prose outside fences
    and inline code; an unclosed fence is the clause (the fenced tail is exempt)."""
    prose, unclosed = scan_fences(lines)
    if unclosed is not None:
        number, char = unclosed
        return (
            f"fence opened at line {number} never closes: the rest of the file"
            f" is treated as fenced ({char} fence)"
        )
    leftovers = []
    for number, line in prose:
        hit = PLACEHOLDER_RE.search(INLINE_CODE_RE.sub("", line))
        if hit:
            leftovers.append((number, hit.group(0)))
    if not leftovers:
        return None
    number, token = leftovers[0]
    return f"{len(leftovers)} unfilled placeholder(s) outside inline code, first {token} (line {number})"


def check_phrase(contract, stem):
    """Check 3. Returns (clause_or_None, phrase_or_None); the concrete phrase must
    stand in the contract section, not merely somewhere in quoted material."""
    m = STEM_RE.fullmatch(stem)
    if not m or not m.group(2).strip():
        return f"filename stem is not <n>-<slug>: {stem!r}", None
    phrase = "reply " + stem
    if contract is None:
        return "no '## Output contract' section in the brief's own prose", None
    if phrase not in "\n".join(contract):
        return f"reply phrase not named in the contract section: {phrase!r}", None
    return None, phrase


def check_markers(contract):
    """Check 4. Returns (clause_or_None, required_lines): the live contract's marker
    template block in file order; begin-before-end holds; zero pairs is a valid
    explicitly no-artifact contract."""
    if contract is None:
        return "no '## Output contract' section in the brief's own prose", []
    markers = [line for line in contract if MARKER_BEGIN_RE.match(line) or MARKER_END_RE.match(line)]
    seen = {}
    for line in markers:
        seen[line] = seen.get(line, 0) + 1
    for line, count in seen.items():
        if count > 1:
            return f"marker line occurs {count} times in the contract: {line!r}", []
    open_names = []
    for line in markers:
        m = MARKER_BEGIN_RE.match(line)
        if m:
            if m.group(1) in open_names:
                return f"begin without end: {m.group(1)!r}", []
            open_names.append(m.group(1))
        else:
            name = MARKER_END_RE.match(line).group(1)
            if name not in open_names:
                return f"end before begin: {name!r}", []
            open_names.remove(name)
    if open_names:
        return f"begin without end: {open_names[0]!r}", []
    return None, markers


def check_sentinel(contract):
    """Check 5: the terminal instruction in the contract; word-bounded."""
    if contract is None:
        return "no '## Output contract' section in the brief's own prose"
    if not any(SENTINEL_RE.search(line) for line in contract):
        return "terminal instruction missing: COMPLETE not named in the contract section"
    return None


def run_checks(text, skeleton_text, stem):
    """All five checks. Returns (failures, facts dict); facts are complete only when no check failed."""
    lines = split_lines(text)
    prose, _unclosed = scan_fences(lines)
    contract = contract_section(prose)
    opener, window_rx = skeleton_parts(skeleton_text)
    failures = []
    facts = {}

    clause, window = check_verbatim(prose, contract, opener, window_rx)
    if clause:
        failures.append((1, clause))
    facts["window"] = window

    clause = check_placeholders(lines)
    if clause:
        failures.append((2, clause))

    clause, phrase = check_phrase(contract, stem)
    if clause:
        failures.append((3, clause))
    facts["phrase"] = phrase

    clause, required_lines = check_markers(contract)
    if clause:
        failures.append((4, clause))
    facts["required_lines"] = required_lines

    clause = check_sentinel(contract)
    if clause:
        failures.append((5, clause))

    return failures, facts


# ---------------------------------------------------------------------------
# round folder and profile


def resolve_round(brief_dir, round_arg):
    """The active round folder. --round as given: a bare round-k or k resolves beside
    the brief, any path travels as given; else the highest round-<k> beside the brief,
    else round-1. A missing folder is created at compose time: a bare mkdir of the
    folder and its replies/, no snapshot machinery."""
    if round_arg is not None:
        if ROUND_NAME_RE.fullmatch(round_arg) or re.fullmatch(r"\d+", round_arg):
            name = round_arg if round_arg.startswith("round-") else "round-" + round_arg
            path = brief_dir / name
        else:
            path = Path(round_arg)
    else:
        path, best_k = None, -1
        try:
            entries = sorted(brief_dir.iterdir())
        except OSError as exc:
            raise Fail(f"cannot list {brief_dir}: {exc}")
        for entry in entries:
            m = ROUND_NAME_RE.fullmatch(entry.name)
            if m and entry.is_dir() and int(m.group(1)) > best_k:
                path, best_k = entry, int(m.group(1))
        if path is None:
            path = brief_dir / "round-1"
    try:
        path.mkdir(parents=True, exist_ok=True)
        (path / "replies").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise Fail(f"cannot create round folder {path}: {exc}")
    return path


def write_profile(profile_path, profile, since):
    """No-clobber write, 0600. Identity ignores the recorded "since" (provenance that
    legitimately differs per run): an existing profile holding the identical check
    object is a no-op and its recorded since is reused; different or unreadable -> exit 2.
    Returns (status, since_used)."""
    full = dict(profile, since=since)
    data = (json.dumps(full, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if profile_path.exists():
        try:
            existing = json.loads(profile_path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise Fail(f"profile conflict: existing profile is unreadable: {profile_path}: {exc}")
        if not isinstance(existing, dict):
            raise Fail(f"profile conflict: existing profile is not a JSON object: {profile_path}")
        recorded = existing.pop("since", None)
        if existing != profile:
            raise Fail(f"profile conflict: existing profile differs: {profile_path}")
        if not isinstance(recorded, int) or recorded <= 0:
            recorded = since
        return "noop", recorded
    try:
        os.makedirs(profile_path.parent, exist_ok=True)
        fd = os.open(str(profile_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise Fail(f"cannot write {profile_path}: {exc}")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise Fail(f"cannot write {profile_path}: {exc}")
    return "written", since


# ---------------------------------------------------------------------------
# cli


def build_parser():
    parser = argparse.ArgumentParser(
        prog="brief-check.py",
        description="Refuse a brief that is not the skeleton; write the harvest profile; print the two hand-over lines.",
    )
    parser.add_argument("brief", help="path to the composed brief markdown")
    parser.add_argument(
        "--round",
        help="round folder: round-k or bare k beside the brief, or a directory path as given;"
        " default: the highest round-<k> beside the brief, else round-1; created when missing",
    )
    parser.add_argument("--json", action="store_true", help="print one JSON document with the same facts instead")
    return parser


def run(args):
    """Return (exit_code, stdout_text, json_doc_or_None) after any write has happened."""
    brief_path = Path(args.brief)
    raw, text = read_text(brief_path, "brief")
    skill_dir = Path(__file__).resolve().parent
    _skeleton_raw, skeleton_text = read_text(skill_dir / SKELETON_REL[0] / SKELETON_REL[1], "skeleton")

    failures, facts = run_checks(text, skeleton_text, brief_path.stem)
    if failures:
        raise Refused(failures)

    round_dir = resolve_round(brief_path.parent, args.round)
    profile_path = round_dir / "replies" / (brief_path.name + ".profile.json")
    out_path = round_dir / "replies" / brief_path.name
    profile = {
        "version": PROFILE_VERSION,
        "required_lines": facts["required_lines"],
        "terminal_line": SENTINEL,
    }
    now = int(time.time())
    status, since = write_profile(profile_path, profile, now)

    session = os.environ.get("OPENCODE_SESSION_ID") or SESSION_UNSET
    skill_dir_str = str(skill_dir)
    profile_str = os.path.abspath(str(profile_path))
    out_str = os.path.abspath(str(out_path))
    verdict_line = f"VERDICT: brief ok {args.brief} {len(raw)} window {facts['window']}"
    harvest_args = shlex.join(
        [
            "python3",
            str(skill_dir / "extract-reply.py"),
            facts["phrase"],
            profile_str,
            "--session",
            session,
            "--since",
            str(since),
            "--out",
            out_str,
        ]
    )
    harvest_line = "HARVEST: " + harvest_args
    doc = {
        "ok": True,
        "brief": args.brief,
        "bytes": len(raw),
        "window": facts["window"],
        "phrase": facts["phrase"],
        "round": os.path.abspath(str(round_dir)),
        "profile": profile_str,
        "profile_status": status,
        "out": out_str,
        "session": session,
        "since": since,
        "required_lines": facts["required_lines"],
        "terminal_line": SENTINEL,
        "verdict_line": verdict_line,
        "harvest_line": harvest_line,
    }
    return EXIT_OK, verdict_line + "\n" + harvest_line + "\n", doc


def dump_json(doc):
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code, out_text, doc = run(args)
    except Refused as exc:
        if args.json:
            doc = {
                "ok": False,
                "failures": [{"check": check_id, "reason": clause} for check_id, clause in exc.failures],
            }
            sys.stdout.write(dump_json(doc))
        else:
            for check_id, clause in exc.failures:
                sys.stdout.write(f"FAIL {check_id}: {clause}\n")
        sys.stderr.write(f"brief-check: exit 1: {len(exc.failures)} failure(s): nothing written\n")
        return EXIT_REFUSED
    except Fail as exc:
        if args.json:
            sys.stdout.write(dump_json({"ok": False, "error": str(exc)}))
        sys.stderr.write(f"brief-check: error: {exc}\n")
        return EXIT_FAIL
    if args.json and doc is not None:
        sys.stdout.write(dump_json(doc))
    elif out_text:
        sys.stdout.write(out_text)
    return code


if __name__ == "__main__":
    sys.exit(main())
