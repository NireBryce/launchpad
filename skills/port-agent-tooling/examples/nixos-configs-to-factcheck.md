# Worked example: nixos-configs → factcheck

_Run 2026-10-30. Source `NireBryce/nixos-configs` at `ecb4ca3`; target
`NireBryce/factcheck` at `9c907bc`. A snapshot: both repos have moved
since, so re-run the inventory instead of trusting the paths here._

```sh
python3 -I inventory.py ../nixos-configs --target ../factcheck \
  --noun nire- --noun elly --noun sops --noun nix --noun tailnet
```

## Target profile

- **What:** a stdlib-only Python 3.11+ CLI that checks a repo's docs
  against the repo. Extracted from nixos-configs' in-tree checker; that
  repo now consumes it as a pinned flake input, and its repo-specific
  checks are plugins that live there.
- **Git flow:** `main` only, linear history, no PRs so far; consumers pin
  by rev, so whatever lands on `main` is what gets pinned. Commits
  already use Conventional-Commits prefixes and a bare
  `Co-Authored-By: Claude` trailer.
- **Checks:** `python -m unittest discover -s tests -t .` plus a
  self-check (`python -m factcheck check`), both in CI on 3.11/3.13/3.14.
  No local git hooks.
- **Docs:** `README.md` only. Its `factcheck.toml` turns off the wiki
  page conventions (`contents`, `dates`, `siblings`) for itself, on
  purpose.
- **Agent surfaces:** none. No AGENTS.md, skills, rules, hooks or
  settings, though agents wrote most of the commits.

So what fits is the git flow, commit hygiene, the review and done-rules,
and the doc-writing skills. Almost none of the wiki machinery fits,
because factcheck has no wiki.

## Port

In dependency order. Each row can land without the ones after it.

