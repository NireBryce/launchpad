---
name: land-pr-series
description: Lands a set of related open PRs one after another without force-pushing, resolving the conflicts each merge causes in the next and checking every branch again before it merges.
when_to_use: Asked to ship, merge or land several PRs at once, a stack of PRs, or a batch of feature branches that touch the same files.
---

# Landing a series of PRs

## Applies to

Several open PRs on one repository going in together: a batch of
features, a stack, a fix plus the PRs that need it. Not one PR (the
repo's own landing skill covers that), and not merging without the
user's yes: the series gets one combined ask (order, method, branch
deletion) and then runs. Stop and ask again if the plan changes on the
way (a new PR is needed, a step fails twice).

## Before the first merge

1. **Read the whole set.** For each PR: base branch, head SHA, CI state,
   open review threads, and the files it touches. Two PRs touching one
   file will conflict, whichever merges second.
2. **Pick the order.**
   - **Infrastructure first:** CI, the test runner, the checks script,
     shared config. Later branches then run under it.
   - **Then independent changes**, smallest diff first, so conflicts land
     on the bigger branches, which have more context to resolve them in.
   - **A PR that regenerates or rewrites a shared file goes last,** so it
     regenerates once over everything else: a generated table, a
     lockfile, a formatted tree.
   - **A stacked PR is retargeted** to the trunk before its base merges.
     Its own merge still waits its turn.
3. **Trial-merge them all together** in a throwaway detached worktree:
   merge each head onto the trunk in order, then run the full checks. A
   conflict or failure here is cheaper than one found mid-series.

## For each PR, in order

1. **Bring the trunk in with a merge, not a rebase.** `git merge
   origin/<trunk>` on the PR branch, in its own worktree. Rewriting a
   pushed branch needs a force-push, which permission rules often forbid
   and reviewers' checkouts don't survive.
2. **Resolve conflicts by meaning, not by side:**
   - **A list both sides appended to** (an import list, a registry, a
     changelog): take the union and keep the file's order, alphabetical
     or by key.
   - **A table both sides added rows to:** keep both rows, and check that
     neither side's row already existed in the other. Merging the same
     row twice is the easy mistake.
   - **A generated region:** take either side, then regenerate with the
     repo's tool. It may refuse until a new row is described; that's
     the point of generating it.
   - **Anything else:** read both hunks. When picking either side would
     lose behaviour, stop and ask.
3. **Check after resolving, then read the output.** Run the full checks
   and read every line, not the last: a passing run can still contain
   leftover conflict markers if nothing checks for them. Diff the
   resolved file against the trunk and confirm it differs by exactly what
   the PR adds.
4. **Commit the merge** with a message that names the conflicts and how
   each was resolved, from a quoted heredoc or a file (`-F`), never an
   inline `-m "..."`: backticks in double quotes run as commands.
5. **Push normally, wait for CI on the new head, then merge pinned to it**
   (`expectedHeadSha` / `--match-head-commit`). Use the **full SHA**, from
   `git ls-remote` or `git rev-parse`; a SHA padded out from a short prefix
   is a different commit, and the merge is refused or, worse, merges the
   wrong one.
6. **Merge method:** rebase for one commit, a merge commit for several
   (their messages carry reasoning a squash flattens), unless the repo
   says otherwise.

## After the last merge

- **Run the checks on the trunk itself**, and confirm its CI run on the
  final merge is green.
- **Delete the merged branches**, the ask the user already answered.
  Confirm each is contained first: `git merge-base --is-ancestor`, or
  `git cherry` for a rebase-merged one, where `-` means its patch is in.
  If deletion is refused, say so and list the branches.
- **Remove the worktrees and local branches**, and unsubscribe from the PRs.
- **Report:** the order, each merge commit, every conflict and how it was
  resolved, and anything left (an unpushable fix, a branch the user must
  delete).

## Traps met landing a series

- **A local commit hook that runs the test suite can rewrite the repo.**
  A pre-push hook exports `GIT_DIR`, and tests that shell out to git then
  write into the real repository. See skill `git-hook-safe-tests`; if the
  suite or its hook is new in this series, check `git config --list`,
  `git reflog` and `git status` in every worktree after the first push.
- **`git commit -- <paths>` takes those paths from the working tree.**
  After `git rm --cached <dir>`, committing with that pathspec re-adds
  the directory and commits nothing removed. Commit the index (no
  pathspec), then check with `git ls-files <dir>`.
- **A failed push can leave work done.** A hook that ran (and failed)
  ran everything before it failed. Look at what it touched before
  retrying.
- **The pushed branch is the truth; the local one may not be.** When a
  worktree's history is suspect, rebuild it from `origin/<branch>` in a
  new worktree and push from there, as a fast-forward. Don't repair it in
  place.

## See also

- `prove-tests-bite`: each PR's tests should fail with its change
  reverted; worth running before the series starts.
- `review-prs-in-parallel`: reviewing the set before landing it.
