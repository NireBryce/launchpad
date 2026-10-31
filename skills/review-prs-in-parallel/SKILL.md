---
name: review-prs-in-parallel
description: Reviews several open PRs at once with one read-only subagent per PR, then verifies each reported finding before fixing it.
when_to_use: Asked to review a batch of PRs, review everything before shipping, or get a second model's eyes on a set of changes.
---

# Reviewing a set of PRs in parallel

## Applies to

Several PRs that need a correctness review before they land, in a harness
that can run subagents (any model). Not one small PR (review it inline),
and not docs accuracy (a docs fact-check is its own procedure).

## Why one agent per PR

A single reviewer across a set either skims or runs out of room. One per
PR, each with that PR's diff and a few specific questions, finds more,
and the reports come back in parallel. Run that way over a batch of
features that had all passed their own tests and CI, the reviewers found
blocking defects in every PR:
- a crash on paths starting with `@`;
- quadratic blow-up on repeated boilerplate;
- non-ASCII paths silently skipped;
- a commit message claiming files were untracked when they weren't;
- a documented CLI form that only worked when `--root` was also passed.

## The reviewer prompt

Each reviewer gets the same frame plus its PR's specifics:

- **Read-only, stated first.** No edits, commits, pushes or GitHub
  comments. Work only in a throwaway worktree under `/tmp`, and remove it
  after. The findings go back to you, not onto the PR.
- **Where:** repo path, PR number, head branch, base branch, and the diff
  command (`git diff origin/<base>...origin/<head>`, three dots).
- **How to run it:** the worktree command, the test command, any parity
  source to compare against (the original script a port came from, a
  real consumer repo).
- **What the PR claims to do**, in two or three sentences.
- **Specific questions**, not just "review this". Name the edge cases you
  suspect for this change:
  - git and filesystem edges: no HEAD yet, shallow clones, non-ASCII
    paths, a root that isn't a repo;
  - scale: repeated input, large repos;
  - backward compatibility and the public API;
  - whether each test fails without the change;
  - doc claims against the code.
- **Report format:** findings most severe first, each with `file:line`,
  what is wrong, a concrete failure scenario (ideally a command actually
  run), a suggested fix, and BLOCKING or OPTIONAL. Verify each finding
  before reporting it, drop what can't be substantiated, say plainly if
  nothing is wrong, and keep it under a stated word count.

Run them in the background, and keep working while they run (the first
PR's fix can start before the last report arrives).

## Handling the reports

1. **Verify before acting.** A report is a claim. Reproduce each BLOCKING
   finding yourself (run the command, read the line) before fixing it.
   Most will hold; check every one anyway.
2. **Fix on the PR's own branch**, with a test that fails without the fix
   (skill `prove-tests-bite`). Commit messages say "from review:" and list
   what changed.
3. **OPTIONAL findings:** batch them into a later change or list them to
   the user. Don't let them grow the PR.
4. **When a reviewer is wrong,** note why in your summary; don't argue
   with the report.
5. **When a finding is in code the PR didn't introduce,** say so, and fix
   it in its own PR or propose it, rather than widening this one.

## Report to the user

A table: PR, blocking findings (one line each), status (fixed with test,
or why not). Then the optional ones. Say which reviewer model ran, and
that every blocking finding was re-verified before it was fixed.

## See also

- `land-pr-series`: landing the set once it's clean.
- `prove-tests-bite`: the check every fix's test should pass.
