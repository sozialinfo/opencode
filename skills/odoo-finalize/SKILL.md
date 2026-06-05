---
name: odoo-finalize
description: Finalize Odoo change - archive with spec sync, create git commit, and push to remote
license: MIT
metadata:
  author: opencode
  version: "1.0"
---

# Odoo Finalize

Finalize an Odoo change by archiving it and syncing to git.

This skill:
1. Archives the change (via `openspec-archive-change`) with specs synced
2. Creates a git commit with conventional commit message
3. Pushes to the remote repository

---

## Workflow

### Step 1: Archive the Change

Load and execute the archive skill:

```
skill({ name: "openspec-archive-change" })
```

**Important configurations:**
- Always sync delta specs to main specs (don't skip)
- Proceed even if prompted — this workflow assumes DoD was satisfied

### Step 2: Stage All Changes

**In a worktree**, never commit worktree-specific configuration files. Check `git status` first and exclude:
- `docker-compose.override.yml` — worktree-only container config
- `odoo.conf` changes to `db_name`/`db_filter` — worktree-only db routing
- `.env` — secrets, never committed

Stage selectively:

```bash
# Restore worktree-only config changes before staging
git checkout -- odoo.conf 2>/dev/null || true

# Stage everything else
git add -A
git reset -- docker-compose.override.yml 2>/dev/null || true
git reset -- .env 2>/dev/null || true
```

Then verify with `git diff --cached --name-only` that only feature-related files are staged.

This includes:
- Code changes from implementation
- Archived change directory (`openspec/changes/archive/`)
- Updated specs (if synced)
- Translation files

### Step 3: Create Commit

Use conventional commit format:

```bash
git commit -m "feat(<module>): <change title>

<Brief description of what was implemented>

Change: <change-name>
DoD: All items passed"
```

**Commit message patterns:**
- `feat(<module>):` — New feature
- `fix(<module>):` — Bug fix
- `refactor(<module>):` — Code refactoring
- `docs(<module>):` — Documentation only
- `test(<module>):` — Test additions/fixes

### Step 4: Push to Remote

```bash
git push origin <current-branch>
```

If the branch doesn't have an upstream:

```bash
git push -u origin <current-branch>
```

---

## Pre-Flight Checks

Before finalizing, verify:

### 1. DoD Was Satisfied
The user should have run `/odoo-implement` and confirmed testing. If unsure, ask:

> "Has the implementation been tested and approved? `/odoo-finalize` will commit and push all changes."

### 2. Clean Working State
Check for unexpected changes:

```bash
git status
```

All changes should be related to the implementation. Flag any unexpected files.

### 3. Correct Branch
Verify we're on the feature branch, not main:

```bash
git branch --show-current
```

**Never push directly to main/master.** If on main, abort and ask user to create a feature branch.

---

## Handling Edge Cases

### No Changes to Commit
If `git status` shows nothing to commit:
- The change may have already been committed
- Or implementation made no code changes

Ask the user how to proceed.

### Merge Conflicts
If push fails due to conflicts:
1. Report the conflict to user
2. Do NOT attempt to resolve automatically
3. Suggest: `git pull --rebase origin <branch>` then retry

### Archive Already Exists
If the archive target already exists:
- This usually means the change was partially archived before
- Report to user and ask how to proceed

---

## Output

### On Success

```markdown
## Change Finalized

**Change:** <change-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<change-name>/
**Specs:** Synced to main specs

### Git
- **Commit:** <commit-hash>
- **Branch:** <branch-name>
- **Pushed:** ✓

The change is now complete and pushed to remote.
```

### On Failure

```markdown
## Finalization Failed

**Change:** <change-name>
**Step:** <which step failed>

### Error
<error message>

### Resolution
<suggested fix>
```

---

## Complete Example

```bash
# 1. Archive (via skill)
# skill({ name: "openspec-archive-change" })
# → Archived to openspec/changes/archive/2026-04-14-add-feature/
# → Specs synced

# 2. Stage
git add -A

# 3. Commit
git commit -m "feat(newsassistant): Add article filtering by date range

Implements date-based filtering for the news article kanban view.
Users can now filter articles by publication date.

Change: add-date-filter
DoD: All items passed"

# 4. Push
git push origin feature/add-date-filter
```

---

## Safety Guardrails

- **Never force push** unless explicitly requested
- **Never push to main/master** directly
- **Never commit** `.env`, credentials, or secrets
- **Always verify** branch before pushing
- **Always include** change reference in commit message
