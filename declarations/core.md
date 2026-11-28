# orchestrate declarations — core: scope, precedence, hard lines, conduct (§1.5, §1.7), the map. capacities: roster.md; reply law: reply.md.
Read every session at open; inlined by /o-open. source: DECISION-1 (2026-11-28).

- scope: the orchestrate main session only; sub-agents ignore this file.
- precedence: a declaration overrides SKILL.md's defaults; a recent part wins over memory.
- hard lines, each "<imperative> — home: <part>":
  - every brief is the skeleton, copied by command — home: briefs.md and brief-skeleton.md
  - the hand-over message quotes brief-check's two lines — home: briefs.md
  - a reply is harvested by command, never retyped — home: reply.md
  - the first line after a paste is the RECEIPT line — home: reply.md
  - exact text is placed from disk, never retyped into a brief — home: briefs.md
  - commit and push follow the project block — home: projects/<project>.md

### 1.5 Conduct
- simple questions: when the owner asks a simple question, they usually mean «ответь коротко и поверхностно» — answer briefly and superficially; depth only on the substantive tasks (owner, 2026-11-26).
- mid-task: answer the owner's messages, then continue the interrupted work.
- docs text: documentation and handoff texts are English, very minimal; the agent is usually overly verbose and bad at words (owner, 2026-11-19).
- screenshots: when a round needs the owner's eye on screenshots, build a VERY SIMPLE static HTML page (labeled before/after figures, no build step), serve it locally on a free port (never 4173/4175) and hand over the URL; file paths alone are not enough (owner, 2026-11-16).

### 1.7 Session economy (owner, 2026-11-24)
- Reads: line ranges only, to verify lines a brief quotes; gathering goes to sub-agents.
- Artifacts over ~80 lines are authored by a sub-agent; the orchestrator verifies law-critical lines only.
- Derivation lives in the session folder; the session carries the verdict and the numbers.
- Handoff: no hard rule; the orchestrator can't see its own fill — ask the owner when in doubt (owner, 2026-11-26).
- exception: a declarations part is read whole, never by line range, never through a sub-agent.

### 1.8 The map (inlined by the commands)
- open: ~/.config/opencode/skills/orchestrate/declarations/core.md + ~/.config/opencode/skills/orchestrate/declarations/roster.md + ~/.config/opencode/skills/orchestrate/declarations/machines/new-mac.md + ~/.config/opencode/skills/orchestrate/declarations/projects/<project>.md — inlined by /o-open
- compose: ~/.config/opencode/skills/orchestrate/declarations/briefs.md + roster.md — inlined by /o-brief; skeleton copied by command; brief-check's two lines into the hand-over
- reply: ~/.config/opencode/skills/orchestrate/declarations/reply.md — inlined by /o-reply
- job: ~/.config/opencode/skills/orchestrate/declarations/jobs.md — pulled, absolute path
- review, decision, correction, handoff, executor, mailbox: SKILL.md's own sentences, pulled — absolute path
- the orchestrate repo: no project block; delivery law: jobs.md's skill-repos line (agent commits and pushes always)
- bytecheck.md: pulled whole only when byte-checking is on or a Harvest rung fails
- self-rescue: before compose/reply/job without that part in recent messages — read it whole now (paths above).

### 1.9 Maintenance
- a law is edited in its one home; this file takes pointers, never law; run decl-check.py after any declarations edit (once it exists).
