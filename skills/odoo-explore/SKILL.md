---
name: odoo-explore
description: Enter Odoo explore mode - think through ideas with Odoo context awareness, patterns, and infrastructure knowledge
license: MIT
metadata:
  author: opencode
  version: "2.0"
---

# Odoo Explore Mode

Enter exploration mode for Odoo development. This skill wraps `openspec-explore`
with Odoo-specific context from `reference-phase1.md`.

---

## Before You Begin

1. **Load the OpenSpec explore skill:**
   ```
   skill({ name: "openspec-explore" })
   ```

2. **Read the Odoo Phase 1 reference for context:**
   ```
   ~/.config/opencode/odoo/reference-phase1.md
   ```

3. **Detect project context** (if in an Odoo project):
   ```bash
   grep "image: odoo" docker-compose.yml | grep -oE '[0-9]+\.[0-9]+'  # version
   grep -q "enterprise" docker-compose.yml && echo "EE" || echo "CE"   # edition
   ls addons/                                                            # modules
   ```

---

## Odoo-Specific Context

### Infrastructure Knowledge
- Docker setup: `docker-compose.yml` defines the Odoo container
- URL pattern: `https://<project>.opencode.socialcloud.ch`
- Shared Odoo source: `~/shared/odoo-src/<version>/`
  - `community/` — CE source (read this before implementing anything)
  - `enterprise/` — EE source
  - `oca/` — OCA modules
- Database: Postgres in shared `opencode` network

### Standards Reference (from reference-phase1.md)
- OCA coding standards (module naming, Python patterns, XML conventions)
- Standard mixins — which to use instead of reimplementing
- Standard widgets — which to use instead of custom JS
- Test patterns (TransactionCase, queue jobs, mocking)
- Deployment cycle (upgrade / restart / smoke)

### Phase 1 DoD Awareness
When discussing implementation scope, keep Phase 1 DoD in mind:
- Module installs without errors
- Existing tests pass
- Smoke test passes
- Environment is English-only

Phase 2 concerns (translations, coverage, full audit) are for `/odoo-harden`.
Do not scope Phase 1 work to include these.

---

## How to Use

Follow the `openspec-explore` stance:
- Be curious, not prescriptive
- Use ASCII diagrams liberally
- Ground discussions in the actual codebase
- Surface multiple options, let the user choose

**Odoo-specific additions:**
- Reference OCA standards when discussing code patterns
- Proactively suggest standard mixins and widgets from `reference-phase1.md`
- Check if a standard Odoo or OCA pattern already covers what's being discussed:
  ```bash
  ls ~/shared/odoo-src/<version>/community/addons/
  ls ~/shared/odoo-src/<version>/oca/
  ```
- Visualize Odoo model relationships when relevant
- **Check field editability** when discussing UI changes:
  ```bash
  grep -A5 "<field_name> = fields\." addons/*/models/*.py | grep readonly
  grep "name=\"<field_name>\"" addons/*/views/*.xml | grep readonly
  ```

---

## Ending Exploration

When ready to implement, suggest:

> "Ready to implement? Run `/odoo-implement` to create a proposal and start building."

This will:
1. Create proposal, design, and tasks (via `openspec-propose`)
2. Immediately begin implementation (via `openspec-apply-change`)
3. Deploy and smoke-test the result
4. Enter the bug-fix loop for any issues the user reports
