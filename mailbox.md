# mailbox — the agent-jobs coordination (orchestrate side)

The coordination conventions are canonical in the agent-jobs repo: `SIGNALS.md` at its root (the Mac clone: `~/Documents/agent-jobs`). Nothing here is needed by a non-orchestrate agent; the mailbox works with or without this file.

- A session that works the mailbox is given its identity once, in the opening prompt: "mailbox <path-to-agent-jobs>, read SIGNALS.md, you are \<who\>" — `<who>` is the session's lane name, the handoff title lowercased (`rastrelli`, `sqad`); box sessions are `box-<name>`; the owner is `owner`.
- The open checkpoint is the first act of a session on mailbox work; the close checkpoint is the last act before `handoff.md`.
- Relay briefs to chat models never carry mailbox state; chat models never see tickets or notes.
- The hand-off no longer repeats what an `open.all` note already says.
- machines: agent-jobs/MACHINES.md (read at open)
