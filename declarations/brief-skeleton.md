Answer as a chat model — no agentic operations. Do not run tools, commands or tests, and do not change any of your settings; an agentic session does all of that.

There's a <N–M>-minute time limit for you to output your answer — i.e. thinking even shouldn't last over that time period. After that there's a hard stop which is not graceful — unfortunately, your progress gets lost. It seems to me that the only solution is for you to output even if the result seems unfinished to you, because the priority for you is to finish on time, not to dwell thinking about finer details and nuances. The other reason for that is diminishing returns on time spent — your answer will be good enough if you spend thinking on the task either 15 or 40 minutes. 1. If you output only partly then that can be continued in a new session, which is better than nothing. 2. If you output as specs then the mechanical writing of code can be done by the orchestrator (a smaller model which sets the task and then integrates, tests it).

## The task
<one or two sentences; less is better>

## Facts (observed; a settled decision is a fact too)
<each with its path or source>

## Assumptions (mine; may be wrong — mark or drop)
<...>

## Open questions (mine)
<...>

## Context and code (verbatim; labelled with path)
<files whole or in generous excerpts>

## Output contract
In this order: <what to return, in what order>. Cap: ≤<LINES> lines; hard stop at <N–M> minutes — output even if unfinished. First line, verbatim: `reply <n>-<slug>`. The artifact travels as the block below, ONE physical line between its markers, breaks replaced by the dictated delimiter, absent from the artifact — default ⏎ (U+23CE); if the artifact documents it, dictate another or ship a raw file — decoded mechanically after the cut. Trim commentary before the artifact first. End with COMPLETE on its own line; if cut off, end without it.

=== begin <name> ===
<the artifact, ONE <BREAK>-joined line>
=== end <name> ===

Before answering, challenge key assumptions, consider a credible alternative, and check likely failure cases; give the requested output with concise rationale and any material uncertainties.
