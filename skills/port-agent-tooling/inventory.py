#!/usr/bin/env python3
"""Inventory the agent tooling in one or more source repos, for porting.

  inventory.py [--target DIR] [--noun WORD]... [--format md|json]
               [--clone-dir DIR] SOURCE...

SOURCE is a local checkout or a git URL (URLs are shallow-cloned into
--clone-dir, default a fresh temp dir). Read-only: nothing in a source is
executed, imported or written; files are only read as text.

For each source it lists every agent-facing surface it can find by
convention -- instruction files (AGENTS.md, CLAUDE.md, ...), skills
(any */SKILL.md), path-scoped rules, harness settings and the hooks they
wire, git hooks, agent scripts, CI workflows, PR/issue templates, and
docs that look like a style guide, an index or a lessons-learned log --
with what the porting skill's tests need about each item:

  nouns    lines naming a repo noun (owner, repo name, a non-standard
           default branch, plus every --noun): how much stripping the
           ported form needs. Not a verdict -- a general mechanism can
           still be written in local nouns.
  evidence dated lines, issue/PR refs (#N), lesson refs (§N): whether
           the item has history behind it, the strongest porting signal.
  wired-script  a repo file that CI, a git hook or harness settings call
           by path, outside the agent directories (often a convention's
           enforcing layer).
  names    other skills in the same source it mentions: candidate
           couplings, to confirm by reading (a passing "see also" is not
           a dependency).

With several sources, a skill name present in more than one is marked
`shared` (independent reinvention is evidence of generality). With
--target, items whose skill name or path already exists in the target
are marked `in-target` (a file at the same path but not the same skill is
`path-exists`), and the target's own surfaces are summarised so
the fit test has something to read.

Stdlib only; Python 3.11+.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Never agent surfaces, at any depth.
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__',
             '.direnv'}
# Build output when at the repo root; a `tools/target/` or `docs/build/`
# deeper down may be real source, so those are walked.
ROOT_ONLY_SKIP = {'result', 'build', 'dist', 'target'}

INSTRUCTION_FILES = ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'CONVENTIONS.md',
                     '.cursorrules', '.windsurfrules',
                     '.github/copilot-instructions.md']
CONTRIBUTING_FILES = ['CONTRIBUTING.md', 'docs/CONTRIBUTING.md',
                      '.github/CONTRIBUTING.md']
RULE_GLOBS = ['.claude/rules/*.md', '.agents/rules/*.md',
              '.cursor/rules/*.mdc', '.cursor/rules/*.md']
SETTINGS_FILES = ['.claude/settings.json', '.agents/settings.json',
                  '.zcode/settings.json', '.codex/config.toml',
                  '.pre-commit-config.yaml', 'lefthook.yml', 'lefthook.yaml']
HOOK_DIRS = ['.agents/hooks', '.claude/hooks', '.githooks', '.husky']
SCRIPT_DIRS = ['.agents/scripts', '.claude/scripts']
TEMPLATE_GLOBS = ['.github/pull_request_template.md',
                  '.github/PULL_REQUEST_TEMPLATE.md',
                  'PULL_REQUEST_TEMPLATE.md',
                  'docs/PULL_REQUEST_TEMPLATE.md',
                  '.github/PULL_REQUEST_TEMPLATE/*.md',
                  '.github/ISSUE_TEMPLATE/*']
CI_GLOBS = ['.github/workflows/*.yml', '.github/workflows/*.yaml',
            '.gitlab-ci.yml', '.forgejo/workflows/*.yml',
            '.gitea/workflows/*.yml']
# Docs whose *name* says they hold a convention or a lessons log. Matched
# against the basename, lowercased, of markdown files anywhere.
DOC_KINDS = [
    ('lessons', re.compile(r'lessons|postmortem|incident|retro')),
    ('styleguide', re.compile(r'style-?guide|conventions')),
    ('index', re.compile(r'^00-index|^index(-for-agents)?\.md$')),
]

DATE_RX = re.compile(r'\b20\d\d-\d\d-\d\d\b')
# An issue or PR reference, not any `#N`: a bare `#7` is as often a list
# cross-reference. Counted: `issue #N`, `PR #N`, `/issues/N`, `/pull/N`,
# and a `#N` opening or closing a parenthesis (`(#182)`, `(#12, §3)`,
# `(§39, #72)`).
ISSUE_RX = re.compile(
    r'(?i:\b(?:issues?|prs?|pull requests?)\s+#\d+)'
    r'|/(?:issues|pull)/\d+\b|\(#\d+\b|(?<![\w/&])#\d+\)')
LESSON_RX = re.compile(r'§\s?\d+')
FRONT_RX = re.compile(r'\A---\n(.*?)\n---\n', re.S)
H1_RX = re.compile(r'^#\s+(.+)$', re.M)
BACKTICK_RX = re.compile(r'`([a-z0-9][a-z0-9-]*)`')
STANDARD_BRANCHES = {'main', 'master', 'trunk', 'develop'}


def git(root, *args):
    try:
        r = subprocess.run(['git', '-C', str(root), '-c',
                            'core.fsmonitor=false', *args],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return r.stdout.strip() if r.returncode == 0 else ''


def is_url(s):
    return bool(re.match(r'^(https?|ssh|git|file)://|^[\w.-]+@[\w.-]+:', s))


def resolve_source(spec, clone_dir, n=0, missing_ok=False):
    """A local path as-is; a URL shallow-cloned into its own numbered
    directory, so two URLs ending in the same name never share a clone.
    Returns (label, Path), or (label, None) for a missing path when
    `missing_ok`."""
    if not is_url(spec):
        p = Path(spec).resolve()
        if not p.is_dir():
            if missing_ok:
                return p.name, None
            sys.exit(f'inventory: not a directory: {spec}')
        return p.name, p
    name = re.sub(r'\.git$', '', spec.rstrip('/').rsplit('/', 1)[-1])
    dest = Path(clone_dir) / f'{n}-{name}'
    if dest.exists():
        url = git(dest, 'remote', 'get-url', 'origin')
        if url != spec:
            sys.exit(f'inventory: {dest} holds a clone of {url or "nothing"},'
                     f' not {spec}; use an empty --clone-dir')
        print(f'inventory: reusing the clone at {dest}', file=sys.stderr)
    else:
        r = subprocess.run(['git', 'clone', '--quiet', '--depth', '1',
                            spec, str(dest)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f'inventory: clone failed for {spec}: {r.stderr.strip()}')
    return name, dest


def repo_nouns(root, extra):
    """Words that mark a line as repo-specific."""
    nouns = {root.name}
    url = git(root, 'remote', 'get-url', 'origin')
    m = re.search(r'[:/]([^/:]+)/([^/]+?)(?:\.git)?$', url)
    if m:
        nouns.update(m.groups())
    head = git(root, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    branch = head.split('/', 1)[-1] if head else ''
    if branch and branch not in STANDARD_BRANCHES:
        nouns.add(branch)
    nouns.update(extra)
    return sorted(n for n in nouns if len(n) >= 3)


def walk(root):
    """Every file, plus every directory symlink (`.claude/skills ->
    ../.agents/skills`), which os.walk lists as a directory and never
    descends into."""
    for dirpath, dirnames, filenames in os.walk(root):
        at_root = Path(dirpath) == Path(root)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not (at_root and d in ROOT_ONLY_SKIP)]
        for d in dirnames:
            if (Path(dirpath) / d).is_symlink():
                yield Path(dirpath) / d
        for f in filenames:
            yield Path(dirpath) / f


def read(path):
    try:
        return path.read_text(errors='replace')
    except (OSError, UnicodeError):
        return ''


def frontmatter(text):
    m = FRONT_RX.match(text)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(':')
            if sep and not line.startswith(' '):
                out[k.strip()] = v.strip()
    return out


DECORATION = re.compile(r'^[\s\-=*_~#/]+|[\s\-=*_~#/]+$')


def summary(text, path=None):
    """A one-line description. Markdown: frontmatter description, else the
    H1. A Python file: its module docstring's first line (read with
    ast.parse, which never runs it). Anything else (scripts and hooks lead
    with a comment header): the first comment or text line with
    decoration (`-- section ----`) stripped and real words in it."""
    suffix = path.suffix if path else ''
    if suffix == '.py':
        try:
            doc = ast.get_docstring(ast.parse(text))
        except (SyntaxError, ValueError):
            doc = None
        if doc:
            return doc.strip().splitlines()[0][:160]
    if suffix in ('', '.md', '.mdc'):
        fm = frontmatter(text)
        if fm.get('description'):
            return fm['description']
        m = H1_RX.search(FRONT_RX.sub('', text, count=1))
        if m:
            return m.group(1).strip()
    for line in FRONT_RX.sub('', text, count=1).splitlines():
        s = DECORATION.sub('', line.strip().strip('"\'')).strip()
        if s.startswith('!') or s.startswith('-*-') or s.startswith('<!--'):
            continue
        if len(re.findall(r'[A-Za-z]{2,}', s)) >= 2:
            return s[:160]
    return ''


def kind_for(rel):
    """The surface a repo-relative path belongs to, or None."""
    p = rel.as_posix()
    name = rel.name
    if name == 'SKILL.md':
        return 'skill'
    if p in INSTRUCTION_FILES:
        return 'instructions'
    if p in CONTRIBUTING_FILES:
        return 'contributing'
    if any(rel.match(g) for g in RULE_GLOBS):
        return 'rule'
    if p in SETTINGS_FILES:
        return 'settings'
    if any(p.startswith(d + '/') for d in HOOK_DIRS):
        return 'githook' if p.startswith(('.githooks/', '.husky/')) else 'hook'
    if any(p.startswith(d + '/') for d in SCRIPT_DIRS):
        return 'script'
    if any(rel.match(g) for g in TEMPLATE_GLOBS):
        return 'template'
    if any(rel.match(g) for g in CI_GLOBS):
        return 'ci'
    if p.startswith(('.agents/', '.claude/')) and '/skills/' not in p:
        return 'agent-config'
    if name.endswith('.md'):
        if any(DOC_KINDS[0][1].search(d.lower()) for d in rel.parts[:-1]):
            return 'lessons-article'
        low = name.lower()
        for k, rx in DOC_KINDS:
            if rx.search(low):
                return k
    return None


def settings_summary(text):
    """Harness settings in one line: which hook events are wired, how
    many commands, how many pre-approved permissions."""
    try:
        data = json.loads(text)
    except ValueError:
        return ''
    if not isinstance(data, dict):
        return 'not a settings object'

    def get(d, key, kind):
        v = d.get(key) if isinstance(d, dict) else None
        return v if isinstance(v, kind) else kind()
    hooks = get(data, 'hooks', dict)
    cmds = sum(len(get(m, 'hooks', list)) for ms in hooks.values()
               if isinstance(ms, list) for m in ms)
    allow = len(get(get(data, 'permissions', dict), 'allow', list))
    parts = [f'hooks: {", ".join(hooks)} ({cmds} commands)' if hooks
             else 'no hooks']
    parts.append(f'{allow} allowed permissions')
    return '; '.join(parts)


def collapse_articles(items):
    """One row per lessons-article directory, not one per article."""
    out, dirs = [], {}
    for i in items:
        if i['kind'] != 'lessons-article':
            out.append(i)
            continue
        d = i['path'].rsplit('/', 1)[0] + '/'
        agg = dirs.get(d)
        if agg is None:
            agg = dirs[d] = {'source': i['source'], 'kind': 'lessons',
                             'path': d, 'lines': 0, 'nouns': 0,
                             'evidence': {'dates': 0, 'issues': 0,
                                          'lessons': 0},
                             'articles': 0, '_text': ''}
            out.append(agg)
        agg['articles'] += 1
        agg['summary'] = f'{agg["articles"]} lesson articles'
        for k in ('lines', 'nouns'):
            agg[k] += i.get(k, 0)
        for k, v in i.get('evidence', {}).items():
            agg['evidence'][k] += v
        agg['_text'] += i.get('_text', '')
    return out


PATH_TOKEN_RX = re.compile(r'[\w.-]+(?:/[\w.-]+)+\.(?:py|sh|bash|js|ts|rb|pl)\b')
WIRING_KINDS = {'ci', 'githook', 'settings', 'hook'}


def wired_scripts(root, items):
    """Repo files that CI, git hooks or harness settings call by path but
    that live outside the conventional agent directories (a CI-only check,
    a hook's helper). Without these, a convention's enforcing layer is
    invisible to the inventory."""
    have = {i['path'] for i in items}
    found = {}
    for i in items:
        if i['kind'] not in WIRING_KINDS:
            continue
        for tok in PATH_TOKEN_RX.findall(i.get('_text', '')):
            tok = tok.lstrip('./')
            for cand in (tok, tok.split('/', 1)[-1]):
                if cand in have or cand in found:
                    break
                if (root / cand).is_file():
                    found[cand] = i['path']
                    break
    return found


def scan(label, root, nouns):
    items = []
    noun_rx = (re.compile('|'.join(re.escape(n) for n in nouns), re.I)
               if nouns else None)
    for path in sorted(walk(root)):
        rel = path.relative_to(root)
        kind = kind_for(rel)
        if kind is None:
            continue
        item = {'source': label, 'kind': kind, 'path': rel.as_posix()}
        if path.is_symlink():
            item['symlink'] = os.readlink(path)
            items.append(item)
            continue
        text = read(path)
        lines = text.splitlines()
        if kind == 'skill':
            item['name'] = frontmatter(text).get('name') or rel.parent.name
        item['summary'] = (settings_summary(text) if path.suffix == '.json'
                           and kind == 'settings' else summary(text, path))
        item['lines'] = len(lines)
        item['nouns'] = (sum(1 for ln in lines if noun_rx.search(ln))
                         if noun_rx else 0)
        item['evidence'] = {
            'dates': len(DATE_RX.findall(text)),
            'issues': len(set(ISSUE_RX.findall(text))),
            'lessons': len(set(LESSON_RX.findall(text))),
        }
        item['_text'] = text
        items.append(item)
    for rel, by in sorted(wired_scripts(root, items).items()):
        text = read(root / rel)
        lines = text.splitlines()
        items.append({
            'source': label, 'kind': 'wired-script', 'path': rel,
            'summary': summary(text, root / rel), 'lines': len(lines),
            'nouns': (sum(1 for ln in lines if noun_rx.search(ln))
                      if noun_rx else 0),
            'evidence': {'dates': len(DATE_RX.findall(text)),
                         'issues': len(set(ISSUE_RX.findall(text))),
                         'lessons': len(set(LESSON_RX.findall(text)))},
            'wired-by': by, '_text': text})
    items = collapse_articles(items)
    # Skill directories that live behind a symlink (.claude/skills ->
    # .agents/skills) are never walked twice: walk() doesn't follow links.
    skills = {i['name'] for i in items if i['kind'] == 'skill' and 'name' in i}
    for i in items:
        text = i.pop('_text', '')
        own = i.get('name')
        named = {m for m in BACKTICK_RX.findall(text)
                 if m in skills and m != own}
        named |= {s for s in skills if s != own
                  and re.search(rf'\bskill [`"]?{re.escape(s)}\b', text)}
        if named:
            i['names'] = sorted(named)
    return items


def mark(sources, target_items):
    skill_sources = {}
    for items in sources.values():
        for i in items:
            if i['kind'] == 'skill' and 'name' in i:
                skill_sources.setdefault(i['name'], set()).add(i['source'])
    t_names = {i.get('name') for i in target_items if i['kind'] == 'skill'}
    t_paths = {i['path'] for i in target_items}
    for items in sources.values():
        for i in items:
            others = skill_sources.get(i.get('name'), set()) - {i['source']}
            if i['kind'] == 'skill' and others:
                i['shared'] = sorted(others)
            if i.get('name') and i.get('name') in t_names:
                i['in-target'] = True
            elif i['path'] in t_paths:
                # The same path is not the same thing: contents may differ.
                i['path-exists'] = True


KIND_ORDER = ['instructions', 'contributing', 'skill', 'rule', 'settings',
              'hook', 'githook', 'script', 'wired-script', 'ci', 'template', 'styleguide',
              'index', 'lessons', 'lessons-article', 'agent-config']


def fmt_evidence(e):
    parts = [f'{v} {k}' for k, v in e.items() if v]
    return ', '.join(parts) or 'none'


def render_md(report):
    out = ['# Agent-tooling inventory', '']
    for label, src in report['sources'].items():
        out += [f'## Source: {label}', '',
                f'Path: `{src["path"]}`; repo nouns: '
                + (', '.join(f'`{n}`' for n in src['nouns']) or 'none'), '']
        items = sorted(src['items'], key=lambda i: (
            KIND_ORDER.index(i['kind']), i['path']))
        out += ['| kind | path | summary | lines | nouns | evidence '
                '| names | flags |', '|---|---|---|---|---|---|---|---|']
        for i in items:
            if 'symlink' in i:
                out.append(f'| {i["kind"]} | `{i["path"]}` | symlink -> '
                           f'`{i["symlink"]}` | | | | | |')
                continue
            flags = []
            if i.get('shared'):
                flags.append('shared: ' + ', '.join(i['shared']))
            if i.get('in-target'):
                flags.append('in-target')
            if i.get('path-exists'):
                flags.append('path-exists in target')
            if i.get('wired-by'):
                flags.append(f'wired by `{i["wired-by"]}`')
            summ = i.get('summary', '').replace('|', '\\|')[:120]
            out.append(
                f'| {i["kind"]} | `{i["path"]}` | {summ} | {i["lines"]} '
                f'| {i["nouns"]} | {fmt_evidence(i["evidence"])} '
                f'| {", ".join(i.get("names", []))} | {"; ".join(flags)} |')
        out.append('')
    t = report.get('target')
    if t:
        out += [f'## Target: {t["label"]}', '', f'Path: `{t["path"]}`', '']
        if not t['items']:
            out += ['No agent-facing surfaces found: everything ported '
                    'starts the layout.', '']
        else:
            out += ['| kind | path | summary |', '|---|---|---|']
            for i in sorted(t['items'], key=lambda i: (
                    KIND_ORDER.index(i['kind']), i['path'])):
                desc = (f'symlink -> `{i["symlink"]}`' if 'symlink' in i
                        else i.get('summary', '').replace('|', '\\|')[:120])
                out.append(f'| {i["kind"]} | `{i["path"]}` | {desc} |')
            out.append('')
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('sources', nargs='+', metavar='SOURCE')
    ap.add_argument('--target', help='the repo the tooling would move to')
    ap.add_argument('--noun', action='append', default=[],
                    help='an extra repo-specific word (repeatable)')
    ap.add_argument('--format', choices=['md', 'json'], default='md')
    ap.add_argument('--clone-dir', help='where URL sources are cloned')
    args = ap.parse_args(argv)

    clone_dir = args.clone_dir or tempfile.mkdtemp(prefix='inventory-')
    report = {'sources': {}}
    sources = {}
    for n, spec in enumerate(args.sources):
        label, root = resolve_source(spec, clone_dir, n)
        if label in sources:
            label = f'{label}@{root}'
        nouns = repo_nouns(root, args.noun)
        sources[label] = scan(label, root, nouns)
        report['sources'][label] = {'path': str(root), 'nouns': nouns,
                                    'items': sources[label]}
    target_items = []
    if args.target:
        tlabel, troot = resolve_source(args.target, clone_dir,
                                       len(args.sources), missing_ok=True)
        if troot is None:
            print(f'inventory: target {args.target} does not exist yet; '
                  'inventorying the sources against an empty target',
                  file=sys.stderr)
        target_items = scan(tlabel, troot, []) if troot else []
        report['target'] = {'label': tlabel,
                            'path': str(troot or args.target),
                            'items': target_items}
    mark(sources, target_items)
    if args.format == 'json':
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print(render_md(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
