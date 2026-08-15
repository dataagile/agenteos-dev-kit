# Remove

Drafts only. This operation deletes a YAML file from `a raiz deste repo: drafts/`. It never touches `published/`.

## Published specs — verbatim refusal

If the target is under `published/`, refuse immediately, before any other step:

> A published spec is already seeded into the catalog/DB — deleting the YAML would diverge the file from what's actually running, the same failure mode as trying to hard-delete a hub contract instead of draining it (this codebase's established pattern: removal of a live, seeded thing is a drain/lifecycle transition, never a file delete). Real removal of a published agent is a contract-drain operation through the W1 flow, not a YAML edit. Use `/w1` for that.

Do not proceed further for a published target under any framing — not even "just delete the file, I'll handle the DB separately." That produces exactly the drift the refusal describes.

## Drafts — sequence

### 1. Locate

Search `drafts/<slug>/*.yaml`. If ambiguous (multiple version files under the same slug), ask which version — don't guess, don't default to "latest."

### 2. Git-clean gate (exact plumbing — same as edit.md)

Run `git status --porcelain -- <path>`.

- **Empty output** → clean, proceed.
- **Non-empty, tracked with changes** → block, ask the user to commit first. Never `git stash`.
- **Untracked** (`??`) → this draft was never committed. Deleting it means **no recovery at all** — there is no git history to restore from. Say this explicitly, in plain terms, before asking for confirmation in step 4. Do not treat "untracked" as equivalent to "safe to delete because it was never real."

### 3. Show the spec summary

Reuse the Read (inspect) structured summary format from `read.md` — metadata block, trigger, config_schema, io, node graph — so the user is looking at what they're about to delete, not just a filename.

### 4. Explicit confirmation

Require the user to type the slug back (not just "yes" or "confirm") before deleting. This is deliberately higher-friction than a yes/no for a destructive, and for untracked files, irreversible, operation.

### 5. Disguised-rename tripwire

Before deleting, check whether the Remove target is the **source** of a same-session Clone (this session cloned `<this-slug>` → some new slug, and now the user wants to remove `<this-slug>` — the original, not the clone) — that composition is a slug rename performed as two steps. Apply the same rule as `clone.md` §4. This tripwire is about removing the *source*; removing the *clone* itself (the new slug that was just created) is ordinary draft cleanup — discarding a clone you decided you didn't want is not a rename of anything and needs no special handling here.

- If the spec being removed was itself cloned *from* a published spec under a different slug in this session (i.e. this draft is really standing in for "renamed publish target"), flag it and confirm with the user whether they intend a genuine new/replacement agent (fine) or are trying to rename a published slug through the back door (refuse, point to `/w1`, cite the 007/PR #149 lesson).
- For a same-session drafts-only clone+remove with no published spec involved anywhere in the chain, this is allowed — just say plainly what happened ("this is now a rename of a draft, done as clone + remove") so the user isn't surprised later.

### 6. Delete

1. Delete the YAML file.
2. If its parent directory (`drafts/<slug>/`) is now empty, remove the empty directory too — don't leave a dangling empty slug folder.
3. Confirm what was deleted (path) and remind the user this was a filesystem delete, not a git operation — if the file was tracked and committed, `git log` still has it; if it was untracked, it's gone.

Remove não toca o catálogo — só o draft local; nada a semear.
