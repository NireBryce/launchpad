---
name: prove-tests-bite
description: Shows that a branch's new or changed tests fail without the change they test, by reverting the non-test files in a throwaway worktree and running the tests again.
when_to_use: Adding a test for a fix or a new check, before saying a test covers a change, or reviewing a PR whose tests might pass either way.
---

# Proving the tests bite

## Applies to

Any change that comes with tests and claims they cover it: a bug fix with a
regression test, a new check with its fixtures, a reviewer asking "does
this test actually catch it?". Not for test-only changes (there is nothing
to revert), and not a substitute for reading the tests: a test can bite
and still test the wrong thing.

## Why

A test that passes on the fixed code proves nothing until it is also seen
failing on the unfixed code. Tests written after the fix pass on the first
try by construction, which is exactly when they're least examined: an
assertion on the wrong value, a fixture that never reaches the branch
under test, a mock that answers for the code. Reverting the change and
watching the test fail is the cheap step that separates the two.

Done by hand it is a `git stash` or copy dance, and done often it's worth
a script. Run by hand on every PR of one session, it caught a test
whose case passed on both versions: a path with `..` in the middle that
resolved either way, so the fix it claimed to cover was never exercised.
Building the script then turned up a stale-bytecode false negative (see
Traps), which a by-hand run can hit just as easily.

## Steps

1. Commit the change and its tests (the script reads committed state).
2. Run, from anywhere in the repo:

   ```sh
   python3 tests_bite.py --base origin/main \
     --test-cmd 'python3 -m unittest discover -s tests -t .'
   ```

   It makes a detached worktree of HEAD, runs the command (it must pass),
   reverts every file the branch changed since the merge base **except**
   test files, runs the command again, and removes the worktree.
3. Read the verdict:
   - **BITES** (exit 0): the tests fail without the change. Good.
   - **DOES NOT BITE** (exit 1): they pass either way. Fix the test, not the
     verdict: find the assertion that should have failed and make it
     depend on the change.
   - exit 2: setup (bad ref, no test files changed, tests failing on HEAD).
4. Say it in the PR's verification: "the new tests fail with the change
   reverted".

## Getting the split right

`--tests` globs decide what counts as a test (and is kept); everything
else is reverted. The defaults cover `tests/**`, `test/**`, `test_*.py`,
`*_test.py`, `*_test.go`, `*.test.*` and `*_spec.*`.

- **The change is test infrastructure** (a fixture helper, a conftest, a
  test package's `__init__`): the defaults keep it as a test, nothing that
  matters is reverted, and it reports DOES NOT BITE. Name only the new test
  file(s) with `--tests`, so the infrastructure is reverted with the rest,
  and run just those tests:

  ```sh
  python3 tests_bite.py --base origin/main \
    --tests 'tests/test_new_thing.py' \
    --test-cmd 'python3 -m unittest tests.test_new_thing'
  ```

- **One test of several:** a narrower `--test-cmd` (a single module) says
  which test bites; the whole suite only says some test does.

## Traps the script handles

- **Stale bytecode.** A reverted Python file of the same size, written in
  the same second, is served from the first run's `.pyc` and the new code
  gets tested again: a false DOES NOT BITE. The script runs with
  `PYTHONDONTWRITEBYTECODE=1` and clears `__pycache__` between runs. For
  another language's build cache, make `--test-cmd` clean it first.
- **A git hook's environment.** Run from a hook, `GIT_DIR` and friends
  would aim the test command's git at the hook's repo; the script clears
  them (skill `git-hook-safe-tests`).
- **Your checkout.** Never touched; everything happens in the throwaway
  worktree.

## Files

- `tests_bite.py`: the script. Stdlib only, Python 3.11+.
- `test_tests_bite.py`: its fixture tests
  (`python3 -m unittest discover -s <this dir> -p 'test_*.py'`).
