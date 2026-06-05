# Odoo Phase 1 Reference — Vibe Coding

This is the fast-coding reference for Phase 1 (vibe coding). It contains everything
needed to write good Odoo code the first time, minimizing Phase 2 refactoring.

Phase 2 hardening will verify these patterns. Following them now avoids major rework.

---

## Deployment Cycle

After all tasks complete (or after any bug fix), run this cycle:

### Context Detection

```bash
# Detect container name (worktree override takes priority)
grep "container_name:" docker-compose.override.yml 2>/dev/null | awk '{print $2}' || \
grep "container_name:" docker-compose.yml | awk '{print $2}'

# Detect database name (always read from odoo.conf — never assume)
grep "^db_name" odoo.conf | awk -F' = ' '{print $2}'

# Detect Odoo version
grep "image: odoo" docker-compose.yml | grep -oE '[0-9]+\.[0-9]+'

# Detect modules
ls addons/
```

Worktree detection: `.git` is a FILE in worktrees, a DIRECTORY in the main repo.
In worktrees, container and DB names differ from the project name — always read
from the override file and odoo.conf.

### Upgrade + Restart + Smoke

```bash
# 1. Upgrade module(s)
# If Makefile exists:
make upgrade           # upgrades all project modules
make upgrade-one MODULE=<name>  # upgrades single module (if target exists)

# Without Makefile (or to be explicit):
docker exec <CONTAINER> odoo -c /etc/odoo/odoo.conf -d <DB> -u <modules> --stop-after-init

# 2. Restart
make restart           # if Makefile exists
docker restart <CONTAINER>       # raw container
docker compose restart odoo      # compose service

# 3. Smoke test
make smoke             # if Makefile exists

# Manual smoke (if no Makefile):
curl -s -o /dev/null -w "%{http_code}" https://<project>.opencode.socialcloud.ch/web/login
# Must return 200

ASSET_URL=$(curl -s https://<project>.opencode.socialcloud.ch/web/login | grep -oE '/web/assets/[^"]+\.css' | head -1)
curl -s -o /dev/null -w "%{http_code}" "https://<project>.opencode.socialcloud.ch${ASSET_URL}"
# Must return 200
```

### When Smoke Fails

```bash
# 500 on login — read logs to find the Python error:
docker logs <CONTAINER> --tail 50

# 200 login but 500 on assets — stale asset cache:
docker compose exec -T odoo odoo shell -d <DB> --http-port=18069 -c /etc/odoo/odoo.conf <<'EOF'
env['ir.attachment'].search([('url', 'like', '/web/assets/')]).unlink()
env.cr.commit()
EOF
docker compose restart odoo

# Only use full rebuild when:
# - New Many2one field to a model that doesn't exist yet
# - _sql_constraints change conflicts with existing data
# - Required field with no default added to a table with existing rows
make rebuild-demo   # or make rebuild
```

### When to Upgrade vs Full Rebuild

| Situation | Action |
|---|---|
| Code change (Python, XML, CSV) | upgrade + restart |
| New module added to depends | upgrade + restart |
| New column on empty table | upgrade + restart |
| _sql_constraints conflict with existing data | full rebuild |
| Required field without default on populated table | full rebuild |
| User explicitly asks for fresh start | full rebuild |

---

## Phase 1 Definition of Done

After all tasks complete and smoke test passes:

1. All tasks in tasks.md are `[x]`
2. Module installs without errors: `docker exec <CONTAINER> odoo -d <DB> -i <module> --stop-after-init -c /etc/odoo/odoo.conf`
3. Existing tests pass (no new test requirement, no coverage gate)
4. Smoke test passes (login 200, assets 200)

Environment is English-only. No translations installed. admin and demo users
remain in English — this is correct for Phase 1.

Completion message:
> "Phase 1 complete. The module is deployed at https://<project>.opencode.socialcloud.ch/web/login (admin/admin).
> Run `/odoo-explore` to keep iterating, or `/odoo-harden` before going live."

---

## Key Code Correctness Checklist

Follow these now to avoid Phase 2 refactoring:

