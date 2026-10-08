---
name: odoo-harden
description: Harden the whole Odoo project before go-live - full automated audit and remediation of all modules
license: MIT
metadata:
  author: opencode
  version: "1.0"
---

# Odoo Harden

Run a zero-tolerance hardening pass on the **entire project** before go-live.

This skill:
1. Detects project context (version, edition, all modules in `addons/`)
2. Creates a `project-hardening` change using the `harden-driven` openspec schema
3. Generates `audit.md` — full automated scan of every file in `addons/`
4. Generates `harden-tasks.md` — remediation checklist for every finding
5. Executes all tasks autonomously via `openspec-apply-change`
6. Runs the mandatory infrastructure sequence (rebuild, tests, translations, user setup, smoke)
7. Reports completion to the user

**Scope:** The entire `addons/` directory — not any specific change.
**Zero tolerance:** Nothing is pre-existing. Every finding gets fixed.
**No pauses:** Run to completion, then list any unresolvable issues at the end.

---

## Before You Begin

Read the full hardening reference:

```
~/.config/opencode/odoo/reference-phase2.md
```

This contains all 10 audit categories, workflows, and the completion report template.

---

## Workflow

### Step 1: Detect Project Context

```bash
# Odoo version
grep "image: odoo" docker-compose.yml | grep -oE '[0-9]+\.[0-9]+'

# Edition (CE or EE)
grep -q "enterprise" docker-compose.yml && echo "EE" || echo "CE"

# Container name
grep "container_name:" docker-compose.override.yml 2>/dev/null | awk '{print $2}' || \
grep "container_name:" docker-compose.yml | awk '{print $2}'

# Database name (always read from odoo.conf)
grep "^db_name" odoo.conf | awk -F' = ' '{print $2}'

# All modules to harden
ls addons/

# Shared source path
ls ~/shared/odoo-src/<version>/
```

Announce detected context before proceeding.

### Step 2: Create the Hardening Change

```bash
openspec new change "project-hardening" --schema harden-driven
```

If a `project-hardening` change already exists (interrupted previous run), ask the
user whether to resume it or start fresh.

### Step 3: Generate Artifacts (Propose Phase)

Load and execute the propose skill:

```
skill({ name: "openspec-propose" })
```

This will:
- Generate `audit.md`: the agent reads every file in `addons/` and records
  all findings across the 10 categories from `reference-phase2.md`
- Generate `harden-tasks.md`: one task per finding plus the mandatory
  infrastructure section

**Audit stance:** Read EVERY file. No shortcuts. No assumptions.
The shared Odoo source at `~/shared/odoo-src/<version>/` must be consulted
for any Category 10 (Standard Pattern Compliance) findings before flagging them.

Reuse the house-rule and security skills instead of re-deriving rules per finding:

```
skill({ name: "odoo-review" })     # guidelines + security pass over the changed files
skill({ name: "odoo-security" })   # focused audit: access, sudo, SQL, RPC, XSS
skill({ name: "odoo-guidelines" }) # addon house rules behind the audit categories
```

### Step 4: Execute All Tasks (Apply Phase)

Load and execute the apply skill:

```
skill({ name: "openspec-apply-change" })
```

Work through every task in `harden-tasks.md`:

- Fix everything autonomously
- Do not pause to ask the user about any finding
- For `cr.commit()` findings: read context and comments carefully;
  never blindly remove; add a comment if justified but undocumented
- For standard pattern replacements: read the actual source in
  `~/shared/odoo-src/<version>/` before refactoring; only replace if the
  standard API genuinely covers the use case
- For OCA dep additions: verify the module exists in `~/shared/odoo-src/<version>/oca/`
  before adding it to `depends`
- For method length violations: extract to private methods, preserve all behavior

**After all non-infrastructure tasks are complete**, execute the mandatory
infrastructure sequence in this order:

#### 5a. Version Bump
Increment patch version in every modified `__manifest__.py`.
Use minor bump if new fields or models were added during hardening.

#### 5b. Pre-commit (if .pre-commit-config.yaml exists)
```bash
pre-commit run --all-files
```
Fix every failure.

#### 5c. Fresh Instance Rebuild
```bash
make rebuild-demo
# or manual docker run if no Makefile — see reference-phase2.md
```

#### 5d. Verify Module Installation
```bash
docker compose logs --tail 100
# Check for startup errors
```

