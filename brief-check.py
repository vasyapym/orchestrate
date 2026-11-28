#!/usr/bin/env python3
"""brief-check - refuse a brief that is not the skeleton, then file the harvest profile.

    python3 brief-check.py <brief.md> [--round round-k] [--json]

Checks (any failure = exit 1; every failed check is named by number and one
clause, never the file's contents):

  1. byte-equal verbatim presence: the brief contains the skeleton's line 1
     (the chat-model opener) as a whole physical line, byte-equal; and the
     skeleton's line 3 (the time-limit paragraph) as a whole physical line
     with exactly one difference - the <N-M> slot replaced by filled window
     digits. The filled digits are echoed on the VERDICT line.
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
     output contract's backticked template markers (`reply <n>-<slug>`,
     `=== begin <name> ===`) survive because they live inside backticks:
     they are markers the specialist must echo, not unfilled slots. A fence
     that never closes fails the check: the rest of the file is treated as
     fenced, and the unclosed fence is named (this decision is brief-check's).
  3. the reply phrase is named: the brief's filename stem is <n>-<slug>
     (digits, one dash, a non-empty slug) and the literal string
     "reply <n>-<slug>" with the real values occurs in the brief.
  4. markers: a marker line is a whole physical line equal to
     "=== begin <name> ===" or "=== end <name> ===". Every begin pairs with
     an end by name; every marker line occurs exactly once in the file;
     count(begin) == count(end) >= 1.
  5. the sentinel is named: the token COMPLETE occurs in the brief.

On success (exit 0) the round folder is resolved - --round if given, else
the highest round-<k> directory numerically beside the brief - and the
profile <round>/replies/<n>-<slug>.md.profile.json is written (0600,
no-clobber: an existing profile holding the identical JSON object is an
exit-0 no-op with mtime untouched; an existing different or unreadable
profile is exit 2, untouched). stdout then carries exactly two lines:

    VERDICT: brief ok <brief-path> <byte-length> window <digits>
    HARVEST: python3 <skill-dir>/extract-reply.py "<reply <n>-<slug>>" <profile> --session <session> --since <epoch-seconds> --out <round>/replies/<n>-<slug>.md

<skill-dir> is the directory containing brief-check.py; <session> is
$OPENCODE_SESSION_ID from the environment when set, else the literal
$OPENCODE_SESSION_ID for the owner's shell to expand; profile and --out
paths are absolute. With --json, one JSON document with the same facts is
printed instead (on failures too).

Exit codes: 0 ok; 1 a failed check or no round folder (nothing written);
2 usage, unreadable input, a broken skeleton, or a profile conflict
(nothing written). stdout carries results only; stderr carries
diagnostics only. Single file. Standard library only. Python 3.8+.
"""

import argparse
import json
import os
import re
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
MARKER_BEGIN_RE = re.compile(r"^=== begin (.+) ===$")
MARKER_END_RE = re.compile(r"^=== end (.+) ===$")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
PLACEHOLDER_RE = re.compile(r"<[^>\n]{1,80}>")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
STEM_RE = re.compile(r"(\d+)-(.+)")
ROUND_NAME_RE = re.compile(r"round-(\d+)")


class Fail(Exception):
    """Exit 2: a named failure cause (nothing written)."""


class Refused(Exception):
    """Exit 1: failed checks, or no round folder (nothing written)."""

    def __init__(self, failures):
        super().__init__(failures)
        self.failures = failures  # list of (check_id, clause); check_id is a number or "round"


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


def skeleton_parts(skeleton_text):
    """(opener, time_paragraph, window_regex) from the skeleton; a broken skeleton is exit 2."""
    lines = skeleton_text.split("\n")
    if len(lines) < 3:
        raise Fail(f"skeleton is broken: {len(lines)} line(s), need at least 3")
    opener, time_para = lines[0], lines[2]
    if time_para.count(SLOT) != 1:
        raise Fail(f"skeleton is broken: time-limit paragraph must hold exactly one {SLOT} slot")
    left, right = time_para.split(SLOT)
    return opener, time_para, re.compile(re.escape(left) + WINDOW_RE + re.escape(right))


# ---------------------------------------------------------------------------
# checks


def check_verbatim(lines, opener, window_rx):
    """Check 1. Returns (clause_or_None, window_or_None)."""
    if opener not in lines:
        return "opener line not present byte-equal", None
    windows = [m.group(1) for line in lines for m in [window_rx.fullmatch(line)] if m]
    if not windows:
        return "time-limit paragraph missing or altered beyond the window slot", None
    return None, windows[0]


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