| Rule | Why |
|---|---|
| `_description` on every model | Required by Odoo, appears in access error messages |
| `_order` on every model | Deterministic ordering — never rely on DB insertion order |
| `ensure_one()` at start of every `action_*` | Prevents silent multi-record bugs |
| `@api.model_create_multi` on every `create()` override | Hard requirement since Odoo 17 |
| `index=True` on Many2one and filter-heavy fields | Prevents slow searches at scale |
| `timeout=` on every HTTP call | Required by pylint-odoo; prevents hanging requests |
| `sanitize=` explicit on every `fields.Html` | Never leave sanitization implicit |
| `noupdate="1"` on seed data | Prevents data reset on module upgrade |
| No `attrs=` in XML | Deprecated since Odoo 17; use `invisible=`, `readonly=`, `required=` |
| `role="alert"` on alert divs | Accessibility requirement |
| `groups=` on sensitive buttons/fields | Security — never expose admin actions to all users |
| `UserError` for user messages | Not `ValidationError` — different UX and semantics |
| `ValidationError` for constraint violations | Not `UserError` |
| `RetryableJobError` for transient failures | Enables automatic job retry |
| No imports inside method bodies | All imports at module top-level |
| No `print()` statements | Use `_logger.info/warning/exception()` |

---

## Standard Mixins — Use These, Don't Reimplement

Before writing any custom implementation, check if a standard mixin covers it.
Read the actual source at `~/shared/odoo-src/<version>/community/` first.

| If you need... | Use | Source path |
|---|---|---|
| Chatter / message posting / tracking | `mail.thread` | `addons/mail/models/mail_thread.py` |
| Activities / reminders | `mail.activity.mixin` | `addons/mail/models/mail_activity_mixin.py` |
| Email aliases | `mail.alias.mixin.optional` | `addons/mail/models/mail_alias_mixin.py` |
| Image fields with resize variants | `image.mixin` | `addons/base/models/image_mixin.py` |
| Avatar with fallback SVG | `avatar.mixin` | `addons/base/models/avatar_mixin.py` |
| Sequence numbers / references | `ir.sequence` | `addons/base/models/ir_sequence.py` |
| Editable sequence with prefix/year | `sequence.mixin` | `addons/account/models/sequence_mixin.py` |
| Portal access token / URL | `portal.mixin` | `addons/portal/models/portal_mixin.py` |
| UTM campaign/source/medium tracking | `utm.mixin` | `addons/utm/models/utm_mixin.py` |
| Analytic distribution | `analytic.mixin` | `addons/analytic/models/analytic_mixin.py` |
| Work schedule / calendar | `resource.mixin` | `addons/resource/models/resource_mixin.py` |
| Phone validation / blacklist | `mail.thread.phone` | `addons/mail/models/mail_thread_phone.py` |
| Email blacklist / bounce | `mail.thread.blacklist` | `addons/mail/models/mail_blacklist.py` |
| CC email handling | `mail.thread.cc` | `addons/mail/models/mail_thread_cc.py` |
| Stage time tracking | `mail.tracking.duration.mixin` | `addons/mail/models/mail_tracking_duration.py` |
| Customer satisfaction ratings | `rating.mixin` | `addons/rating/models/rating_mixin.py` |
| Website publish toggle | `website.published.mixin` | `addons/website/models/mixins.py` |
| SEO metadata fields | `website.seo.metadata` | `addons/website/models/mixins.py` |
| Date arithmetic | `odoo.tools.date_utils` | `odoo/tools/date_utils.py` |
| Float equality / comparison | `odoo.tools.float_utils` | `odoo/tools/float_utils.py` |
| HTML sanitization | `odoo.tools.mail.html_sanitize` | `odoo/tools/mail.py` |

**OCA modules** (check `~/shared/odoo-src/<version>/oca/` first, add to depends if available):

| If you need... | OCA Module | Path |
|---|---|---|
| Async job queue | `queue_job` | `oca/queue/queue_job/` |
| Audit trail / logging | `auditlog` | `oca/server-tools/auditlog/` |
| User role assignment | `base_user_role` | `oca/server-backend/base_user_role/` |
| Multi-image handling | `base_multi_image` | `oca/server-tools/base_multi_image/` |
| Mail activity board | `mail_activity_board` | `oca/mail/mail_activity_board/` |

---

## Standard Widgets — Use These, Don't Write Custom JS

Check this list before writing any custom JavaScript widget.

