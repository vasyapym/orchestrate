#!/usr/bin/env python3
"""check.py - the DECISION-2 gate: brief now, reply/decl in step 3.
usage: check.py brief <brief.md> [--round <dir>]
exit 0 ok / 1 refused (one FAIL line per missed check: number, path, cause) / 2 broken
"""
import json, os, re, shlex, sys
from pathlib import Path

SLOT, OC = "<N\u2013M>", "## Output contract"
MARK, PH = re.compile(r"^=== (begin|end) (.+) ===$"), re.compile(r"<[^>\n]{1,80}>")
UNSET = "<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"
USAGE = "usage: check.py brief <brief.md> [--round <dir>]"


def die(msg): # exit 2, nothing written
    sys.stderr.write("check.py: %s\n" % msg)
    sys.exit(2)


def split(text): # F13: LF lines, one trailing CR dropped
    return [l[:-1] if l[-1:] == "\r" else l for l in text.split("\n")]


def head(lines): # lines before the first "## " line
    return lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))]


def check(lines, sk, spec): # refuse (exit 1) or -> (window, required lines)
    p = [l for l in head(sk) if l.startswith("There's a")]
    if not sk[0] or len(p) != 1 or p[0].count(SLOT) != 1:
        die("broken skeleton: need line 1 and one 'There's a' paragraph with one %s" % SLOT)
    l, r = p[0].split(SLOT)
    rx = re.compile(re.escape(l) + r"(\d+(?:\s*\u2013\s*\d+)?)" + re.escape(r))
    miss, h = [], head(lines)
    if sk[0] not in h:
        miss += [(1, "opener missing from the head")]
    w = [m[1] for m in map(rx.fullmatch, h) if m]
    window = w[0] if w else ""
    if not w:
        miss += [(2, "time paragraph missing from the head")]
    oc = [i for i, l in enumerate(lines) if l.startswith(OC)]
    c, t, st, req, mm = lines[oc[-1] + 1:] if oc else [], [], [], [], None
    for l in c:
        m = MARK.match(l)
        if m:
            if l in req and not mm:
                mm = "a marker line is not unique"
            req.append(l)
            if m[1] == "begin":
                st.append(m[2])
            elif st and st[-1] == m[2]:
                st.pop()
            elif not mm:
                mm = "an end without its begin before it"
        if m or not st:
            t.append(l)
    if st and not mm:
        mm = "a begin without its end after it"
    a = [i for i, l in enumerate(lines[:oc[-1]]) if l.startswith("## Context and code")] if oc else []
    live = lines[:a[0]] + t if a else lines
    hit = [i for i, l in enumerate(live, 1) if PH.search(l)]
    if hit:
        miss += [(3, "placeholder left in live text (line %d)" % hit[0])]
    stem = Path(spec).stem
    ok, phrase = re.fullmatch(r"\d+-.*\S.*", stem), "reply " + stem
    if not ok:
        miss += [(4, "stem is not <n>-<slug>")]
    if not oc:
        miss += [(n, "no %r heading" % OC) for n in (4, 5, 6, 7)]
    else:
        text = "\n".join(c)
        if ok and phrase not in text:
            miss += [(4, "phrase %r missing from the contract" % phrase)]
        if window and window not in text:
            miss += [(5, "digits %r missing from the contract" % window)]
        if mm:
            miss += [(6, mm)]
        if not re.search(r"\bCOMPLETE\b", text):
            miss += [(7, "terminal line missing from the contract")]
    if miss:
        print("\n".join("FAIL %d %s: %s" % (n, spec, why) for n, why in miss))
        sys.exit(1)
    return window, req


def brief(rest): # -> the two hand-over lines
    rd = None
    if "--round" in rest:
        i = rest.index("--round")
        rd, rest = rest[i + 1], rest[:i] + rest[i + 2:]
    if len(rest) != 1:
        die(USAGE)
    path, skill = Path(rest[0]), Path(__file__).resolve().parent
    raw = path.read_bytes()
    sk = split((skill / "declarations" / "brief-skeleton.md").read_text(encoding="utf-8"))
    window, req = check(split(raw.decode("utf-8")), sk, rest[0])
    out = (Path(rd) if rd else path.parent) / "replies"
    profile = out / (path.name + ".profile.json")
    doc = {"version": 1, "required_lines": req, "terminal_line": "COMPLETE"}
    if profile.exists():
        try:
            old = json.loads(profile.read_bytes())
        except (OSError, ValueError):
            old = None
        if not isinstance(old, dict) or {k: v for k, v in old.items() if k != "since"} != doc:
            die("profile conflict at %s; never rewritten" % profile)
    else:
        out.mkdir(parents=True, exist_ok=True)
        with open(os.open(profile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
            f.write((json.dumps(doc, indent=2, sort_keys=True) + "\n").encode())
    ab = os.path.abspath
    harvest = shlex.join([
                          "python3", str(skill / "extract-reply.py"), "reply " + path.stem, ab(profile),
                          "--session", os.environ.get("OPENCODE_SESSION_ID") or UNSET,
                          "--since", str(int(profile.stat().st_mtime)), "--out", ab(out / path.name)])
    return "VERDICT: brief ok %s %d window %s\nHARVEST: %s" % (rest[0], len(raw), window, harvest)


def main(argv):
    mode = argv[0] if argv else ""
    if mode not in ("brief", "reply", "decl"):
        die(USAGE)
    if mode != "brief": # step 3 extends this dispatch
        die("mode %r not built yet (step 3)" % mode)
    try:
        print(brief(argv[1:]))
    except Exception as exc: # a crash is a named exit 2
        die("%s: %s" % (type(exc).__name__, exc))


if __name__ == "__main__":
    main(sys.argv[1:])

