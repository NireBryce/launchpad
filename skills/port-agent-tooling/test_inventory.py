#!/usr/bin/env python3
"""Fixture tests for inventory.py: each test builds the case it checks.

  python3 -m unittest discover -s skills/port-agent-tooling -p 'test_*.py'
"""

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import inventory


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def skill(name, desc, body=''):
    return f'---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n{body}'


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        inventory.main(['--format', 'json', *argv])
    return json.loads(buf.getvalue())


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.a = base / 'alpha'
        self.b = base / 'beta'
        self.t = base / 'target'
        for d in (self.a, self.b, self.t):
            d.mkdir()
        write(self.a, 'AGENTS.md', '# Agents\n\nalpha rules.\n')
        os.symlink('AGENTS.md', self.a / 'CLAUDE.md')
        write(self.a, '.agents/skills/ship/SKILL.md', skill(
            'ship', 'Lands work through a PR.',
            '\nUse skill `use-a-worktree` first. alpha-host only.\n'
            'Broke on 2026-01-02 (#12, §3).\n'))
        write(self.a, '.agents/skills/use-a-worktree/SKILL.md', skill(
            'use-a-worktree', 'Sets up a worktree.'))
        write(self.a, '.githooks/commit-msg', '#!/bin/sh\n# Fix trailers.\n')
        write(self.a, '.agents/hooks/git-guard.sh', '#!/bin/sh\n# Guard.\n')
        write(self.a, 'wiki/agent-lessons-learned.md', '# Lessons\n')
        write(self.a, 'wiki/agent-lessons-learned/1-first.md', '# 1\n§1\n')
        write(self.a, 'wiki/agent-lessons-learned/2-second.md', '# 2\n§2\n')
        write(self.a, '.claude/settings.json', json.dumps({
            'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
                {'type': 'command', 'command': 'x'}]}]},
            'permissions': {'allow': ['Bash(make test)']}}))
        write(self.a, '.agents/lessons-map.toml', '# map\n')
        write(self.a, '.github/workflows/ci.yml',
              'jobs:\n  t:\n    steps:\n      - run: python3 tools/check_trailers.py\n')
        write(self.a, 'tools/check_trailers.py', '"""Fail on bad trailers."""\n')
        write(self.a, 'tools/unwired.py', '"""Nobody calls this."""\n')
        write(self.a, 'src/main.py', 'print(1)\n')
        write(self.b, '.claude/skills/ship/SKILL.md', skill(
            'ship', 'Ships things.'))
        write(self.t, '.agents/skills/use-a-worktree/SKILL.md', skill(
            'use-a-worktree', 'Target copy.'))

    def tearDown(self):
        self.tmp.cleanup()

    def items(self, report, label):
        return {i['path']: i for i in report['sources'][label]['items']}

    def test_finds_each_surface_and_ignores_code(self):
        r = run(str(self.a))
        got = {p: i['kind'] for p, i in self.items(r, 'alpha').items()}
        self.assertEqual(got, {
            'AGENTS.md': 'instructions',
            'CLAUDE.md': 'instructions',
            '.agents/skills/ship/SKILL.md': 'skill',
            '.agents/skills/use-a-worktree/SKILL.md': 'skill',
            '.githooks/commit-msg': 'githook',
            '.agents/hooks/git-guard.sh': 'hook',
            'wiki/agent-lessons-learned.md': 'lessons',
            'wiki/agent-lessons-learned/': 'lessons',
            '.claude/settings.json': 'settings',
            '.agents/lessons-map.toml': 'agent-config',
            '.github/workflows/ci.yml': 'ci',
            'tools/check_trailers.py': 'wired-script',
        })

    def test_wired_script_names_its_caller(self):
        i = self.items(run(str(self.a)), 'alpha')['tools/check_trailers.py']
        self.assertEqual(i['wired-by'], '.github/workflows/ci.yml')
        self.assertEqual(i['summary'], 'Fail on bad trailers.')

    def test_lesson_articles_collapse_to_one_row(self):
        i = self.items(run(str(self.a)), 'alpha')['wiki/agent-lessons-learned/']
        self.assertEqual(i['articles'], 2)
        self.assertEqual(i['evidence']['lessons'], 2)

    def test_settings_summary_names_hook_events(self):
        i = self.items(run(str(self.a)), 'alpha')['.claude/settings.json']
        self.assertEqual(i['summary'],
                         'hooks: PreToolUse (1 commands); '
                         '1 allowed permissions')

    def test_symlink_reported_not_read(self):
        i = self.items(run(str(self.a)), 'alpha')['CLAUDE.md']
        self.assertEqual(i['symlink'], 'AGENTS.md')
        self.assertNotIn('lines', i)

    def test_nouns_evidence_and_coupling(self):
        i = self.items(run(str(self.a), '--noun', 'alpha-host'),
                       'alpha')['.agents/skills/ship/SKILL.md']
        self.assertEqual(i['name'], 'ship')
        self.assertEqual(i['summary'], 'Lands work through a PR.')
        self.assertEqual(i['nouns'], 1)  # only the line naming alpha-host
        self.assertEqual(i['evidence'],
                         {'dates': 1, 'issues': 1, 'lessons': 1})
        self.assertEqual(i['names'], ['use-a-worktree'])

    def test_zero_nouns_is_reachable_and_nonzero_too(self):
        r = run(str(self.a))
        items = self.items(r, 'alpha')
        self.assertEqual(
            items['.agents/skills/use-a-worktree/SKILL.md']['nouns'], 0)
        self.assertGreater(items['AGENTS.md']['nouns'], 0)  # "alpha rules"

    def test_shared_across_sources_and_in_target(self):
        r = run(str(self.a), str(self.b), '--target', str(self.t))
        a = self.items(r, 'alpha')
        self.assertEqual(a['.agents/skills/ship/SKILL.md']['shared'],
                         ['beta'])
        self.assertTrue(a['.agents/skills/use-a-worktree/SKILL.md']
                        .get('in-target'))
        self.assertNotIn('in-target', a['.agents/skills/ship/SKILL.md'])
        self.assertEqual([i['path'] for i in r['target']['items']],
                         ['.agents/skills/use-a-worktree/SKILL.md'])

    def test_non_standard_default_branch_is_a_noun(self):
        subprocess.run(['git', 'init', '-q', str(self.a)], check=True)
        subprocess.run(['git', '-C', str(self.a), 'symbolic-ref',
                        'refs/remotes/origin/HEAD',
                        'refs/remotes/origin/experimental'], check=True)
        self.assertIn('experimental', inventory.repo_nouns(self.a, []))

    def test_markdown_renders(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            inventory.main([str(self.a), '--target', str(self.t)])
        md = buf.getvalue()
        self.assertIn('## Source: alpha', md)
        self.assertIn('symlink -> `AGENTS.md`', md)
        self.assertIn('## Target: target', md)


if __name__ == '__main__':
    unittest.main()
