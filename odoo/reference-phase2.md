# Odoo Phase 2 Reference — Hardening

This is the hardening reference for Phase 2 (`/odoo-harden`). It contains the full
Definition of Done, audit specifications, and all quality enforcement workflows.

Phase 1 (`/odoo-implement`) uses `reference-phase1.md`. This file is only needed
during the hardening pass.

---

## Hardening Principles

- **Zero tolerance**: Nothing is pre-existing. If it is in `addons/`, it is in scope.
- **Autonomous**: Fix everything without pausing to ask the user.
- **Complete**: Run to the very end. Only at the final step list anything that could
  not be resolved, with concrete proposed fixes.
- **Source-grounded**: Read actual source from `~/shared/odoo-src/<version>/` before
  recommending or applying any standard pattern replacement.

---

## The 10 Audit Categories

### Category 1 — Manifest Integrity

Every `__manifest__.py` must have:

| Key | Requirement |
|---|---|
| `name` | Human-readable display name |
| `version` | `<odoo>.<major>.<minor>.<patch>` e.g. `20.0.1.0.0` (prefix matches the project's Odoo series) |
| `category` | Valid Odoo category string |
| `summary` | Short one-line description |
| `author` | Organization name |
| `website` | Valid URI |
| `license` | `LGPL-3` or `AGPL-3` |
| `depends` | Direct deps only, no transitive extras |
| `data` | Security first, then data, then views, menus last |
| `installable` | `True` |

Data load order (critical):
```python
"data": [
    "security/module_security.xml",   # groups + record rules
    "security/ir.model.access.csv",   # CRUD permissions
    "data/seed_data.xml",             # reference data (noupdate="1")
    "data/ir_cron_data.xml",          # scheduled actions
    "views/model_views.xml",          # views
    "views/menu.xml",                 # menus LAST
],
```

`noupdate="1"` required on all:
- Security groups and record rules
- Seed stages / phases
- Cron jobs
- Queue job channels and functions
- System parameters

**Version bump** (always the last code change before infrastructure):
- Patch: bug fixes, code quality improvements, hardening-only changes
- Minor: new fields, new models, new features introduced during hardening
- Major: breaking changes, data model changes requiring migration

---

### Category 2 — Python Code Correctness

Checks (all required, zero exceptions):

- Import order: stdlib → third-party → odoo → odoo.addons → local relative
- No imports inside method bodies — move to module top-level
- `_logger = logging.getLogger(__name__)` in every file that logs
- No `print()` statements — use `_logger`
- `_description` set on every model class
- `_order` set explicitly on every model class
- `ensure_one()` at start of every `action_*` method
- `@api.model_create_multi` on every `create()` override (Odoo 17+ hard requirement)
- Computed fields: all fields assigned in every branch; always iterate `for record in self:`
- `_sql_constraints` used for uniqueness where possible (not only Python validators)
- Module-level constants for magic values (timeouts, limits, tag sets)
- `timeout=` on every HTTP request (`requests.get`, `requests.post`, `Session.get`, etc.)
- No `eval()` usage

**Method refactoring — indentation verification:**
After any refactoring that moves, renames, or modifies method signatures,
verify the method is still correctly indented inside its class:

```bash
# Check that methods aren't accidentally de-indented to module level
python3 -c "
with open('models/<file>.py') as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if l.startswith('def ') and l.lstrip().startswith('def '):
        print(f'WARNING line {i+1}: method at column 0 — not in class?')
"
```

Run the module's tests immediately after the refactoring — a de-indented
method renders silently as a module-level function with no runtime error
until the method is actually called on an instance.

**`cr.commit()` rule (contextual — never blindly remove):**
- Read the surrounding code AND comments before taking any action
- If usage is justified (long-running batch, shell script, post-migration) and
  documented with a comment → leave it alone
- If usage is justified but undocumented → add an explanatory comment
- Only remove if genuinely wrong (inside normal ORM request lifecycle with no justification)
- Valid exceptions: Odoo shell scripts, Makefile post-setup targets, long-running
  cron jobs where partial progress must be preserved

---

### Category 3 — Security

- Every model has at least one row in `ir.model.access.csv` — no accidental public models
- Security groups use `implied_ids` for role hierarchy (Manager implies User)
- Record rules exist for row-level isolation on user-owned data
- `noupdate="1"` on all `ir.rule` and `res.groups` records
- Admin/manager groups have default users added in security XML
- Sensitive buttons/fields use `groups=` attribute in XML
- All `fields.Html` have explicit `sanitize=` declaration
- No hardcoded credentials, API keys, or passwords in Python, XML, or data files
- Dedicated `test_security.py` that tests:
  - Group hierarchy (Manager implies User)
  - Per-role CRUD: who can create/read/write/delete each model
  - Record rule enforcement: test `AccessError` for unauthorized operations
  - Configuration model restrictions

---

### Category 4 — XML / View Quality

- `<?xml version="1.0" encoding="utf-8"?>` header on every XML file
- 4-space indentation throughout
- XML ID naming convention:
  - Views: `<model>_view_<type>` (form, list, kanban, search)
  - Actions: `<model>_action`
  - Menus: `<model>_menu`
  - Groups: `group_<module>_<role>`
  - Rules: `<model>_rule_<group>`
  - Cron: `ir_cron_<description>`
- No `attrs=` — use `invisible=`, `readonly=`, `required=` directly (Odoo 17+)
- `invisible=` uses domain-style Python expressions
- `role="alert"` on all alert `<div>` banners
- Form views follow canonical structure: `<header>` → `<sheet>` → `<chatter/>`
- **Button placement and view inheritance:** Moving `button_box` from `<sheet>`
  into `<header>` can silently break inherited views that inject buttons via
  `xpath="//div[@name='button_box']"` or `xpath="//header" position="inside"`.
  Before moving button_box, check ALL view extensions across ALL modules that
  inherit from the target form:

  ```bash
  grep -r "inherit_id.*news_source_view_form\|xpath.*button_box\|xpath.*header" addons/
  ```

  If other modules extend the form's header or button_box, leave the
  button_box in `<sheet>` — it works correctly and is the safer default.
- Menu items in separate `menu.xml` file, loaded last in manifest data list

---

### Category 5 — Performance

- `index=True` on all `Many2one` fields used in search domains or `_order`
- `index=True` on `Char`/`Date`/`Datetime` fields used in frequent search filters
- Compute methods batch over `self` with a single SQL query (never per-record SQL in a loop)
- `search_count()` instead of `len(search())` when only count is needed
- Long-running operations (HTTP, AI, file processing, >1s) use `with_delay()` via queue_job
- `store=True` only on computed fields genuinely needed for search/sort
- No N+1 query patterns in `write()` or `create()` overrides

Batch compute pattern:
```python
def _compute_job_count(self):
    counts = {}
    if self.ids:
        self.env.cr.execute(
            "SELECT model_id, COUNT(*) FROM queue_job WHERE model_id IN %s GROUP BY model_id",
            [tuple(self.ids)]
        )
        counts = {row[0]: row[1] for row in self.env.cr.fetchall()}
    for record in self:
        record.job_count = counts.get(record.id, 0)
```

---

### Category 6 — Structural Completeness

- `static/description/icon.png` exists (128×128 or 256×256 PNG)
  - If missing: generate a simple placeholder using the module's initials
- `demo/` directory exists with realistic sample data for every major model
- Migration scripts present if any column was renamed or dropped since last version
  - **Not just the current version** — scan `git log` for field renames
    across the module's entire history. A rename in an older commit that lacks
    a migration script will cause data loss on every upgrade.
  - Check for column renames across git history:
    ```bash
    git log --oneline --all -- <module>/models/ | head -20
    git show <commit> -- <module>/models/ | grep -E '^\+.*fields\.|^\-.*fields\.'
    # Flag any -/+ pairs with different field names on the same model
    ```
  - Scripts must guard: `if not version: return`  (skip on fresh install)
  - Column renames should use guard-checked `ALTER TABLE ... RENAME COLUMN`,
    not drop+create (which silently loses data):
    ```python
    def migrate(cr, version):
        cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '<table>' AND column_name = '<old>'
                    AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = '<table>' AND column_name = '<new>'
                    )
                ) THEN
                    ALTER TABLE <table> RENAME COLUMN <old> TO <new>;
                END IF;
            END
            $$;
        """)
    ```
- `res.config.settings` fields for all user-configurable parameters
  - `config_parameter=` key prefixed with module name to avoid collisions
- Queue job channels and retry patterns defined if module uses `queue_job`:
  ```xml
  <record id="channel_module" model="queue.job.channel">
      <field name="name">module</field>
      <field name="parent_id" ref="queue_job.channel_root"/>
  </record>
  ```

---

### Category 7 — Maintainability

- Docstrings on all business methods:
  - Simple: one-line description
  - Complex: multi-line with Args / Returns / Raises
- Context keys used to suppress side effects in tests
  (e.g. `skip_<action>=True` pattern in `create()`)
- Correct exception types:
  - `UserError` — user-facing errors with actionable messages
  - `ValidationError` — constraint violations
  - `RetryableJobError` — transient external failures in queue jobs
- `mail.thread` inherited on models with important state changes
- `tracking=True` on status/state fields for automatic chatter tracking
- No dead code (commented-out blocks, unused imports, unused methods)
- **Methods over 100 lines must be refactored**: extract logical sub-steps into
  well-named private methods. Preserve all behavior exactly.

---

### Category 8 — Documentation

Every module's `README.md` must contain these sections:
1. Module title (H1) + one-paragraph description
2. **Features** — bullet list of capabilities
3. **Models** — one subsection per model with field table (name, type, description)
4. **Security** — groups table + record rules description
5. **Configuration** — post-install setup steps
6. **Dependencies** — module depends list
7. **License**

All public model methods must have docstrings.

---

### Category 9 — Tooling Compliance

- No `*.pot` files committed
- No `en.po` files (English is the source language, not a translation target)
- No `# -*- coding: utf-8 -*-` encoding pragmas
- No `.rej` files (copier conflict artifacts)

**PO file cross-contamination check:**
When a module is split or extracted from another, its `i18n/*.po` files may be
verbatim copies of the parent module's. Validate:

```bash
# Check if po file header matches the directory name
head -4 addons/<module>/i18n/de.po | grep -q "modules:.*<module>" || echo "WRONG MODULE"

# Count msgids from other modules (not the current one)
TOTAL=$(grep -c '^msgid ' addons/<module>/i18n/de.po)
FROM_OTHER=$(grep -c "module: <other_module>" addons/<module>/i18n/de.po || true)
if [ "$FROM_OTHER" -gt 0 ] && [ "$FROM_OTHER" -gt $((TOTAL/2)) ]; then
    echo "PO file is mostly from a different module — regenerate with proper POT"
fi
```

For newly extracted submodules, always export a fresh POT and rewrite the
PO files from scratch. Never copy another module's PO file verbatim.

If `.pre-commit-config.yaml` exists in the project:
```bash
pre-commit run --all-files
```
Fix every failure before proceeding.

---

### Category 10 — Standard Pattern Compliance

**Always read the actual source before recommending a replacement.**

```bash
# Read standard mixin source before any replacement:
cat ~/shared/odoo-src/<version>/community/addons/mail/models/mail_thread.py
cat ~/shared/odoo-src/<version>/community/addons/base/models/image_mixin.py
# etc.
```

Check for custom reimplementations of:

| Standard | Custom anti-pattern to look for |
|---|---|
| `mail.thread` | Custom message/chatter tables, custom follower systems |
| `mail.activity.mixin` | Custom task/reminder/todo models |
| `mail.alias.mixin.optional` | Custom email routing tables |
| `image.mixin` | Raw `Binary` image fields without resize variants |
| `ir.sequence` | Custom counter fields, custom reference number generators |
| `sequence.mixin` | Custom sequence prefix/year/number parsing |
| `portal.mixin` | Custom `access_token` fields or portal URL generation |
| `utm.mixin` | Custom campaign/source/medium tracking fields |
| `analytic.mixin` | Custom analytic account distribution |
| `resource.mixin` | Custom work schedule / calendar logic |
| `mail.thread.phone` | Custom phone validation or blacklist |
| `mail.thread.blacklist` | Custom email blacklist/bounce handling |
| `mail.tracking.duration.mixin` | Custom stage time tracking |
| `rating.mixin` | Custom satisfaction rating systems |
| `website.published.mixin` | Custom website published/draft toggle |
| `website.seo.metadata` | Custom SEO meta fields |
| `odoo.tools.date_utils` | Custom date arithmetic functions |
| `odoo.tools.float_utils` | Custom float equality/comparison helpers |
| `odoo.tools.mail.html_sanitize` | Custom HTML sanitization |
| OCA `queue_job` | Custom background job queues |
| OCA `auditlog` | Custom audit trail / change log tables |
| OCA `base_user_role` | Custom user role assignment systems |
| OCA `base_multi_image` | Custom multi-image handling |

**Custom JS widgets**: flag any widget defined in `static/src/` that reimplements
functionality already available as a standard `widget=` attribute. Replace with the
standard widget. See `reference-phase1.md` for the widget quick-reference.

**OCA deps**: if an OCA module in `~/shared/odoo-src/<version>/oca/` solves a
custom pattern, add it to `depends` in `__manifest__.py` and refactor. Do not
recommend a dep that is not available in the shared source.

**Code deduplication via mixins — AbstractModel caveat:**
When extracting duplicated logic (e.g., `_call_ai`) into an AbstractModel
mixin, only add it to `_inherit` on models that define `_name` (not
`_inherit = "some.model"`). A model that `_inherit = "news.article"` cannot
also inherit an AbstractModel via list syntax — this fails during
`_auto_init` with ``"The _name attribute X is not valid"``. Instead, use
**delegation**: add a thin wrapper method that calls the mixin's logic
via `self.env["abstract.model.name"].method()`:

```python
# In the concrete model extension (e.g., news.article):
def _call_ai(self, system_prompt, user_content, temperature=0.1):
    return self.env["strategy.strategy"]._call_ai(
        system_prompt, user_content, temperature=temperature
    )
```

Only use `_inherit = [..., "abstract.mixin"]` on models that define
`_name` (i.e., it becomes their primary model class).

---

## Iterative Testing Gate

**Do not batch all changes and test at the end.** After fixing all findings
in a single module, run its tests before moving to the next module:

```bash
# Stop the running container (tests need exclusive DB access)
docker compose stop

# Run tests for the module just hardened
docker run --rm --network opencode \
    -v $(pwd):/mnt/extra-addons \
    -v $(pwd)/odoo.conf:/etc/odoo/odoo.conf:ro \
    -v .../oca/...:/mnt/oca/...:ro \
    --env-file .env \
    odoo:<version> odoo --test-tags <module> --stop-after-init \
    -d <DB> -c /etc/odoo/odoo.conf --http-port=18069
```

If tests fail, fix the issue in that module before continuing. The most
common failures after hardening are:
- **View rendering errors**: forms with moved elements causing xpath breaks
  (verify with `docker compose up -d` and visual check after view changes)
- **Import errors**: removed `__pycache__` exposing stale test imports
- **ACL failures**: tightened permissions causing `AccessError` in tests
- **Method delegation failures**: mocks targeting old module paths no longer
  matching after refactoring

Never proceed to the next module with failing tests from the current one.

---

## Coverage Measurement

```bash
# Using Makefile (preferred):
make test-coverage

# Manual (docker run for isolation):
docker run --rm --network opencode \
    -v $(pwd)/addons:/mnt/extra-addons \
    -v $(pwd)/odoo.conf:/etc/odoo/odoo.conf:ro \
    -w /tmp \
    odoo:<version> bash -c "\
        pip install --quiet --break-system-packages coverage && \
        ~/.local/bin/coverage run \
            --source=/mnt/extra-addons/<module> \
            -m odoo \
            -d test_$(date +%s) \
            -i <module> \
            --test-enable \
            --test-tags=/<module> \
            --stop-after-init \
            --http-port=18069 \
            -c /etc/odoo/odoo.conf && \
        ~/.local/bin/coverage report --show-missing && \
        ~/.local/bin/coverage report --fail-under=80"
```

**Threshold: ≥ 80%**. Write additional tests if below. Focus on:
- Business logic paths
- Error paths (invalid input, API failures)
- Security boundaries (`AccessError` assertions)

---

## Translation Workflow

### Extract POT (temporary — never commit)

```bash
docker exec <CONTAINER> odoo -d <DB> \
    --modules=<module> \
    --i18n-export=/tmp/<module>.pot \
    --stop-after-init \
    -c /etc/odoo/odoo.conf

# Copy to local filesystem
docker cp <CONTAINER>:/tmp/<module>.pot ./addons/<module>/i18n/<module>.pot
```

### Write PO Files

Read the POT. Create or update `i18n/de.po` and `i18n/fr.po`:
- Translate ALL msgid entries — no fuzzy, no untranslated
- Use formal language: **Sie** (German) / **vous** (French)
- Preserve HTML tags and placeholders (`%s`, `%(name)s`)
- Translate selection field values, error messages, button strings, cron names
- `translate=True` on `fields.Char`/`fields.Text` for config labels (e.g., stage names)

### PO File Header

```po
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server 18.0\n"
"Language-Team: German\n"
"Language: de\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"
```

### Install Translations

```bash
docker exec <CONTAINER> odoo -d <DB> \
    -l fr_FR \
    --i18n-overwrite \
    --stop-after-init \
    -c /etc/odoo/odoo.conf

docker exec <CONTAINER> odoo -d <DB> \
    -l de_DE \
    --i18n-overwrite \
    --stop-after-init \
    -c /etc/odoo/odoo.conf

# For module-specific translation update:
docker exec <CONTAINER> odoo -d <DB> \
    -u <modules> \
    -l de_DE,fr_FR \
    --i18n-overwrite \
    --stop-after-init \
    -c /etc/odoo/odoo.conf
```

**Delete the POT file after use.** Never commit `*.pot`.

---

## Fresh Instance Rebuild

```bash
# With Makefile:
make rebuild-demo

# Manual (if no Makefile):
docker compose down
docker exec postgres psql -U opencode -d postgres -c "DROP DATABASE IF EXISTS \"<DB>\";"
sudo rm -rf filestore/*

docker run --rm --network opencode \
    -v $(pwd)/addons:/mnt/extra-addons \
    -v $(pwd)/odoo.conf:/etc/odoo/odoo.conf:ro \
    -v $(pwd)/filestore:/var/lib/odoo/filestore \
    odoo:<version> odoo \
    -d <DB> \
    -i base,<modules> \
    --stop-after-init \
    -c /etc/odoo/odoo.conf

docker compose up -d
sleep 8
```

---

## User Language Setup (Phase 2)

After rebuild, switch admin and demo users to German:

```bash
docker compose exec -T odoo odoo shell -d <DB> -c /etc/odoo/odoo.conf --http-port=18069 <<'EOF'
env['res.users'].search([('login', 'in', ['admin', 'demo'])]).write({'lang': 'de_DE'})
env.cr.commit()
EOF
```

Note: `cr.commit()` is valid here — the Odoo shell runs outside the normal
request/transaction lifecycle and will not auto-commit.

Result:
- `admin` user → German (de_DE)
- `demo` user → German (de_DE)
- French (fr_FR) installed and available
- English remains as source language

---

## Smoke Test

```bash
# With Makefile:
make smoke

# Manual:
# 1. Login page returns 200
curl -s -o /dev/null -w "%{http_code}" https://<project>.opencode.socialcloud.ch/web/login

# 2. CSS assets return 200 (no broken filestore)
ASSET_URL=$(curl -s https://<project>.opencode.socialcloud.ch/web/login | grep -oE '/web/assets/[^"]+\.css' | head -1)
curl -s -o /dev/null -w "%{http_code}" "https://<project>.opencode.socialcloud.ch${ASSET_URL}"

# 3. Module installed
docker compose exec -T odoo odoo shell -d <DB> --http-port=18069 -c /etc/odoo/odoo.conf <<'EOF'
module = env['ir.module.module'].search([('name', '=', '<module>')])
print(f"State: {module.state if module else 'NOT FOUND'}")
EOF
```

---

## Hardening Completion Report

After all tasks and infrastructure steps complete, report to the user:

```
## Hardening Complete

**Project:** <project>
**Modules hardened:** <list>

**Environment:**
- URL: https://<project>.opencode.socialcloud.ch/web/login
- Credentials: admin / admin
- UI language: German (de_DE)
- French (fr_FR) also installed

**DoD Status:**
- [x] All hardening tasks complete
- [x] Coverage ≥ 80% across all modules
- [x] DE + FR translations complete and installed
- [x] OCA standards enforced
- [x] Security hardened
- [x] Documentation complete
- [x] Fresh instance rebuilt with demo data
- [x] All tests green
- [x] Smoke test passed

Run `/odoo-finalize` to archive the hardening change and push to git.
```

If any issues could not be resolved:
```
## Issues Requiring Manual Attention

1. <issue description>
   Proposed fix: <concrete steps>

2. <issue description>
   Proposed fix: <concrete steps>
```
