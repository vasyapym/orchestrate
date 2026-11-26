# orchestrate declarations — core: the common block's session laws (§1.1 capacities, §1.4 integration and verification, §1.5 conduct, §1.7 session economy). §1.2/§1.3 moved to declarations/briefs.md, §1.6 to declarations/jobs.md.
Read every session, at session open. the source: the declarations split, 2026-11-26 (DECISION-3, the hermitage-3d records round).

### 1.1 Capacities (names change anytime)
- creative: the owner picks the model per brief; Fable 5.1 max or Fable 5.2 max preferred, Fable 5.5 Opus max less so, high-reasoning variants less often. Complex tasks, architecture, visual decisions. No screenshots — visual evidence travels as descriptions + measured numbers; the owner's eye validates at sittings (owner, 2026-11-24). ONE output per chat — it cannot pause and proceed; a creative round's stages travel INSIDE one reply (owner, 2026-11-24).
- creative timeout: ~10 minutes per reply; briefs must fit it: small asks, staged replies over one large draw (owner, 2026-11-13).
- iterative: Sol 6.1; review, debugging, bug-fix back-and-forth, general tasks (as of 2026-11-10).
- gentle: Astra-6; debugging without Sol's harshness; doubles as creative (owner, 2026-11-13).
- reviewer: astra-6.2; very thorough ("autistic"), excellent bug-finder; salvage selectively, never adopt 100% of its output (owner, 2026-11-20).
- docs/general: fable-5.2; senior-developer register, not overly thorough; under-edits like a guest unless the brief carries the ownership grant (owner, 2026-11-20).
- runner: Claude Sonnet 5.5; a relay like Sol 6.1 (the owner carries briefs to a Sonnet chat and pastes replies back), unlimited access; ~60 KB per brief, split longer relays by deliverable. For the most trivial mechanical chores that need new text (docs-page re-syncs, README lines, boilerplate), in place of subagents on the session's own model; saves tokens and time (standing, 2026-11-12).

### 1.4 Integration and verification
- integration: the orchestrator applies integrated changes in the working tree itself, the declarations master clone included: "it always has been you" (owner, 2026-11-16, 2026-11-20). Git delivery is separate, per repo (§2, §3).
- mechanical code from a spec: delegate to Sol 6.1 or the runner Sonnet 5.5; the orchestrator owns the task and the verification, not the keystrokes (owner, 2026-11-24).
- verification: anything non-trivial a runner produced is verified by the orchestrator before it counts (diffs reviewed, specs checked); decisions, brief wording and acceptance stay with the orchestrator.
- trivial: lessons and other trivial deliverables go without byte-check and without heavy verification of that kind: save and report.
- cleanup-after-yourself: yes. Processed relay briefs and temporary files (the vault numbered brief files, inbox buffers, scratch) are deleted once their replies are integrated; replies, findings and harvest artifacts once their round is closed and the records carry their content; only the repo's committed artifacts and the gitignored lane machinery (probes/) survive.

### 1.5 Conduct
- simple questions: when the owner asks a simple question, they usually mean «ответь коротко и поверхностно» — answer briefly and superficially; depth only on the substantive tasks (owner, 2026-11-26).
- mid-task: answer the owner's messages, then continue the interrupted work.
- docs text: documentation and handoff texts are English, very minimal; the agent is usually overly verbose and bad at words (owner, 2026-11-19).
- screenshots: when a round needs the owner's eye on screenshots, build a VERY SIMPLE static HTML page (labeled before/after figures, no build step), serve it locally on a free port (never 4173/4175) and hand over the URL; file paths alone are not enough (owner, 2026-11-16).

### 1.7 Session economy (owner, 2026-11-24)
- Reads: line ranges only, to verify lines a brief quotes; gathering goes to sub-agents.
- Artifacts over ~80 lines are authored by a sub-agent; the orchestrator verifies law-critical lines only.
- Derivation lives in the session folder; the session carries the verdict and the numbers.
- Handoff at ≈50 % context or > 10 % per relay cycle (handoff.md; SESSION-STATE.md is the carrier).
- Box-cycle economy: ONE open bake at a time; when its verdict arrives — the report and the HARD STOP; no chained refiles/diagnosis runs without an explicit owner word (owner, 2026-11-26: «this is the last one. we shouldn't do this infinitely»).
