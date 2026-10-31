#!/usr/bin/env python3
"""Do a branch's tests catch the change they claim to test?

  tests_bite.py --base REF --test-cmd 'CMD' [--tests 'GLOB']... [--repo DIR]

In a throwaway detached worktree of HEAD, it runs CMD once as-is (it must
pass), then reverts every file the branch changed since the merge base
with REF *except* the tests (files matching a --tests glob; default
`tests/**`, `test_*.py`, `*_test.go`, `*.test.*`, `*_spec.*`), and runs
CMD again. The tests "bite" if that second run fails: they depend on the
change. If it still passes, the new tests would have passed without the
change, so they prove nothing about it.

Exit 0 bites, 1 doesn't bite, 2 setup error (bad ref, nothing to revert,
CMD failing on HEAD itself). Only committed state is used: commit first.
The worktree is removed on exit; your checkout is never touched. Git
variables a hook exports (GIT_DIR and friends) are cleared, so CMD never
reaches the repo this was run from.

Stdlib only; Python 3.11+.
"""
import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TESTS = ['tests/**', 'test/**', '**/test_*.py', '**/*_test.py',
                 '**/*_test.go', '**/*.test.*', '**/*_spec.*', 'test_*.py']
REPO_LOCAL = ('GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG',
              'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT',
              'GIT_OBJECT_DIRECTORY', 'GIT_DIR', 'GIT_WORK_TREE',
              'GIT_IMPLICIT_WORK_TREE', 'GIT_GRAFT_FILE', 'GIT_INDEX_FILE',
              'GIT_NO_REPLACE_OBJECTS', 'GIT_REPLACE_REF_BASE', 'GIT_PREFIX',
              'GIT_SHALLOW_FILE', 'GIT_COMMON_DIR')


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in REPO_LOCAL
            and not k.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_'))}


def git(repo, *args, check=True):
    r = subprocess.run(['git', '-C', str(repo), *args], env=clean_env(),
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f'tests_bite: git {" ".join(args)}: '
                         f'{r.stderr.strip()}')
    return r


def is_test(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def run_cmd(cmd, cwd):
    # No bytecode cache: a reverted file of the same size, checked out in
    # the same second, would otherwise be served from the first run's
    # .pyc and the change would still be tested.
    env = dict(clean_env(), PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run(cmd, shell=True, cwd=cwd, env=env,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base', required=True)
    ap.add_argument('--test-cmd', required=True)
    ap.add_argument('--tests', action='append',
                    help='glob for test files (repeatable)')
    ap.add_argument('--repo', default='.')
    a = ap.parse_args(argv)
    globs = a.tests or DEFAULT_TESTS
    repo = git(a.repo, 'rev-parse', '--show-toplevel').stdout.strip()

    base = git(repo, 'merge-base', a.base, 'HEAD').stdout.strip()
    changed = git(repo, 'diff', '--name-status', '--no-renames', base,
                  'HEAD').stdout.splitlines()
    revert = [(st, p) for st, p in (ln.split('\t', 1) for ln in changed)
              if not is_test(p, globs)]
    tests = [p for _, p in (ln.split('\t', 1) for ln in changed)
             if is_test(p, globs)]
    if not tests:
        print('tests_bite: the branch changes no test files (check --tests)')
        return 2
    if not revert:
        print('tests_bite: the branch changes only tests; nothing to revert')
        return 2

    tmp = Path(tempfile.mkdtemp(prefix='tests-bite-'))
    wt = tmp / 'wt'
    try:
        git(repo, 'worktree', 'add', '-q', '--detach', str(wt), 'HEAD')
        rc, out = run_cmd(a.test_cmd, wt)
        if rc != 0:
            print(f'tests_bite: the tests fail on HEAD itself (exit {rc}); '
                  f'fix that first\n{out}')
            return 2
        for status, path in revert:
            if status.startswith('A'):
                (wt / path).unlink()
            else:
                git(wt, 'checkout', base, '--', path)
        for cache in wt.rglob('__pycache__'):
            shutil.rmtree(cache, ignore_errors=True)
        rc, out = run_cmd(a.test_cmd, wt)
        print(f'tests_bite: reverted {len(revert)} non-test file(s) to '
              f'{base[:12]}, kept {len(tests)} test file(s)')
        if rc != 0:
            print(f'tests_bite: BITES -- the tests fail without the change '
                  f'(exit {rc})')
            return 0
        print('tests_bite: DOES NOT BITE -- the tests still pass without '
              'the change, so they prove nothing about it')
        return 1
    finally:
        git(repo, 'worktree', 'remove', '--force', str(wt), check=False)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
