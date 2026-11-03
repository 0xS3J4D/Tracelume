# Writing style

How we write README text, docs, UI labels and error messages. Short version: write like an
experienced examiner explaining the tool to a colleague.

## Rules
- **Say what it does, plainly.** "Recovers deleted SQLite rows from free pages", not
  "powerful deleted-data capabilities".
- **Lead with the action.** Headings and buttons start with a verb or a noun the user knows:
  *Register evidence*, *Run all*, *Export PDF report*.
- **Short sentences.** One idea per sentence. Cut words that don't change the meaning.
- **Active voice.** "Tracelume hashes the file", not "the file is hashed by Tracelume" —
  unless the actor doesn't matter.
- **Be exact about limits.** If something is beta, untested on real devices, Linux-only or
  slower on Apple Silicon, say so where the user meets it.
- **Never overstate.** Only describe features that work today. Planned work goes in the
  roadmap, labelled *planned*.
- **Numbers and names over adjectives.** "17 tools", "SHA-256 and MD5", "UTC".
- **Contractions are fine** (*don't*, *it's*). Avoid exclamation marks except in thanks.
- **British or American spelling?** British (*licence*, *normalise*), consistently.

## Words we avoid
*delve, leverage, seamless, robust, cutting-edge, empower, elevate, streamline,
game-changer, revolutionary, harness, realm, tapestry, crucial, pivotal, comprehensive,
"in conclusion", "it's worth noting", "furthermore"*. Also avoid forced groups of three and
question-and-answer padding ("Why does this matter? Because …").

## UI text
- Buttons: verb first, no trailing punctuation (*Create case*).
- Errors: what happened + what to do. "No device found. Check the cable and unlock the
  phone." Not "An error occurred."
- Times: always show the zone (*UTC*). Never present a guessed time zone as fact.

## Forensic language
- *Artifact*, *evidence item*, *case*, *examiner*, *chain of custody*, *recovered (deleted)
  record*. Use them the same way everywhere.
- Carved or AI-produced results are always labelled as such.
