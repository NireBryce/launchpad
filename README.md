# launchpad

Holding area for work to be spun off into its own repos.

## Contents

- [`skills/port-agent-tooling/`](skills/port-agent-tooling/SKILL.md) --
  a harness-neutral skill for finding which agent tooling (skills, rules,
  hooks, scripts, doc conventions, instruction-file sections) in one or
  more source repos is worth porting to a target repo, and porting it.
  Ships `inventory.py`, a read-only stdlib scanner, with fixture tests:

  ```sh
  python3 -m unittest discover -s skills/port-agent-tooling -p 'test_*.py'
  ```

- [`skills/land-pr-series/`](skills/land-pr-series/SKILL.md) -- landing
  several related PRs in order without force-pushing: trial-merge them
  together, bring the trunk in with a merge, resolve conflicts by
  meaning, re-check, merge pinned to the full head SHA.
- [`skills/review-prs-in-parallel/`](skills/review-prs-in-parallel/SKILL.md)
  -- one read-only reviewer subagent per PR, a prompt frame for them, and
  verifying every finding before fixing it.
- [`skills/prove-tests-bite/`](skills/prove-tests-bite/SKILL.md) --
  showing a branch's tests fail with its change reverted. Ships
  `tests_bite.py`, with fixture tests:

  ```sh
  python3 -m unittest discover -s skills/prove-tests-bite -p 'test_*.py'
  ```
- [`skills/git-hook-safe-tests/`](skills/git-hook-safe-tests/SKILL.md) --
  keeping a test suite that runs git from writing into the real repo when
  a git hook runs it, and what to check if it already has.
