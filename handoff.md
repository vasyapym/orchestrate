# handoff — the hand-off part of orchestrate

A hand-off ends one session by leaving one file for the next: a fresh session in the same repository continues the work without re-deriving it, and without inheriting this session's fatigue. It is not a brief — no specialist reads it and no reply is expected; its reader is the next session of this skill, opened with the file's path. Everything the session put on disk stays on disk and is pointed at, not retold. The hand-off carries what no path holds — the task's wording, the user's spoken decisions, what the session assumed and could not verify — and marks which is which, so the next session starts from the frame and not from this session's weather.

## When it runs

On the user's word — the part named, or the session ended in ordinary words ("let's continue tomorrow", "hand this off") — and on your own when the session shows the signs it exists for: many rounds behind it and work plainly ahead, a reply misread, a question already answered asked again. Mid-round, first bring the batch in hand to a verified state or set it aside, and say what you are doing; the user may refuse, and the round goes on. A fresh session writes none, and a round that closed clean with nothing ahead needs none — the report in chat and the records on disk are already the whole story.

## You write it yourself

In one pass, at the end: only you hold the conversation it quotes, and a sub-agent holds none of it — handed the task, it would write what it guesses. Quote the user's words exactly as they stand in the conversation; re-typing them from memory paraphrases, and a paraphrase written late in a tired session is how a decision nobody made enters the record. The ladder for everything else: a path where disk holds it, a label where only you hold it, silence where nothing holds it. If the document runs past a page, it is retelling; cut by what the paths already hold.

## What the document carries

Headed sections, in this order:

- **Task as stated.** The user's words at open, verbatim, and each amendment as given. This exists nowhere on disk, so it is the one part never paraphrased; re-quote it whole even where an earlier hand-off holds it, because the document is read alone.
- **Settled.** Each decision this conversation took, quoted as the user gave it, with a decision record's path beside it where one exists; ruled-out options that would otherwise come back, a line each. A quoted decision is a fact under the core. What you merely understood the user to prefer is not settled: it belongs under Open, labelled yours.
- **State.** Where the work stands, by path and command: the last commit; what the working tree holds uncommitted and which intention each change belongs to — the intentions are the content, the diff the reader takes from disk; briefs, replies, round records and ledgers by path; gates run and their results; what was integrated and what rejected.
- **Open.** What the next session inherits unsettled: questions awaiting the user; disagreements left for them unresolved; next steps the records name, with the part whose moment will come — `decision.md`, `correction.md`, a review pass — beside the item; your assumptions the work leaned on, labelled yours; what this session could not verify. An unknown is stated as unknown, never dressed as a caution: "the build may be broken" is either a fact with a command or an unknown.
- **Next.** Where the user said what the next session should focus on, their words quoted as given — not expanded into instructions; and one suggested step of your own, a line or two, labelled yours. The suggestion sets no course.

End the document with the reader's line:

> Confirm against the repository what you act on: quoted decisions here are settled; paths are checked by opening them; lines marked yours or unknown are leads, not facts.

## What it must not carry

- **A course.** No plan of attack, no order of work, no "first", "make sure", "do not touch". The next session is an orchestrator like this one: it opens under the core, restates the task, asks its one round of questions, and the user steers. A prohibition that is real is a settled decision — quote it under Settled; one that is not settles nothing and is noise.
- **Your weather.** Nothing of the session's own account — what it tried, what it apologized for, what it felt behind on. None of it is evidence about the work; what the work costs shows in the records.
- **The unlabelled inference.** A claim with no path and no quote is yours: labelled as such, or absent.

## Where it goes

`HANDOFF.md` in the session's brief folder — one per session, written again if the session goes on, so the file always holds the newest state; no brief folder this session, create one as the core's hand-over default does. It survives cleanup until a later hand-off supersedes it. Tell the user the path; the user opens the next session with it, as they carry a brief.

## Take a hand-off

Opened with one, read it whole once, then open under the core as always — restate the task, one round of questions where the document leaves room. Its labels travel: a quoted decision is settled and bounds the work like any other; a path is opened, not trusted; a line marked yours is a claim like a sub-agent's finding — usable as a lead, confirmed against disk before anything is built on it. Where the document and the disk disagree, the disk wins, and the difference goes to the user in one line: a hand-off that lies in small things may lie in large ones.
