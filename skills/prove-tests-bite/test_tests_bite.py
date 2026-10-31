"""tests_bite.py on throwaway repos: a test that depends on the change
bites, one that doesn't is reported, setup errors exit 2, and a git hook's
GIT_DIR never reaches the repo under test."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tests_bite  # noqa: E402

CMD = f'{sys.executable} -m unittest discover -s tests -t .'


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = tests_bite.clean_env()
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t.invalid',
                        GIT_COMMITTER_NAME='t',
                        GIT_COMMITTER_EMAIL='t@t.invalid')
        self.git('init', '-q', '-b', 'main')
        self.write('calc.py', 'def f():\n    return 1\n')
        self.write('tests/__init__.py', '')
        self.commit('base')
        self.git('checkout', '-q', '-b', 'feature')

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.root), *args], env=self.env,
                       check=True, capture_output=True)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', msg)

    def bite(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = tests_bite.main(['--base', 'main', '--test-cmd', CMD,
                                  '--repo', str(self.root), *extra])
        return rc, out.getvalue()


class Bites(Repo):
    def test_a_test_of_the_change_bites(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.write('tests/test_calc.py', 'import unittest, calc\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.assertEqual(calc.f(), 2)\n')
        self.commit('f returns 2')
        rc, out = self.bite()
        self.assertEqual(rc, 0, out)
        self.assertIn('BITES', out)

    def test_a_test_that_passes_either_way_does_not(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.write('tests/test_calc.py', 'import unittest, calc\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.assertTrue(callable(calc.f))\n')
        self.commit('f returns 2, weak test')
        rc, out = self.bite()
        self.assertEqual(rc, 1, out)
        self.assertIn('DOES NOT BITE', out)

    def test_a_new_module_is_removed_for_the_second_run(self):
        self.write('extra.py', 'X = 1\n')
        self.write('tests/test_extra.py', 'import unittest, extra\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.assertEqual(extra.X, 1)\n')
        self.commit('add extra')
        self.assertEqual(self.bite()[0], 0)


class SetupErrors(Repo):
    def test_failing_on_head_is_exit_2(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.write('tests/test_calc.py', 'import unittest\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.fail()\n')
        self.commit('broken')
        self.assertEqual(self.bite()[0], 2)

    def test_no_test_changes_or_only_tests_is_exit_2(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.commit('no tests')
        self.assertEqual(self.bite()[0], 2)

    def test_checkout_is_untouched_and_worktree_removed(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.write('tests/test_calc.py', 'import unittest, calc\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.assertEqual(calc.f(), 2)\n')
        self.commit('f returns 2')
        self.bite()
        self.assertIn('return 2', (self.root / 'calc.py').read_text())
        wts = subprocess.run(['git', '-C', str(self.root), 'worktree',
                              'list'], env=self.env, capture_output=True,
                             text=True).stdout.strip().splitlines()
        self.assertEqual(len(wts), 1)


class HookEnv(Repo):
    def test_an_inherited_git_dir_is_ignored(self):
        self.write('calc.py', 'def f():\n    return 2\n')
        self.write('tests/test_calc.py', 'import unittest, calc\n'
                   'class T(unittest.TestCase):\n'
                   '    def test(self): self.assertEqual(calc.f(), 2)\n')
        self.commit('f returns 2')
        with tempfile.TemporaryDirectory() as other:
            subprocess.run(['git', 'init', '-q', other], env=self.env,
                           check=True)
            saved = os.environ.get('GIT_DIR')
            os.environ['GIT_DIR'] = str(Path(other) / '.git')
            try:
                rc, out = self.bite()
            finally:
                if saved is None:
                    os.environ.pop('GIT_DIR')
                else:
                    os.environ['GIT_DIR'] = saved
        self.assertEqual(rc, 0, out)


if __name__ == '__main__':
    unittest.main()
