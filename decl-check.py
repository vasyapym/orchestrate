#!/usr/bin/env python3
"""decl-check - the declarations self-check: six named checks over the skill tree.

    python3 decl-check.py [root] [--no-machine]

root defaults to this tool's own directory (the skill repo). The checked
files: declarations/ (core.md, briefs.md, reply.md, roster.md, jobs.md,
brief-skeleton.md, machines/*.md, projects/*.md), SKILL.md, bytecheck.md,
commands/*.md and the machine-side config root.

Checks (each miss is one named failure: path + clause; any miss -> exit 1;
failures list every miss with the summary line last, bytecheck-style):

  1. byte caps per part (DECISION-1, adopted design part A, with amendment
     5 applied - core.md's cap is 3,500, not the design's 3,000):
       declarations/core.md           <= 3,500
       declarations/briefs.md         <= 4,000
       declarations/reply.md          <= 4,000
       declarations/roster.md         <= 2,000
       declarations/brief-skeleton.md <= 2,200
       declarations/jobs.md           <= 2,800
     machines/*.md and projects/*.md carry no cap: the design leaves them
     as today.
  2. path resolution. Every absolute path written in declarations/core.md
     and every inlined `cat` path in commands/*.md resolves (expand ~, test
     existence). Token rules:
       - a path token is a maximal non-whitespace run starting with ~/ or /
         (a backtick ends it); a token containing < or $ is a template
         placeholder (projects/<project>.md, shell $1) and is skipped;
       - a token starting with / must hold a second / - the slash-commands
         /o-open, /o-brief, /o-reply are commands, not paths;
       - trailing punctuation (., ; : ) ] em-dash) is stripped.
     In a command file the `cat` argument is taken up to the first space
     that begins a shell token, so `2>/dev/null` and `|| echo` tails do not
     break the parse; if that argument holds < or $ it is skipped.
  3. the skeleton's chat-model opener (declarations/brief-skeleton.md
     line 1) equals SKILL.md's chat-model line - the first SKILL.md line
     whose text, after stripping a leading "> ", starts with "Answer as a
     chat model - no agentic operations"; byte-equal after that strip.
  4. the time-limit paragraph - the skeleton's line starting "There's a
     <N-M>-minute" - occurs in exactly one file of the checked set
     (declarations/*.md + SKILL.md + bytecheck.md, present files), as a
     whole physical line byte-equal. 0 or >= 2 fails (the clause names the
     files); exactly one passes, and by construction that one is the
     skeleton.
  5. every hard line in core.md (lines matching ^  - .* - home: ) names a
     home: the text after "- home: " must name an existing file under
     declarations/. Allowed forms: the two-home form "briefs.md and
     brief-skeleton.md", and template tokens holding < or $
     (projects/<project>.md) which are skipped as in check 2.
  6. the machine-side config root ~/.config/orchestrate/declarations.md:
     missing -> miss (named); a symlink -> its real path must equal
     core.md's real path; a regular file -> its bytes must equal core.md's;
     anything else -> miss. --no-machine skips this check - decl-check's
     own decision, so test environments and other-machine runs (which have
     no config root) can still check the rest.

Exit codes: 0 every check passes; 1 one or more misses (nothing written);
2 usage (unknown flag, root not a directory) or environment (a spine file
unreadable: declarations/core.md, declarations/brief-skeleton.md, SKILL.md).
stdout carries results only; stderr carries diagnostics only. The tool
reads only - it never writes to the tree it checks. Single file. Standard
library only. Python 3.8+.
"""

import argparse
import os
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_FAIL = 2

TOOL_NAME = "decl-check"

# (path relative to root, cap in bytes, citation appended to a breach clause).
# core.md's cap is DECISION-1 amendment 5: 3,500, not the design's 3,000.
BYTE_CAPS = (
    ("declarations/core.md", 3500, "DECISION-1 amendment 5: 3,500, not the design's 3,000"),
    ("declarations/briefs.md", 4000, ""),
    ("declarations/reply.md", 4000, ""),
    ("declarations/roster.md", 2000, ""),
    ("declarations/brief-skeleton.md", 2200, ""),
    ("declarations/jobs.md", 2800, ""),
)

CORE_REL = "declarations/core.md"
SKELETON_REL = "declarations/brief-skeleton.md"
SKILL_REL = "SKILL.md"
BYTECHECK_REL = "bytecheck.md"
CONFIG_ROOT = "~/.config/orchestrate/declarations.md"