| # | candidate | source | general kernel | strip / replace | evidence |
|---|---|---|---|---|---|
| 1 | **Layout** | `AGENTS.md` header, `CLAUDE.md` symlink, `.claude/` real dir with `skills`/`settings.json` symlinks into `.agents/` | One canonical instruction file, harness-specific names as symlinks, skills as plain markdown any harness can read. | nothing; the header's "written by agents" framing stays | a symlinked `.claude/` made Claude Code refuse worktrees (recorded in the source AGENTS.md header) |
| 2 | **AGENTS.md "Before calling it done"** | `AGENTS.md` §"Before calling it done"; lessons §1, §3, §20, §22, §23, §31 | Name the rung you reached. Test a new checker against a case it should catch. Read the output, not the exit status. When a check fires on new work, fix its model before reaching for the escape flag. Before believing a zero, show the query can return non-zero. | rungs become *tests pass*, *self-check passes*, *parity run on a consumer repo*, *used in the consumer's CI*. Drop eval/build/switch. | six numbered lessons. Fixture-per-check is already a README design note; this makes it a rule. §22 (silent name-match misses) and §23 are exactly the failure modes of a regex-over-prose checker |
| 3 | **Commit hygiene** | `.githooks/commit-msg`, `core.hooksPath` wiring in `.agents/hooks/session-start.sh` | Rewrite any `Co-Authored-By: Claude <model> <email>` trailer to the bare agent name, because an agent can't verify its model. | none (the hook has one noun) | 136 wrong trailers in the source log before it existed |
| 4 | **`ship`, adapted** | `.agents/skills/ship/SKILL.md` (+ `side-flows.md`; `.agents/scripts/ship.py` later) | A bare "push" means: branch, PR, CI green, then one combined ask that covers merging *and* deleting the branch. Never push straight to the protected branch. | `experimental`→`main`; drop the promotion flow and `just` steps; step 0 is the CI's two commands | dated incident (2026-08-21: a bare "push" read as license to push to `main`); 3 issues |
| 5 | **`use-a-worktree`, adapted** | `.agents/skills/use-a-worktree/SKILL.md` | Work that branches or commits gets its own `git worktree`, so concurrent sessions can't change each other's checkout. | drop `just agent worktree`; plain `git worktree add -b` | 2026-08-30: two sessions sharing one checkout swapped branches under each other |
| 6 | **`review`, adapted** | `.agents/skills/review/SKILL.md` | Run the mechanical checks first, then read the diff for the traps a diff can't show, then state the outcome at the rung reached. | the whole "Read for" list is Nix-specific. Replace with factcheck's traps: stdlib-only, 3.11 syntax, REVIEW vs hard findings, a fixture test per new check, a default that encodes one repo's conventions, plugin-API changes that break pinned consumers, the README checks table out of date | issue #223 |
| 7 | **`fact-hygiene`** | `.agents/skills/fact-hygiene/SKILL.md` | Write facts so they can't rot: only state what you watched; a date is when someone last checked; a cross-reference is a live pointer; don't record a count a command answers. | incidents become one-line reasons; "hosts/modules" become "checks/configs" | 2 issues, dated incidents. Category 4 is what factcheck's own `docrefs` BARE COUNT enforces, so the skill and the check already form a coupling |
| 8 | **`new-skill` + dogfood `skill-files`** | `.agents/skills/new-skill/SKILL.md`; factcheck's `skill-files` check | A one-sentence description; triggers in `when_to_use`; full detail in `## Applies to`; no injection syntax. A check enforces the mechanical half. | drop the `bash-guards` paragraph until a guard exists; add `.agents/skills` to factcheck's own scopes | the source's `skill-files` check (now factcheck core) |
| 9 | **`boyscouting`, `git-archaeology`** | `.agents/skills/{boyscouting,git-archaeology}/SKILL.md` | Fix small things only in files the diff already touches, in the same commit. Search history across renames with the pickaxe and a glob pathspec. | the rename examples | git-archaeology: a dated miss (2026-09-15) |
| 10 | **`propose-issue` + `investigate-bug`, adapted** | both SKILL.md files; `flake/scripts/threads.sh` | Check whether a bug is already tracked before investigating it. Propose an issue with real content, filed only in this repo. | `just threads` becomes `gh issue list --search` plus a grep of README and tests | 2026-08-24: hours spent re-deriving a bug that was already written up (§39, #72) |
| 11 | **Docs-sync, as one AGENTS.md line** | `wiki-sync` skill (its rule, not its procedure) | A change that makes the README stale fixes it in the same change. | no wiki: one line, no skill | the source's most-cited rule |
| 12 | **PR template, adapted** | `.github/PULL_REQUEST_TEMPLATE.md` | What changed / Why / Verified (beyond CI) / Deliberately left alone, plus a model-agnostic agent disclosure. | the `just` comment | none beyond use |

## Port, adapted (small, take or leave)

- **`session-start.sh`, minus the `just` and hostname parts.** It puts
  branch, worktree, dirty count and `core.hooksPath` into context before
  the first tool call, and wires `.githooks`. Only worth it once row 3
  exists.
- **A pre-push hook running CI's two commands.** CI is currently the only
  gate, and both commands are stdlib-only and fast. Port the hook alone,
  without the source's offline-degrade machinery, which is there for Nix
  and has nothing to degrade from here.

## Feature (better as factcheck checks than as tooling)

These source scripts already do factcheck's job: comparing what docs say
against the repo. They belong in its registry, not in an agent toolbox.

| source | becomes | note |
|---|---|---|
| `.agents/scripts/move_refs.py` (+ test) | a fixer: `factcheck fix-refs` after `git mv` | stdlib, 2 noun lines, tested; the `links` check's natural partner |
| `wiki/meta/scripts/wiki_stale_refs.py` | a `paths` check: backticked repo paths that no longer exist | generalizes `docrefs`' moved-dirs table; REVIEW severity |
| `.agents/scripts/doc_drift.py` + `docscope.py` | a `drift` report: docs ranked by commits under the paths they cite since their last-modified date | REVIEW-only by nature; where `docs-audit-all` starts |
| `wiki/meta/scripts/check_restatement.py` | a `restatement` REVIEW check: 8-gram overlap between instruction files, skills and docs | enforces "one pointer per fact" |
| `examples/nixos-plugins/lessons_index.py` (in factcheck) | core `lessons` check, configured by `[lessons]` | only its default paths name the source; the map half stays in the consumer, as the README says |
| README's checks table | a `generated` region rendered from the registry | factcheck's own `generated` check would then keep its README honest |

## Later (general, but factcheck lacks what it acts on)

| candidate | trigger to revisit |
|---|---|
| Destructive-git guard: `git-guard-pretooluse.sh` + `guard_check.py` + its test + `guards-without-hooks` + settings wiring | Strong evidence (an uncommitted-edit loss, #182), but 673 lines of bash. Better spun out once from launchpad as a shared hook than copied into each repo. Revisit when that exists, or at the first lost edit here |
| Lessons-learned log (§-numbered index plus articles, Home/Enforced fields) and the lesson-reminder hook with its topic map | The first mistake an agent repeats in factcheck. Seed it from the README's "Design notes worth keeping", which already read as lessons |
| `agent-scripts` + `recurring.py` transcript miner | Enough session history in factcheck to mine. Also needs a command runner (`just` or `make`) |
| `explain-tricky-code` | When the slug and fence internals need a newcomer pass |
| `boyscouting-all`, `trim-docs` | When the docs outgrow the README |
| `secrets-guard-*` hooks | When a credential first enters this repo's CI or config |

## Skip

- **Nix and host specific:** `new-flake-module`, `new-host-config`,
  `new-package`, `package-platform-support`, `home-manager-dotfiles`,
  `impermanence-initrd`, `new-homelab-service`, `new-tailscale-service`,
  `low-side-secrets`, `secrets-hygiene`, `triage-flagged-secrets`,
  `maintenance-schedule`, `cod-completions`, `keybinding-cheatsheet`,
  `comment-wrap`, `trim-history`, `extract-nix-tooling*`. Their rules
  files and the `nix-untracked`, `just`, `impermanence-edit`,
  `edit-check` and ZCode-canary hooks go too.
- **Wiki apparatus:** two-audience sibling pages, `-history.md`
  companions, `00-INDEX` routing, `new-wiki-page`, `wiki-history-sweep`,
  `wiki-fact-check`, `docs-audit-all`, `book-fact-check`. factcheck has
  no wiki, and its config turns off the matching checks for itself.
  `docs-audit-all`'s method returns as the `drift` feature above.
- **`extract-agent-tooling(-all)`:** superseded by this skill. The
  follow-up belongs in nixos-configs, which could point those two skills
  here.

## Found along the way

- factcheck `README.md`'s Provenance section still says the example
  plugins move into the consumer "at flip time". nixos-configs has
  flipped (its `tools/docchecks/` and `factcheck.toml` `[plugins]`), so
  the sentence and `examples/nixos-plugins/` are stale. That's a factcheck
  issue to propose, not something to fix in this port.
- The `skill-files` defaults (`needs-tags = ["bash-guards"]` and its cue)
  encode the source's guard vocabulary. Row 8 is the first time a second
  repo hits them; expect to make them config-only.

## Suggested order

Rows 1–3 in one PR: layout, the done-rules, the trailer hook. Then 4–6
(git flow and review), then 7–12. Features go one PR per check, each with
its fixture test. The one question to settle first: should `main` stay
directly pushable, or get the PR-plus-CI ruleset that `ship` assumes?
