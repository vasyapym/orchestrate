#!/usr/bin/env python3
"""check.py - one gate, three modes (DECISION-2 §C); brief now, reply/decl step 3.

Usage: check.py brief <brief.md> [--round <dir>]. Live text: the file minus the span
from the first "## Context and code" line to the last "## Output contract" line,
minus lines strictly between a begin/end marker pair in the contract. Refuses (one
clause per missed check: the check and the path, never contents) unless: skeleton
line 1 whole in the head, byte-equal; the digit-filled time paragraph whole in the
head; no angle-bracket placeholder remains in live text; the contract names the
first-line phrase, a terminal line, the same digits, and zero or more marker pairs
(begin before end, each line unique). Writes <round>/replies/<brief>.profile.json
once (schema v1 keys only: required_lines, terminal_line), never rewritten; --since
is its mtime. Prints last VERDICT: brief ok <brief> <bytes> window <N-M>, then
HARVEST: the shell-quoted extract-reply.py argv. Lessons (§E) held. Exit
0 ok / 1 refused / 2 broken (usage, unreadable input, broken skeleton, conflict).
"""
import json, os, re, shlex, sys
from pathlib import Path

SLOT, CTX, OC = "<N\u2013M>", "## Context and code", "## Output contract"
BEGIN, END = re.compile(r"^=== begin (.+) ===$"), re.compile(r"^=== end (.+) ===$")
PH, DONE = re.compile(r"<[^>\n]{1,80}>"), re.compile(r"\bCOMPLETE\b")
STEM = re.compile(r"(\d+)-(.+)")
UNSET = "<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"
USAGE = "usage: check.py brief <brief.md> [--round <dir>]"


class Fail(Exception):
    pass  # exit 2: a named cause; nothing written


class Refused(Exception):  # exit 1: failed checks; nothing written
    def __init__(self, misses, path):
        self.misses, self.path = misses, path


def split(text):  # LF lines, one trailing CR dropped (F13); bytes untouched
    return [l[:-1] if l[-1:] == "\r" else l for l in text.split("\n")]


def head(lines):  # the prose head: the lines before the first "## " line
    for i, l in enumerate(lines):
        if l.startswith("## "):
            return lines[:i]
    return lines


def cut(lines):  # (contract, live, required, marker miss) - the section cut
    a = next((i for i, l in enumerate(lines) if l.startswith(CTX)), None)
    s = [i for i, l in enumerate(lines) if l.startswith(OC)]
    if not s:
        return None, lines, [], None
    c, t, st, seen, req, mm = [], [], [], set(), [], None
    for l in lines[s[-1] + 1:]:
        c.append(l)
        b, e = BEGIN.match(l), END.match(l)
        if b or e:
            req.append(l)
            if l in seen and mm is None:
                mm = "a marker line is not unique"
            seen.add(l)
        if b:
            st.append(b.group(1))
            t.append(l)
        elif e:
            if st and e.group(1) == st[-1]:
                st.pop()
            elif mm is None:
                mm = "an end without its begin before it"
            t.append(l)
        elif not st:
            t.append(l)
    if st and mm is None:
        mm = "a begin without its end after it"
    return c, (lines[:a] + t if a is not None and a <= s[-1] else lines), req, mm


def skeleton(text):  # (opener, window regex); a broken skeleton is exit 2
    lines = split(text)
    if not lines or not lines[0]:
        raise Fail("skeleton broken: no opener line")
    p = [l for l in head(lines) if l.startswith("There's a")]
    if len(p) != 1 or p[0].count(SLOT) != 1:
        raise Fail("skeleton broken: no single 'There's a' paragraph with one %s" % SLOT)
    l, r = p[0].split(SLOT)
    return lines[0], re.compile(re.escape(l) + r"(\d+(?:\s*\u2013\s*\d+)?)" + re.escape(r))