#### 5e. Run Tests
```bash
make test
# All tests must be green
```

#### 5f. Run Coverage
```bash
make test-coverage
# Must be ≥ 80% across all modules
# Write additional tests if below threshold
```

#### 5g. Install Languages
```bash
# Install French
docker exec <CONTAINER> odoo -d <DB> -l fr_FR --i18n-overwrite --stop-after-init -c /etc/odoo/odoo.conf

# Install German
docker exec <CONTAINER> odoo -d <DB> -l de_DE --i18n-overwrite --stop-after-init -c /etc/odoo/odoo.conf

# Install module translations
docker exec <CONTAINER> odoo -d <DB> -u <modules> -l de_DE,fr_FR --i18n-overwrite --stop-after-init -c /etc/odoo/odoo.conf
```

#### 5h. Switch Users to German
```bash
docker compose exec -T odoo odoo shell -d <DB> -c /etc/odoo/odoo.conf --http-port=18069 <<'EOF'
env['res.users'].search([('login', 'in', ['admin', 'demo'])]).write({'lang': 'de_DE'})
env.cr.commit()
EOF
```
Note: `cr.commit()` is valid here — the Odoo shell runs outside the normal
request/transaction lifecycle and will not auto-commit.

#### 5i. Smoke Test
```bash
make smoke
# or two-curl check — see reference-phase2.md
```

#### 5j. Visual Verification (Playwright)
After the rebuild, perform a visual smoke test using Playwright to verify the UI renders correctly:
1. Log in with admin credentials via Playwright
2. Navigate to a member detail form view
3. Verify that `image_1920` renders as an actual image (not just file size text)
4. Check for console warnings — especially `Missing widget: * for field of type *`
5. Verify the kanban view shows member avatars
6. Check that CSS assets load correctly (HTTP 200)

```python
# Example: verify image rendering in form view
await page.goto("https://<project>.opencode.socialcloud.ch/odoo/action-XXX/YYY")
img_field = await page.evaluate("""() => {
    const f = document.querySelector('[name="image_1920"]');
    return f ? {imgCount: f.querySelectorAll('img').length} : {error: 'NOT FOUND'};
}""")
# Must have at least 1 img child (the preview)
```

**Common post-harden visual issues caught by this:**
- `widget="contact_image"` on `image_1920` → renders as file input, not image preview. Fix: use `widget="image" class="oe_avatar" options='{"preview_image": "avatar_128"}'` (standard Odoo 18 pattern from `base/views/res_partner_views.xml`)
- Non-existent widgets silently fall back to file input rendering with no error (only a console warning)
- Custom standalone form views that don't inherit `base.view_partner_form` need explicit `image_1920` field configuration

### Step 5: Report to User

Use the completion report template from `reference-phase2.md`.

Always include:
- Login URL: `https://<project>.opencode.socialcloud.ch/web/login`
- Credentials: admin / admin
- UI language: German (de_DE), French also installed

If any issues could not be resolved, list them with concrete proposed fixes.

End with:
> "Run `/odoo-finalize` to archive the hardening change and push to git."

---

## Project Detection

### Odoo Executable
```bash
docker exec <CONTAINER> odoo -d <DB> ...     # correct
docker exec <CONTAINER> odoo-bin -d <DB> ... # wrong — not in official image
```

### Worktree vs Main Project

`.git` is a FILE in worktrees, a DIRECTORY in the main repo.
In worktrees, read container and DB from `docker-compose.override.yml` and `odoo.conf`.

### Shared Source Path

```
~/shared/odoo-src/
├── <version>/
│   ├── community/   # Always check here first for standard patterns
│   ├── enterprise/  # Check here for EE-only patterns
│   └── oca/         # Check here for OCA module availability
```

---

## Error Handling

### If a task cannot be completed
Continue to the next task. At the very end, list all unresolvable issues
with concrete proposed next steps. Never skip silently.

### If tests fail after rebuild
Read test output, fix the failing code or test, re-run tests.
All tests must be green before proceeding to smoke test.

### If coverage is below 80%
Write additional tests focused on:
- Business logic paths
- Error paths (invalid input, API failures)
- Security boundaries (AccessError assertions)
Re-run coverage until ≥ 80%.

### If smoke fails
Read container logs (`docker compose logs --tail 100`), fix the issue, restart,
re-smoke. Do not report completion until smoke passes.
