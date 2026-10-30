---
name: port-agent-tooling
description: Finds the skills, rules, hooks, scripts and doc conventions in source repos that would work in a target repo, and ports the chosen ones in the target's terms.
when_to_use: Asked what from repo A is worth bringing to repo B, to generalize a repo's agent tooling, to seed a new repo's AGENTS.md or skills from existing ones, or to compare the agent tooling of several repos.
---

# Porting agent tooling between repos

## Applies to

A deliberate pass whose question is "which of the agent tooling in these
repos would earn its place in that one". Sources are one or more repos
whose agents have built up skills, path-scoped rules, guard hooks, git
hooks, agent scripts, doc conventions, a lessons-learned log or a long
AGENTS.md/CLAUDE.md. The target is one repo: an existing project that
has little of this, a new one, or a shared "general" repo that the
tooling will be spun out into.

Not for:

- noticing one candidate while doing other work: record it in the
  source repo's own candidates list, if it keeps one, and move on;
- copying files verbatim: a port that keeps the source's nouns is a
  false claim in the target (see "Port, don't copy");
- filing issues or PRs on a third-party project: only repos the user
  named.

The output comes in two parts, and the user approves between them: a
**report** (what is worth porting, ranked, with the fit to the target),
then **the port** of whatever the user picks, landed through the
target's own git flow.

## Inputs

- **Sources**: local checkouts or git URLs, one or more.
- **Target**: a local checkout. If it doesn't exist yet, the report
  still works; the port waits for it.
- **Repo nouns** for each source: hostnames, user and account names,
  product names, a non-default branch name, the build tool, anything
  that only means something there. `inventory.py` derives the owner, repo
  name and non-standard default branch itself; the rest are passed with
  `--noun`. Five minutes reading the source's AGENTS.md finds them.

## Step 1: inventory

Run the script next to this file. It only reads files as text; nothing
in a source is executed.

```sh
python3 -I inventory.py SOURCE... --target TARGET \
  --noun <word> --noun <word> > inventory.md
```

`--format json` gives the same data for further processing. Per source it
lists every surface found by convention, with: a one-line summary,
`nouns` (lines naming a repo noun), `evidence` (dated lines, `#N` issue
refs, `§N` lesson refs), `names` (other skills it mentions), and flags:
`shared` (a skill of that name exists in another source too) and
`in-target` (the target already has it). The target's own surfaces are
listed last.

The inventory says *where to look*, not what to port. A zero `nouns`
count can still be a source-specific skill written in general words; a
high one can be a general mechanism written in local nouns.

If the user didn't name sources or a scope, ask once: all surfaces, or
one kind (skills only, hooks only, docs conventions only).

## Step 2: profile the target

Read the target before judging anything against it. Write down, in the
report, in a few lines:

- what it is (language, size, what it ships, who consumes it);
- its git flow: default branch, whether work lands via PR, CI and what CI
  runs, commit-message conventions (`git log --format=%B -20`);
- its checks: test command, linters, any doc checker;
- its docs: README only, `docs/`, a wiki; any page conventions;
- the agent surfaces it already has (the inventory's last section);
- the harnesses its agents run in, and which of those run hooks at all.
  A hook adds nothing in a harness that doesn't run it, and under an
  unattended permission mode an "ask" prompts nobody.

A mechanism can only be ported to a target that has the thing it acts
on. A skill for keeping wiki pages in sync needs a wiki; a guard for a
build tool needs the build tool.

## Step 3: judge each candidate — three tests

Apply them at the level of the **mechanism**, not the topic. "Docs
maintenance" is a topic; "lint fails when a page's agent summary is
older than the page" is a mechanism. If nearly everything seems to
qualify, the tests are being applied to topics.

1. **Generality.** Restate the item's one-sentence purpose with every
   repo noun removed. Still true and still useful: general. Only true
   with the source's domain vocabulary put back (its build system, its
   platform): general *within that domain*, so it ports only to a target
   in the same domain. Only true for the source's own machines, accounts
   or data: not portable; stop. An item can split: the general half ports,
   the specific half stays.
2. **Fit.** Does the target have what the mechanism acts on (step 2)?
   Would its failure mode happen there? A rule against a mistake the
   target's workflow can't make is noise in its instructions file.
3. **Evidence.** Rank by what stands behind the item, strongest first:
   an enforcing check or hook with a test > a numbered lesson or a dated
   incident it cites > an issue it cites > none. Evidence in the source
   does not transfer as evidence in the target, but it is the best
   predictor of which rules will be needed. `shared` across sources is
   evidence too: two repos reinventing it independently.

Then group by **coupling**: a skill and the check that enforces it, a
hook and the settings that wire it, a rule and the lesson it cites
travel as one candidate or not at all. `names` in the inventory is the
starting point; confirm each by reading, since a "see also" is not a
dependency.

Then split each candidate into its **automatic** half (a hook, a check, a
CI step: it fires without anyone asking) and its **convention** half (an
instruction an agent can skip). The report says which half the port
brings. Porting only the convention half of a mechanism the source held
automatically is a downgrade, and the report has to say so.

## Step 4: classify and report