### Status & State
| Widget | Use for |
|---|---|
| `statusbar` | Stage pipeline at top of form (the standard) |
| `badge` | Read-only colored value pill |
| `state_selection` | Status dot + label dropdown |
| `priority` | Star rating (0–3 stars, selection field with 0/1/2/3 values) |
| `selection_badge` | Clickable button-badges for small option sets |

### Boolean
| Widget | Use for |
|---|---|
| `boolean_toggle` | iOS-style on/off toggle |
| `boolean_favorite` | Star favorite toggle |

### Numeric
| Widget | Use for |
|---|---|
| `monetary` | Float with currency symbol (default for monetary fields) |
| `float_time` | Float as HH:MM duration (timesheet hours) |
| `progressbar` | Horizontal progress bar with max value |
| `percentpie` | Circular percentage indicator |
| `statinfo` | Large number in stat button |
| `handle` | Drag handle for sequence ordering in list views |

### Relational
| Widget | Use for |
|---|---|
| `many2many_tags` | Default for many2many — colored tag pills |
| `many2many_checkboxes` | Small fixed sets of options as checkboxes |
| `many2many_tags_avatar` | Many2many with avatar images |
| `many2one_avatar` | Many2one with related record's image |
| `many2one_avatar_user` | Many2one for res.users with avatar |
| `radio` | 2–5 options as radio buttons instead of dropdown |

### Date & Time
| Widget | Use for |
|---|---|
| `daterange` | Span two date fields as a single range picker |
| `remaining_days` | Days remaining with color coding (green/orange/red) |

### File & Image
| Widget | Use for |
|---|---|
| `image` | Inline image with upload |
| `binary` | File upload/download button |
| `pdf_viewer` | Inline PDF viewer |
| `signature` | Draw-pad for handwritten signatures |

### Activity
| Widget | Use for |
|---|---|
| `kanban_activity` | Activity dot + popover on Kanban cards |
| `list_activity` | Activity icons in list view rows |

### Other
| Widget | Use for |
|---|---|
| `domain` | Domain rule editor (for char fields storing domain strings) |
| `color_picker` | 12-color Odoo palette (integer field 0–11) |
| `dashboard_graph` | Sparkline from JSON text field on Kanban cards |
| `html` | Rich-text WYSIWYG editor (default for html fields) |
| `ace` | Code editor with syntax highlighting |
| `copy_clipboard` | Read-only char with copy button |

---

## OCA Coding Standards

### Module Naming
- Singular form: `sale_order` not `sale_orders`
- Prefixes: `base_` (base modules), `l10n_XX_` (localizations)
- Extension modules: prefix with Odoo module name (e.g., `mail_forward`)

### Manifest (`__manifest__.py`)

```python
{
    "name": "Module Name",
    "version": "18.0.1.0.0",   # <odoo_version>.<major>.<minor>.<patch>
    "category": "Category",
    "summary": "Short one-line description",
    "author": "Author Name",
    "website": "https://github.com/org/repo",
    "license": "LGPL-3",        # or AGPL-3
    "depends": ["base"],
    "data": [
        "security/module_security.xml",   # security groups + rules FIRST
        "security/ir.model.access.csv",
        "data/module_data.xml",           # seed data
        "views/model_views.xml",
        "views/menu.xml",                 # menus LAST
    ],
    "demo": ["demo/model_demo.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

### Version Numbering
- **major**: Data model changes, breaking changes
- **minor**: New features, backward compatible
- **patch**: Bug fixes

### Python — Import Order

```python
# 1. Standard library
import logging
import os
from datetime import datetime, timedelta

# 2. Known third-party
import requests

# 3. Odoo framework
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# 4. Odoo addons
from odoo.addons.queue_job.exception import RetryableJobError

# 5. Local relative
from .utils import helper_function

_logger = logging.getLogger(__name__)

