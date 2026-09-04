## Project

**LocalAI-Stack** Containing HowTos, docker.compose.yml, scripts etc. All you need to build your own AI-Stack on your hardware.

## Where things are documented

- **How it came to this** — `HISTORY.md` holds all completed work including why it was changed or implemented. Each entry includes a reference to the stack.
- **Which file owns which concern** — `FILEMAP.md`. Read it before creating a file or moving code.
- **Description, requirements, HowTo** — the root `README.md` lists all sub-projects and links to each; every sub-project folder has its own `README.md`. Every `README.md` has a German counterpart `README-DE.md`.
- **Open work and ideas** — `PROJECTPLAN.md` in the base dir including reference to the stack(s).

## Change Control

- **`CLAUDE.md`, `HISTORY.md`, `PROJECTPLAN.md` are approval-gated.** Present a draft for the change and wait for confirmation.

## Verification

Do web research before proposing solutions or commands. Things change rapidly in this field.


## Rules for working with the user

- **Implement only what was explicitly instructed.**
- **Answer only what was asked.**
- **Keep reports and decisions short.**
- **Everything documented is Proof of Concept and playground. Only mention problems for live service.**
- **If several things need to be dicided name the total und present them one after the other, starting with highest priority and severety.**

## Documentation Style

Applies to `CLAUDE.md`, `HISTORY.md`, `FILEMAP.md`, `PROJECTPLAN.md`, `DECISIONS.md`, and both language versions of every `README.md`.

- **`CLAUDE.md`, `HISTORY.md`, `FILEMAP.md`, `PROJECTPLAN.md`, `DECISIONS.md` are written in English only.**
- **Every `README.md` has a German counterpart `README-DE.md`, kept in sync.**
- **A rule stands alone.**
- **Deletion test:** cut the explanation. If the rule still holds, it stays cut.
  If it collapses, the explanation is needed.
- **One bullet, one rule.**
- **Never document what the code already states.** 
- **Only name the alternative where it is a mistake someone would actually make.**
- **Bold marks identifiers and rules.**
- **An adverb earns its place by changing the meaning.**
- **`PROJECTPLAN.md` holds open work.**
- **A `README.md` documents what is built.** An idea that is only named goes to `PROJECTPLAN.md`.
- **`HISTORY.md` is append-only.**
- **Maintainer decides which explanations are needed.** Even if they fail the Deletion Test.

## Code Style

- **Comments in code and config files are English.**
- **Optional components ship commented out in the file they belong to.** A second
  file is a copy that drifts from the original.

## Documentation Protocol

Triggered by the user with `Doku-Protokoll.` at the end of a work session.

**"No change" is a valid result for every step.**

### Phase A — report, write nothing

Respect Documentation Style. Work through steps 1–8 and collect the findings into **one** report, then wait
for approval.

1. **`PROJECTPLAN.md` and `HISTORY.md`**** — list the changes.
3. **`CLAUDE.md`** — propose a change only if a convention or one of these
   working agreements changed.
6. **`FILEMAP.md`** — propose a change only if a file gained, lost or handed over
   a concern.
7. **`README.md`** — Be very focused when changing README.md files. People are actually using them to builkd their test stacks.
8. **Consistency check** — compare `PROJECTPLAN.md` against `HISTORY.md`. Report
   duplicates.

### Phase B — user approval and apply

The user approval is needed to apply changes from Phase A. After applying,
verify: look for duplicates, check touched items against Documentation Style
rules. Report findings.

- **No findings:** commit and push.
- **Findings:** wait for the user to clear them before committing.