Each candidate gets exactly one verdict:

| verdict | meaning |
|---|---|
| **port** | mechanism general, fits, worth its weight now; strip nouns and land |
| **port, adapted** | the kernel fits but the procedure must be rewritten for the target's tools (its test command, its branch, its CI) |
| **feature** | better as part of the target's product than its tooling (a source script that is exactly what the target tool does) |
| **later** | general, but the target lacks what it acts on today; name the trigger that would change that |
| **skip** | specific to the source, or no failure mode in the target |

The report: the target profile, then one table per verdict with
candidate, source paths (coupled files included), the general kernel in
one sentence, what to strip or parameterize, evidence, and dependencies
on other candidates. Order the **port** table by evidence, then by
dependency, so the first rows can land alone. End with the order you
would port in and the one question you need answered.

Write it where the user can read it (a file, or the target's issue
tracker if they ask), give the short version in chat, and **stop for
the user's pick**. Don't start porting on the strength of the report.

## Step 5: port, don't copy

For each picked candidate, in the target, on a branch, in the target's
conventions:

- **Rewrite the nouns, keep the rule.** Hostnames, paths, recipe names,
  branch names and tool names become the target's, or become parameters
  where the target has none. Incident narrative stays in the source; the
  ported rule keeps its *reason* in one line, plus a provenance pointer
  ("adapted from `<source>/<path>`") so the next reader can find the
  history.
- **Don't import the source's dates as the target's facts.** A dated
  incident in the source is not something that happened in the target.
  Counts, versions and lists copied from the source rot immediately:
  replace them with the command or file that answers them.
- **Port couplings whole.** A skill whose check isn't ported says the rule
  is unenforced, not that it is enforced.
- **Re-earn the evidence.** A ported check or hook lands with a test
  against the case it exists to catch, in the target's test runner, in
  the same commit. A clean run on a tree that never had the defect proves
  nothing.
- **Match the target's layout** if it has one; if it has none, the
  smallest one that works across harnesses is: `AGENTS.md` canonical,
  `CLAUDE.md` a symlink to it, skills as plain markdown at
  `.agents/skills/<name>/SKILL.md`, and a real `.claude/` directory whose
  `skills`/`settings.json` are symlinks into `.agents/`.
- **Instructions-file lines are the expensive surface**: they load in
  every session. Port a line only when its failure mode is common in the
  target; otherwise put the rule in the skill or rule file for that task
  and leave a one-line pointer.
- **A convention held by one layer isn't held.** A local git hook runs
  only in clones that wired it, so pair it with a CI check of the same
  rule, and with the harness's own setting where one exists (commit
  attribution, say). Each layer backs up the one before.
- **CI runs the contributors' command, not a copy of its steps.** One
  entry point (a recipe, a script) is the checklist; CI and the pre-push
  hook call it, so a step added there gates everything with no second
  edit.
- **Hooks keep their decision form.** A guard that must hold denies,
  because an ask is a no-op under unattended permission modes. Text the
  agent must read goes where the agent sees it, not only where the human
  does. A skill that depends on a hook says so in one tagged line, so an
  agent in a harness without hooks knows to warn the user and check
  commands by hand.
- **Pre-approved permissions are re-justified, not copied.** Port only
  read-only commands with a closed argument surface. A wildcard over a
  general tool (an interpreter, a package manager, a build tool's eval)
  never qualifies.
- **A lesson ports as its rule, in its Home.** The Home is the file an
  agent doing that task already reads (the instructions file, a skill, a
  rule file). The source's account stays in the source behind a pointer.
  A rule that only an index states reaches nobody. If the target keeps a
  lessons log, each entry records what enforces it, and `none` is an
  honest answer.
- **Security analysis stays private.** If a source keeps threat-model
  notes out of public text, keep that rule and don't carry the notes.
  Never copy secrets, key fingerprints, internal hostnames, or personal
  emails, even ones the source committed on purpose.

Land it through the target's flow (its PR process, its CI). If the
target has a doc checker, run it on the ported files.

## Step 6: say what you reached

Per ported item: *written* (in the tree), *checked* (its test and the
target's checks pass), or *used* (an agent session in the target
actually followed or triggered it). A port is rarely past *checked* on
the day it lands; say so, and don't describe a written rule as enforced.

## Running it again

The report is a snapshot. On a re-run, reconcile first: for each item
ported last time, does the source still have it, and has it changed
enough that the port is now behind? Then survey for new items. The
inventory's `in-target` flag marks the ones already ported under the
same name.

## Calibrate

The report is a shortlist, not an inventory: a target usually wants a
handful of items, not the source's whole tooling. A small project with
one maintainer wants the git flow, the commit conventions, the review
checklist and the checks-before-done rule; it rarely wants a wiki
apparatus or a twelve-hook guard suite.

## Files

- `inventory.py`: the step 1 scanner. Stdlib only, Python 3.11+.
- `test_inventory.py`: its fixture tests
  (`python3 -m unittest discover -s <this dir> -p 'test_*.py'`).
- `examples/`: worked reports from real runs. Read one before writing
  your first report; it shows the expected depth.