# Module-level constants (not inside methods)
HTTP_TIMEOUT = 30
MAX_RETRIES = 3
```

### Python — Class Structure

```python
class ModelName(models.Model):
    # 1. Private attributes
    _name = "model.name"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Human-Readable Description"
    _order = "name"

    # 2. Fields
    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one("res.partner", index=True)
    tag_ids = fields.Many2many("model.tag")
    content = fields.Html(sanitize=True)

    # 3. SQL constraints
    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", "Name must be unique."),
    ]

    # 4. Default methods
    def _default_name(self):
        return "Default"

    # 5. Compute methods
    @api.depends("field1", "field2")
    def _compute_total(self):
        for record in self:
            record.total = record.field1 + record.field2

    # 6. Constrains and onchange
    @api.constrains("field1")
    def _check_field1(self):
        for record in self:
            if not record.field1:
                raise ValidationError(_("Field1 is required."))

    @api.onchange("field2")
    def _onchange_field2(self):
        if self.field2:
            self.name = self.field2.name

    # 7. CRUD overrides
    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    # 8. Action methods
    def action_confirm(self):
        self.ensure_one()
        self.state = "confirmed"

    # 9. Business / private methods
    def _process_data(self):
        """Process internal data. Returns processed result."""
        for record in self:
            ...
```

### Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Compute | `_compute_<field>` | `_compute_total` |
| Inverse | `_inverse_<field>` | `_inverse_name` |
| Search | `_search_<field>` | `_search_status` |
| Default | `_default_<field>` | `_default_stage_id` |
| Onchange | `_onchange_<field>` | `_onchange_partner_id` |
| Constraint | `_check_<name>` | `_check_date_range` |
| Action | `action_<verb>` | `action_publish` |
| Cron | `_cron_<description>` | `_cron_sync_all` |
| Many2one | `_id` suffix | `stage_id` |
| x2many | `_ids` suffix | `line_ids` |

### XML Standards

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="model_name_view_form" model="ir.ui.view">
        <field name="name">model.name.view.form</field>
        <field name="model">model.name</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button string="Confirm" name="action_confirm"
                            type="object" class="oe_highlight"
                            invisible="state != 'draft'"/>
                    <field name="state" widget="statusbar" clickable="True"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button class="oe_stat_button" type="object"
                                name="action_view_lines" icon="fa-list">
                            <field name="line_count" widget="statinfo"
                                   string="Lines"/>
                        </button>
                    </div>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="partner_id"/>
                        </group>
                        <group>
                            <field name="date"/>
                            <field name="state" widget="badge"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Details">
                            <field name="line_ids">
                                <list>
                                    <field name="sequence" widget="handle"/>
                                    <field name="name"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                </sheet>
                <div class="alert alert-warning" role="alert"
                     invisible="not warning_message">
                    <field name="warning_message"/>
                </div>
                <chatter/>
            </form>
        </field>
    </record>
</odoo>
```

**XML ID naming:**

| Type | Pattern | Example |
|---|---|---|
| View | `<model>_view_<type>` | `sale_order_view_form` |
| Action | `<model>_action` | `sale_order_action` |
| Menu | `<model>_menu` | `sale_order_menu` |
| Group | `group_<module>_<role>` | `group_sale_manager` |
| Rule | `<model>_rule_<group>` | `sale_order_rule_manager` |
| Cron | `ir_cron_<description>` | `ir_cron_sync_orders` |

**Do not use `attrs=`** — deprecated since Odoo 17. Use `invisible=`, `readonly=`, `required=` directly.

### Security

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_model_user,model.name user,model_model_name,module.group_module_user,1,1,1,0
access_model_manager,model.name manager,model_model_name,module.group_module_manager,1,1,1,1
```

Never use string concatenation for SQL:
```python
# WRONG
cr.execute("SELECT id FROM table WHERE name = '" + name + "'")

# CORRECT
cr.execute("SELECT id FROM table WHERE name = %s", (name,))
```

`cr.commit()` — do not call in normal module code. Exceptions exist (e.g. long-running
batch migrations, Odoo shell scripts) but must be documented with an explanatory comment.

### Seed Data

```xml
<odoo>
    <data noupdate="1">   <!-- noupdate="1" prevents reset on upgrade -->
        <record id="stage_new" model="model.stage">
            <field name="name">New</field>
        </record>
    </data>
</odoo>
```

---

## Test Patterns

### Base Test Class

```python
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestModelName(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context,
            queue_job__no_delay=True,  # prevents background job enqueueing
        ))
        cls.record = cls.env["model.name"].create({"name": "Test Record"})

    def test_feature(self):
        """Test description — one line."""
        result = self.record.action_method()
        self.assertEqual(result, expected)
```

### Queue Job Testing

```python
from odoo.addons.queue_job.tests.common import trap_jobs

def test_job_creation(self):
    with trap_jobs() as trap:
        self.record.action_trigger()
        trap.assert_jobs_count(1)
        trap.perform_enqueued_jobs()