def checks(lines, opener, rx, stem):  # (misses, window, phrase, required_lines)
    miss, h = [], head(lines)
    if opener not in h:
        miss.append((1, "opener missing from the head"))
    w = [m.group(1) for l in h for m in [rx.fullmatch(l)] if m]
    window = w[0] if w else ""
    if not w:
        miss.append((2, "time paragraph missing from the head"))
    c, liv, req, mm = cut(lines)
    hit = next((i for i, l in enumerate(liv) if PH.search(l)), None)
    if hit is not None:
        miss.append((3, "placeholder left in live text (line %d)" % (hit + 1)))
    m = STEM.fullmatch(stem)
    phrase = "reply " + stem if m and m.group(2).strip() else None
    if not phrase:
        miss.append((4, "stem is not <n>-<slug>"))
    if c is None:
        miss += [(n, "no %r heading" % OC) for n in (4, 5, 6, 7)]
        return miss, window, phrase, []
    text = "\n".join(c)
    if phrase and phrase not in text:
        miss.append((4, "phrase %r missing from the contract" % phrase))
    if window and window not in text:
        miss.append((5, "digits %r missing from the contract" % window))
    if mm:
        miss.append((6, mm))
    if not any(DONE.search(l) for l in c):
        miss.append((7, "terminal line missing from the contract"))
    return miss, window, phrase, req


def brief(rest):  # the brief mode; returns the two hand-over lines
    rd = None
    if "--round" in rest:
        i = rest.index("--round")
        rd, rest = rest[i + 1], rest[:i] + rest[i + 2:]
    if len(rest) != 1:
        raise Fail(USAGE)
    path, skill = Path(rest[0]), Path(__file__).resolve().parent
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        opener, rx = skeleton((skill / "declarations" / "brief-skeleton.md").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Fail("cannot read the brief or the skeleton: %s" % exc)
    miss, window, phrase, req = checks(split(text), opener, rx, path.stem)
    if miss:
        raise Refused(miss, rest[0])
    rd = Path(rd) if rd else path.parent
    profile = rd / "replies" / (path.name + ".profile.json")
    doc = {"version": 1, "required_lines": req, "terminal_line": "COMPLETE"}
    if profile.exists():
        try:
            old = json.loads(profile.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            old = None
        if not isinstance(old, dict) or {k: v for k, v in old.items() if k != "since"} != doc:
            raise Fail("profile conflict at %s; never rewritten" % profile)
    else:
        try:
            profile.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(profile), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write((json.dumps(doc, indent=2, sort_keys=True) + "\n").encode())
        except OSError as exc:
            raise Fail("cannot write %s: %s" % (profile, exc))
    ab = os.path.abspath
    harvest = shlex.join(["python3", str(skill / "extract-reply.py"), phrase, ab(str(profile)),
                          "--session", os.environ.get("OPENCODE_SESSION_ID") or UNSET,
                          "--since", str(int(profile.stat().st_mtime)),
                          "--out", ab(str(rd / "replies" / path.name))])
    return "VERDICT: brief ok %s %d window %s\nHARVEST: %s" % (rest[0], len(raw), window, harvest)


def main(argv):
    mode = argv[0] if argv else ""
    if mode not in ("brief", "reply", "decl"):
        sys.stderr.write(USAGE + "\n")
        return 2
    if mode != "brief":  # step 3 extends this dispatch
        sys.stderr.write("check.py: mode %r not built yet (step 3)\n" % mode)
        return 2
    try:
        printed = brief(argv[1:])
    except Refused as exc:
        for n, clause in exc.misses:
            print("FAIL %d %s: %s" % (n, exc.path, clause))
        return 1
    except Fail as exc:
        sys.stderr.write("check.py: %s\n" % exc)
        return 2
    except Exception as exc:  # a crash is a named exit 2, never a traceback
        sys.stderr.write("check.py: %s: %s\n" % (type(exc).__name__, exc))
        return 2
    print(printed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
