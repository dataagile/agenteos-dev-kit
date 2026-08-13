# Backup

A dedicated git commit — a snapshot of ONE spec file at this exact moment, restorable later via plain git. Not a parallel `backups/` folder, not a Write-tool copy, not `git stash`.

## What a backup is

- **Scope**: exactly one YAML file (the target spec version, e.g. `drafts/fin-collections/v0.5.yaml` or `published/fin-pagamentos/v1.yaml`).
- **Mechanism**: `git commit`, nothing else. Git history *is* the backup store — there is no second, parallel mechanism to keep in sync.
- **Commit message convention** (always this exact shape): `chore(agent-specs): backup <slug> v<version>` — `<slug>` and `<version>` read from the YAML's own `slug`/`version` fields, not the filename (they can diverge from a stale filename).

## Branch safety (hard rule — never skip this)

**Never create the backup commit on the branch the user currently has checked out**, regardless of what that branch is — `main`, a feature branch, anything. Two reasons, both real in this repo:
1. If the current branch is `main`/`master`, committing directly is an obvious mistake.
2. Even on a feature branch, this repo's working tree is shared across parallel sessions (other Claude Code instances, other tools) that switch branches independently — it happened during F1. A backup commit landing on whatever branch happens to be checked out *right now* can land on the wrong session's branch, polluting someone else's in-progress history.

The safe default that avoids both: **isolate the backup commit in its own throwaway worktree**, on its own dedicated branch, and never touch the user's checked-out branch or index.

**Never use `git stash`** for this or anything else the skill does — per the user's global stash-safety rule, stash is destructive if dropped and this repo's shared working tree means "local changes" are never safely assumed to be disposable.

### Exact sequence

```bash
# 1. Compute names — <UTC-timestamp> as YYYYMMDDTHHMMSSZ, deterministic and sortable.
SLUG="<slug-from-yaml>"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_BRANCH="wip/agentspec-backup-${SLUG}-${TS}"
WORKTREE_DIR="$(mktemp -d)/agentspec-backup-${SLUG}"

# 2. Create the worktree on a brand-new branch, based on the current HEAD
#    (backups branch from wherever the target file currently lives in history —
#    normally the same commit the user is on, but this never depends on what
#    is or isn't staged/dirty in the real working tree).
git worktree add -b "$BACKUP_BRANCH" "$WORKTREE_DIR" HEAD

# 3. Copy the CURRENT on-disk version of the target file into the worktree
#    (this backs up what's on disk right now, including any uncommitted
#    edits the user made — that is the point of an on-demand backup).
cp <repo-root>/<path-to-target-yaml> "$WORKTREE_DIR/<path-to-target-yaml>"

# 4. Commit inside the worktree only.
git -C "$WORKTREE_DIR" add "<path-to-target-yaml>"
git -C "$WORKTREE_DIR" commit -m "chore(agent-specs): backup ${SLUG} v<version>"

# 5. Remove the worktree. The branch survives — worktree removal never
#    deletes the branch or its commits.
git worktree remove "$WORKTREE_DIR"
```

After step 5, report the branch name (`wip/agentspec-backup-<slug>-<timestamp>`) and the commit SHA to the user — that pair is the restore handle. Never delete the branch automatically; it is disposable-but-durable by design (the `wip/` prefix signals that), and only the user decides when it's safe to prune.
If step 4's commit legitimately no-ops (the target file is already byte-identical to HEAD, so there's nothing new to commit), tell the user the current HEAD SHA already covers this content — HEAD is the restore handle, no new commit was needed, and the `wip/` branch may be deleted as redundant.

This sequence never touches:
- The user's checked-out branch (a separate worktree has its own HEAD).
- The user's index/staging area (the worktree has its own).
- Any uncommitted changes elsewhere in the working tree (only the one target file is copied in).

## Restore

Backups are plain commits — restoring is plain git, no skill-specific tooling:

```bash
# Find backup commits for a file (across all branches, including pruned-looking wip/ branches).
git log --all --oneline -- a raiz deste repo: <drafts-or-published>/<slug>/<file>.yaml

# Inspect one backup's content without checking anything out.
git show <sha>:a raiz deste repo: <drafts-or-published>/<slug>/<file>.yaml

# Restore it into the working tree (only after confirming with the user —
# this overwrites the current file).
git show <sha>:a raiz deste repo: <drafts-or-published>/<slug>/<file>.yaml > a raiz deste repo: <drafts-or-published>/<slug>/<file>.yaml
```

Always run the restored content through the validator before telling the user it's safe to use again: `.venv/bin/python .claude/skills/agentos-builder/scripts/validate_spec.py <path>` — a backup from before a schema/tooling change may no longer validate cleanly, and that's information the user needs, not something to paper over.

## When Backup is a prerequisite

Edit and Remove both gate on git cleanliness for the target file per SKILL.md's shared git-clean gate — if the working tree is dirty for that file, they block and ask the user to commit first, rather than silently proceeding. Backup is the tool offered at that point when the user wants a restorable snapshot before a destructive change but isn't ready to commit their in-progress edits normally. See `edit.md` / `remove.md` for exactly when each calls this — this file only documents *how* a backup snapshot itself is taken and restored, not the gating logic that decides *when* one is needed.