```

### Mocking HTTP Requests

```python
# Direct requests.get/post:
@patch("odoo.addons.module.models.model_name.requests.post")
def test_api_call(self, mock_post):
    mock_post.return_value = self._make_mock_response(200, {"key": "value"})
    ...

# requests.Session().post():
@patch.object(requests.Session, "post")
def test_session_call(self, mock_post):
    mock_post.return_value = self._make_mock_response(200, {"uid": 1})
    ...

def _make_mock_response(self, status_code, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.json.return_value = json_data or {}
    return response
```

### Running Tests

```bash
# Always use --http-port to avoid port conflicts with running container
docker run --rm --network opencode \
    -v $(pwd)/addons:/mnt/extra-addons \
    -v $(pwd)/odoo.conf:/etc/odoo/odoo.conf:ro \
    odoo:<version> odoo \
    -d test_<module>_$(date +%s) \
    -i <module> \
    --test-enable \
    --test-tags=/<module> \
    --stop-after-init \
    --http-port=18069 \
    -c /etc/odoo/odoo.conf
```

---

## Module Structure

```
addons/<module>/
├── __init__.py
├── __manifest__.py
├── hooks.py                    # post_init_hook / pre_init_hook (if needed)
├── models/
│   ├── __init__.py
│   └── model_name.py           # one file per logical model
├── views/
│   ├── model_name_views.xml
│   └── menu.xml                # menus in separate file, loaded last
├── data/
│   └── model_name_data.xml     # seed data with noupdate="1"
├── demo/
│   └── model_name_demo.xml     # realistic sample data
├── security/
│   ├── module_security.xml     # groups and record rules
│   └── ir.model.access.csv
├── i18n/                       # populated in Phase 2 (harden)
│   ├── de.po
│   └── fr.po
├── tests/
│   ├── __init__.py
│   ├── test_model_name.py
│   └── test_security.py
├── static/
│   └── description/
│       └── icon.png            # 128×128 or 256×256
└── README.md
```

---

## Infrastructure

### Container Naming

| Pattern | Example |
|---|---|
| Main project | `odoo-<project>` | `odoo-newsassistant` |
| Worktree | `odoo-<project>-<workspace>` | `odoo-newsassistant-happy-knight` |

### URLs

- Main: `https://<project>.opencode.socialcloud.ch`
- Worktree: `https://<project>-<workspace>.opencode.socialcloud.ch`

### Demo Credentials

- Username: `admin` / Password: `admin`
- Demo user: `demo` / Password: `demo`

### Shared Odoo Source

```
~/shared/odoo-src/
├── 17.0/
│   ├── community/    # CE source
│   ├── enterprise/   # EE source
│   └── oca/
└── 18.0/
    ├── community/    # CE source — read this before implementing anything
    ├── enterprise/   # EE source
    └── oca/
        ├── mail/
        ├── partner-contact/
        ├── queue/
        ├── server-backend/
        ├── server-tools/
        └── web/
```

Always read the actual source before using a mixin or utility. Don't rely on memory.

### Odoo Executable

```bash
docker exec <CONTAINER> odoo -d <DB> ...     # correct
docker exec <CONTAINER> odoo-bin -d <DB> ... # wrong — not found in official image
```

### Makefile Standard Targets

```bash
make upgrade           # upgrade all project modules
make upgrade-one MODULE=<name>  # upgrade single module
make restart           # restart container(s)
make rebuild           # full rebuild (drops DB, clears filestore, reinit)
make rebuild-demo      # full rebuild with demo data
make test              # run tests
make test-coverage     # run tests with coverage report
make smoke             # smoke test
make logs              # follow container logs
make shell             # open Odoo shell
make stop / start      # container lifecycle
```

---

## PDF Reports (QWeb)

```xml
<template id="report_model">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">   <!-- always t-as="doc", not "o" -->
            <t t-call="web.external_layout">
                <div class="page">
                    <span t-field="doc.name"/>
                </div>
            </t>
        </t>
    </t>
</template>
```

- Never `t-field` on block elements (`td`, `tr`, `li`) — only on inline elements
- Set `report.url` to `http://localhost:8069` in post-setup for correct CSS rendering
- Use `web.external_layout` (not a specific variant) — framework picks the company layout
