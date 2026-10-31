---
name: git-hook-safe-tests
description: Keeps a test suite that shells out to git from writing into the real repository when it runs inside a git hook.
when_to_use: Adding a pre-push or pre-commit hook that runs tests, writing a test that runs git in a temp directory, or tests passing in a shell but failing or misbehaving under a hook.
---

# Keeping tests out of the hook's repository

## Applies to

A repository whose tests run git (`git init` in a temp dir, `git commit`,
`git config`, `git ls-files`) **and** that runs those tests from a git
hook, or might: a pre-push or pre-commit hook calling the test command, a
CI step inside a hook, any tool that runs your suite from one. Not for
hook code that itself runs git; that needs `git -C "$repo_root"`, a
different problem.

## What goes wrong

Git exports `GIT_DIR`, `GIT_INDEX_FILE` and related variables to every
hook. Inherited by the test process, they override discovery: `git -C
/tmp/xyz init` reinitialises the hook's repo, `git -C /tmp/xyz config
user.name t` writes into the hook's **shared repo config**, `git -C
/tmp/xyz add -A && git commit` stages and commits fixture files onto the
hook's current branch. `-C` changes the directory, not the repository.

What it looked like when it happened: tests that passed in a shell
failed only under pre-push, so the push was refused. Meanwhile the
refused runs had already left their traces:
- the shared config read `user.name=t`, `user.email=t@t`,
  `commit.gpgsign=false` and `core.bare=true`;
- a local branch had a run of commits named "base";
- several worktrees' indexes were full of fixture files.

The next real commit made from any worktree was authored `t <t@t>`,
unsigned, and merged before anyone noticed.

## The fix, in two places

1. **The test entry point** (whatever CI and the hook call) clears the
   variables before running anything:

   ```sh
   unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR \
       GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
   ```

2. **The test package itself**, so the suite is safe however it's run.
   For Python, in `tests/__init__.py` (runs before any test module), strip
   exactly what `git rev-parse --local-env-vars` lists:

   ```python
   import os, re
   REPO_LOCAL_GIT_ENV = (
       'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG',
       'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_OBJECT_DIRECTORY',
       'GIT_DIR', 'GIT_WORK_TREE', 'GIT_IMPLICIT_WORK_TREE', 'GIT_GRAFT_FILE',
       'GIT_INDEX_FILE', 'GIT_NO_REPLACE_OBJECTS', 'GIT_REPLACE_REF_BASE',
       'GIT_PREFIX', 'GIT_SHALLOW_FILE', 'GIT_COMMON_DIR')
   for name in list(os.environ):
       if name in REPO_LOCAL_GIT_ENV or re.match(
               r'^GIT_CONFIG_(KEY|VALUE)_\d+$', name):
           del os.environ[name]
   ```

   Other runners have an equivalent: a pytest `conftest.py` at the root, a
   Go `TestMain`, a Jest `globalSetup`.

Fixtures should also give git an identity and config of their own
(`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, explicit
`GIT_AUTHOR_*`), so a test never depends on, or writes to, the user's.

## Prove it

A test that runs the git-writing tests in a subprocess with `GIT_DIR`
aimed at a scratch repo, then compares that repo's config, branch list and
index before and after. It must fail with step 2 removed; skill
`prove-tests-bite` does that check.

## If it already happened

Check before trusting anything:
- the repo config, `git config --file .git/config --list`, for `user.*`,
  `commit.gpgsign` and `core.bare` against the global config and a
  sibling clone;
- every worktree's `git reflog` for commits you didn't make;
- every worktree's `git status`.

Restore the config by hand. Rebuild the index with a mixed `git reset`,
which leaves the working tree alone. Move a branch carrying junk commits
back by recreating it from its remote, not by force-pushing over the
remote. Then look for commits authored with the fixture identity
(`git log --format='%h %an' | grep ' t$'`) and decide whether rewriting
them is worth it.