CHAT_MODEL_PREFIX = "Answer as a chat model \u2014 no agentic operations"
PARAGRAPH_PREFIX = "There's a <N\u2013M>-minute"
HOME_SEP = " \u2014 home: "
HARD_LINE_RE = re.compile(r"^  - .*\u2014 home: ")
PATH_TOKEN_RE = re.compile(r"(?:~/|/)[^\s`]+")
SPAN_RE = re.compile(r"`([^`]*)`")
CAT_RE = re.compile(r"(?:^|\s)cat\s+([^\s`]+)")
TRAILING_PUNCT = ".,;:)]\u2014"


class Fail(Exception):
    """Exit 2: usage or environment error (nothing written)."""


class Refused(Exception):
    """Exit 1: named misses (nothing written)."""

    def __init__(self, misses):
        super().__init__(misses)
        self.misses = misses  # list of (where, rule, clause)


# ---------------------------------------------------------------------------
# reading


def read_text(path, what):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise Fail(f"cannot read {what}: {exc}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Fail(f"{what} is not valid UTF-8: {exc}")


def read_bytes(path, what):
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise Fail(f"cannot read {what}: {exc}")


# ---------------------------------------------------------------------------
# path tokens (check 2)


def path_tokens(line):
    """Absolute path tokens of one line, per the check-2 token rules."""
    for match in PATH_TOKEN_RE.finditer(line):
        token = match.group(0).rstrip(TRAILING_PUNCT)
        if "<" in token or "$" in token:
            continue  # template placeholder: projects/<project>.md, shell $1
        if token.startswith("~") or token.count("/") >= 2:
            yield token


def resolves(root, token):
    """Expand ~, resolve relative tokens against the root, test existence."""
    resolved = os.path.expanduser(token)
    if not os.path.isabs(resolved):
        resolved = os.path.join(str(root), resolved)
    return os.path.exists(resolved)


# ---------------------------------------------------------------------------
# checks (each appends (where, rule, clause) misses)


def check_caps(root, misses):
    """Check 1: byte caps per part; machines and project blocks carry no cap."""
    for rel, cap, note in BYTE_CAPS:
        path = root / rel
        if not path.exists():
            misses.append((rel, "cap", "file is missing (cap %s bytes)" % f"{cap:,}"))
            continue
        size = len(read_bytes(path, rel))
        if size > cap:
            clause = "cap %s > %s bytes" % (f"{size:,}", f"{cap:,}")
            if note:
                clause += " (%s)" % note
            misses.append((rel, "cap", clause))


def check_core_paths(root, misses):
    """Check 2, first half: absolute paths written in core.md resolve."""
    text = read_text(root / CORE_REL, CORE_REL)
    for number, line in enumerate(text.split("\n"), 1):
        for token in path_tokens(line):
            if not resolves(root, token):
                misses.append((f"{CORE_REL}:{number}", "path", f"path does not resolve: {token}"))


def check_command_paths(root, misses):
    """Check 2, second half: inlined `cat` paths in commands/*.md resolve."""
    commands = root / "commands"
    if not commands.is_dir():
        return  # nothing to scan; this check does not test the layout itself
    for path in sorted(commands.glob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = read_text(path, rel)
        for number, line in enumerate(text.split("\n"), 1):
            for span in SPAN_RE.finditer(line):
                for match in CAT_RE.finditer(span.group(1)):
                    token = match.group(1)
                    if "<" in token or "$" in token:
                        continue  # template placeholder: projects/$1.md
                    if not resolves(root, token):
                        misses.append(
                            (f"{rel}:{number}", "path", f"cat path does not resolve: {token}"))


def check_opener(root, misses):
    """Check 3: the skeleton's line 1 equals SKILL.md's chat-model line."""
    opener = read_text(root / SKELETON_REL, SKELETON_REL).split("\n")[0]
    skill_lines = read_text(root / SKILL_REL, SKILL_REL).split("\n")
    for number, line in enumerate(skill_lines, 1):
        content = line[2:] if line.startswith("> ") else line
        if content.startswith(CHAT_MODEL_PREFIX):
            if opener != content:
                misses.append(
                    (f"{SKELETON_REL}:1", "opener",
                     f"opener differs from {SKILL_REL}:{number}'s chat-model line"))
            return
    misses.append((SKILL_REL, "opener", "chat-model line not found in SKILL.md"))


def check_paragraph(root, occurrence_set, misses):
    """Check 4: the time-limit paragraph occurs in exactly one checked file."""
    paragraph = None
    for line in read_text(root / SKELETON_REL, SKELETON_REL).split("\n"):
        if line.startswith(PARAGRAPH_PREFIX):
            paragraph = line
            break
    if paragraph is None:
        misses.append((SKELETON_REL, "paragraph",
                       "time-limit paragraph occurs in 0 files: no skeleton line starts "
                       "'There's a <N-M>-minute'"))
        return
    holders = []
    for path in occurrence_set:
        rel = path.relative_to(root).as_posix()
        if paragraph in read_text(path, rel).split("\n"):
            holders.append(rel)
    if len(holders) == 1:
        return  # by construction the one holder is the skeleton
    if not holders:
        misses.append((SKELETON_REL, "paragraph",
                       "time-limit paragraph occurs in 0 files of the checked set"))
    else:
        misses.append((SKELETON_REL, "paragraph",
                       "time-limit paragraph occurs in %d files: %s (one home only)"
                       % (len(holders), ", ".join(holders))))


def check_homes(root, misses):
    """Check 5: every core.md hard line names an existing home in declarations/."""
    declarations = root / "declarations"
    text = read_text(root / CORE_REL, CORE_REL)
    for number, line in enumerate(text.split("\n"), 1):
        if not HARD_LINE_RE.match(line):
            continue
        home = line.rsplit(HOME_SEP, 1)[1].strip()
        if "<" in home or "$" in home:
            continue  # template token: projects/<project>.md
        for part in home.split(" and "):
            part = part.strip()
            if not part:
                misses.append((f"{CORE_REL}:{number}", "home", "hard line names no home"))
            elif not (declarations / part).is_file():
                misses.append(
                    (f"{CORE_REL}:{number}", "home",
                     f"hard-line home does not name a file in declarations/: {part}"))


def check_config_root(root, misses):
    """Check 6: the machine-side config root mirrors core.md."""
    config = Path(os.path.expanduser(CONFIG_ROOT))
    core = root / CORE_REL
    if not os.path.lexists(config):
        misses.append((CONFIG_ROOT, "config-root",
                       "machine-side config root is missing: %s" % CONFIG_ROOT))
        return
    if os.path.islink(config):
        if os.path.realpath(config) != os.path.realpath(core):
            misses.append((CONFIG_ROOT, "config-root",
                           "symlink resolves to %s, not core.md (%s)"
                           % (os.path.realpath(config), os.path.realpath(core))))
        return
    if config.is_file():
        if read_bytes(config, CONFIG_ROOT) != read_bytes(core, CORE_REL):
            misses.append((CONFIG_ROOT, "config-root",
                           "regular file does not equal core.md byte for byte"))
        return
    misses.append((CONFIG_ROOT, "config-root", "neither a symlink nor a regular file"))


# ---------------------------------------------------------------------------
# run and report


def run(args):
    """Run every check; returns the miss list (empty when all pass)."""
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent
    if not root.is_dir():
        raise Fail("root %s is not a directory" % args.root)
    # spine files: checks 2-5 cannot run without them; unreadable -> exit 2.
    read_text(root / CORE_REL, CORE_REL)
    read_text(root / SKELETON_REL, SKELETON_REL)
    read_text(root / SKILL_REL, SKILL_REL)

    misses = []
    check_caps(root, misses)
    check_core_paths(root, misses)
    check_command_paths(root, misses)
    check_opener(root, misses)
    declarations_md = sorted((root / "declarations").glob("*.md"))
    occurrence_set = [p for p in declarations_md + [root / SKILL_REL, root / BYTECHECK_REL]
                      if p.is_file()]
    check_paragraph(root, occurrence_set, misses)
    check_homes(root, misses)
    if not args.no_machine:
        check_config_root(root, misses)
    return misses


def render(misses):
    """Every miss as a ! line, summary line last (bytecheck-style)."""
    lines = []
    for where, rule, clause in misses:
        lines.append(f"! {where} {rule} {clause}")
    if misses:
        counts = {}
        for _where, rule, _clause in misses:
            counts[rule] = counts.get(rule, 0) + 1
        breakdown = ", ".join("%d %s" % (n, rule) for rule, n in sorted(counts.items()))
        lines.append("decl-check: FAIL %d miss(es) (%s) -> exit %d"
                     % (len(misses), breakdown, EXIT_REFUSED))
    else:
        lines.append("decl-check: PASS 0 miss(es) -> exit %d" % EXIT_OK)
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Six named checks over the orchestrate declarations tree.",
    )
    parser.add_argument("root", nargs="?",
                        help="skill repo root (default: this tool's own directory)")
    parser.add_argument("--no-machine", action="store_true",
                        help="skip check 6, the machine-side config root (for test environments)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        misses = run(args)
    except Fail as exc:
        sys.stderr.write(f"{TOOL_NAME}: error: {exc}\n")
        return EXIT_FAIL
    except OSError as exc:  # named cause only; never a traceback
        sys.stderr.write(f"{TOOL_NAME}: error: unexpected {type(exc).__name__}: {exc}\n")
        return EXIT_FAIL
    sys.stdout.write(render(misses))
    if misses:
        sys.stderr.write(f"{TOOL_NAME}: exit {EXIT_REFUSED}: {len(misses)} miss(es): "
                         "nothing written\n")
        return EXIT_REFUSED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
