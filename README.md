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