def check_phrase(text, stem):
    """Check 3. Returns (clause_or_None, phrase_or_None)."""
    m = STEM_RE.fullmatch(stem)
    if not m or not m.group(2).strip():
        return f"filename stem is not <n>-<slug>: {stem!r}", None
    phrase = "reply " + stem
    if phrase not in text:
        return f"reply phrase not named: {phrase!r}", None
    return None, phrase


def check_markers(lines):
    """Check 4. Returns (clause_or_None, required_lines); required_lines are the brief's
    marker lines in file order, begins and ends."""
    begins = [line for line in lines if MARKER_BEGIN_RE.match(line)]
    ends = [line for line in lines if MARKER_END_RE.match(line)]
    if not begins and not ends:
        return "no marker lines", []
    seen = {}
    for line in begins + ends:
        seen[line] = seen.get(line, 0) + 1
    for line, count in seen.items():
        if count > 1:
            return f"marker line occurs {count} times: {line!r}", []
    begin_names = {MARKER_BEGIN_RE.match(line).group(1) for line in begins}
    end_names = {MARKER_END_RE.match(line).group(1) for line in ends}
    for name in sorted(begin_names - end_names):
        return f"begin without end: {name!r}", []
    for name in sorted(end_names - begin_names):
        return f"end without begin: {name!r}", []
    if len(begins) != len(ends) or not begins:
        return f"count(begin)={len(begins)} count(end)={len(ends)}; need equal and >= 1", []
    required = [line for line in lines if MARKER_BEGIN_RE.match(line) or MARKER_END_RE.match(line)]
    return None, required


def check_sentinel(text):
    """Check 5."""
    if SENTINEL not in text:
        return "sentinel COMPLETE not named"
    return None


def run_checks(text, skeleton_text, stem):
    """All five checks. Returns (failures, facts dict); facts are complete only when no check failed."""
    lines = text.split("\n")
    opener, _time_para, window_rx = skeleton_parts(skeleton_text)
    failures = []
    facts = {}

    clause, window = check_verbatim(lines, opener, window_rx)
    if clause:
        failures.append((1, clause))
    facts["window"] = window

    clause = check_placeholders(lines)
    if clause:
        failures.append((2, clause))

    clause, phrase = check_phrase(text, stem)
    if clause:
        failures.append((3, clause))
    facts["phrase"] = phrase

    clause, required_lines = check_markers(lines)
    if clause:
        failures.append((4, clause))
    facts["required_lines"] = required_lines

    clause = check_sentinel(text)
    if clause:
        failures.append((5, clause))

    return failures, facts


# ---------------------------------------------------------------------------
# round folder and profile


def resolve_round(brief_dir, round_arg):
    """The round folder beside the brief; a miss is exit 1."""
    if round_arg is not None:
        name = round_arg if ROUND_NAME_RE.fullmatch(round_arg) else "round-" + round_arg
        path = brief_dir / name
        if path.is_dir():
            return path
        raise Refused([("round", f"round folder not found: {path}")])
    best, best_k = None, -1
    try:
        entries = sorted(brief_dir.iterdir())
    except OSError as exc:
        raise Fail(f"cannot list {brief_dir}: {exc}")
    for entry in entries:
        m = ROUND_NAME_RE.fullmatch(entry.name)
        if m and entry.is_dir() and int(m.group(1)) > best_k:
            best, best_k = entry, int(m.group(1))
    if best is None:
        raise Refused([("round", f"no round-<k> directory beside {brief_dir}")])
    return best


def write_profile(profile_path, profile):
    """No-clobber write, 0600. Identical JSON object -> no-op; different or unreadable -> exit 2."""
    data = (json.dumps(profile, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if profile_path.exists():
        try:
            existing = json.loads(profile_path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise Fail(f"profile conflict: existing profile is unreadable: {profile_path}: {exc}")
        if existing != profile:
            raise Fail(f"profile conflict: existing profile differs: {profile_path}")
        return "noop"
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
    return "written"


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
        help="round folder name (round-k, or bare k); default: the highest round-<k> beside the brief",
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
    status = write_profile(profile_path, profile)

    session = os.environ.get("OPENCODE_SESSION_ID") or "$OPENCODE_SESSION_ID"
    since = int(time.time())
    skill_dir_str = str(skill_dir)
    profile_str = os.path.abspath(str(profile_path))
    out_str = os.path.abspath(str(out_path))
    verdict_line = f"VERDICT: brief ok {args.brief} {len(raw)} window {facts['window']}"
    harvest_payload = (
        f'python3 {skill_dir_str}/extract-reply.py "{facts["phrase"]}" {profile_str}'
        f" --session {session} --since {since} --out {out_str}"
    )
    harvest_line = "HARVEST: " + harvest_payload
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
