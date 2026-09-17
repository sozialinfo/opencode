---
name: odoo-implement
description: Implement Odoo features with full Definition of Done enforcement - creates proposal, implements tasks, ensures tests, translations, and fresh instance
license: MIT
metadata:
  author: opencode
  version: "2.0"
---

# Odoo Implement (Phase 1 — Vibe Coding)

Implement an Odoo feature from proposal to working deployment.

This skill:
1. Sets up the worktree environment
2. Creates a proposal (via `openspec-propose`)
3. Implements all tasks (via `openspec-apply-change`)
4. Deploys and smoke-tests the result
5. Asks the user to verify
6. Handles bug-fix prompts in a tight fix → deploy → verify loop

**Phase 1 goal:** Working code, deployed and verifiable. Fast iteration.
**No translations, no coverage gates, no fresh rebuild.**
Those are Phase 2 (`/odoo-harden`) concerns.

---

## Before You Begin

Read the Phase 1 coding reference:

```
~/.config/opencode/odoo/reference-phase1.md
```

This contains:
- Deployment cycle commands (upgrade / restart / smoke)
- Standard mixins and widgets to use proactively
- OCA coding standards, class structure, naming conventions
- Test patterns, module structure, infrastructure conventions

---

## Workflow

### Phase 0: Worktree Setup

```
skill({ name: "odoo-worktree-setup" })
```

Ensures container, database, Caddy routing, and env vars are correct.
No-op if not a worktree.

### Phase 0.5: Guidelines Reference

Load the house rules skill:

```
skill({ name: "odoo-guidelines" })
```

Provides module structure, manifest, Python/ORM, fields, controllers, XML views and data, QWeb reports, access rights, performance, and tests conventions. Apply this knowledge throughout Phase 2 implementation — do **not** mix conventions from different versions.

### Phase 1: Proposal

```
skill({ name: "openspec-propose" })
```

Creates:
- `proposal.md` — what and why
- `design.md` — technical approach
- `tasks.md` — implementation checklist

### Phase 2: Implementation

```
skill({ name: "openspec-apply-change" })
```

Work through all tasks, marking complete as you go.

While implementing, proactively apply patterns from two sources:

1. **Guidelines skill** (loaded in Phase 0.5) — consult for ORM API, view syntax, field types, security, OWL patterns, and house rules.
2. **`reference-phase1.md`** — deployment cycle, mixins, widgets, OCA standards, module structure, code correctness checklist.

Key checklist items (from reference-phase1.md):
- Use standard mixins instead of reimplementing (check `~/shared/odoo-src/<version>/`)
- Use standard widgets instead of custom JS
- Follow class structure, naming conventions, XML standards
- Apply the key code correctness checklist (ensure_one, model_create_multi, index, etc.)

Following these patterns now avoids major refactoring in Phase 2.

### Phase 3: Deployment

When all tasks are `[x]`, run the deployment cycle once:

```
skill: run the deployment cycle from reference-phase1.md
```

**Do not run the deployment cycle between individual tasks** — complete all tasks
first, then deploy.

### Phase 4: Phase 1 Definition of Done

After a green smoke test, verify:

1. **All tasks `[x]`** in `tasks.md`
2. **Module installs without errors:**
   ```bash
   docker exec <CONTAINER> odoo -c /etc/odoo/odoo.conf -d <DB> -i <module> --stop-after-init
   ```
3. **Existing tests pass:**
   ```bash
   make test
   # or: docker run ... odoo -d test_<module>_$(date +%s) -i <module> --test-enable --test-tags=/<module> --stop-after-init --http-port=18069
   ```
   No coverage gate. No new test requirement. Just verify nothing is broken.
4. **Smoke test green** (login 200, assets 200)

Then report to the user:

```
## Phase 1 Complete

**URL:** https://<project>.opencode.socialcloud.ch/web/login
**Credentials:** admin / admin
**Language:** English

Please verify the feature works as expected.
When ready to keep iterating: describe the next change or bug to fix.
When done with this feature: run `/odoo-finalize`.
Before going live: run `/odoo-harden`.
```

---

## Deployment Cycle

Use this cycle after all tasks are done, and after every bug fix.

### 1. Detect Context

```bash
# Container name (worktree override takes priority)
grep "container_name:" docker-compose.override.yml 2>/dev/null | awk '{print $2}' || \
grep "container_name:" docker-compose.yml | awk '{print $2}'

# Database (always read from odoo.conf — never assume)
grep "^db_name" odoo.conf | awk -F' = ' '{print $2}'

# Modules
ls addons/
```

### 2. Upgrade

```bash
# With Makefile:
make upgrade
make upgrade-one MODULE=<name>   # if single module target exists

# Without Makefile:
docker exec <CONTAINER> odoo -c /etc/odoo/odoo.conf -d <DB> -u <modules> --stop-after-init
```

### 3. Restart

```bash
make restart                     # if Makefile exists
docker restart <CONTAINER>       # raw container
docker compose restart odoo      # compose service
```

### 4. Smoke Test

```bash
make smoke                       # if Makefile exists

# Manual:
curl -s -o /dev/null -w "%{http_code}" https://<project>.opencode.socialcloud.ch/web/login
# Expected: 200

ASSET_URL=$(curl -s https://<project>.opencode.socialcloud.ch/web/login | grep -oE '/web/assets/[^"]+\.css' | head -1)
curl -s -o /dev/null -w "%{http_code}" "https://<project>.opencode.socialcloud.ch${ASSET_URL}"
# Expected: 200
```

### 5. Handle Smoke Failures

**500 on login (Python error):**
```bash
docker logs <CONTAINER> --tail 50
# Fix the error, then restart from step 2
```

**200 login, 500 on assets (stale asset cache):**
```bash
docker compose exec -T odoo odoo shell -d <DB> --http-port=18069 -c /etc/odoo/odoo.conf <<'EOF'
env['ir.attachment'].search([('url', 'like', '/web/assets/')]).unlink()
env.cr.commit()
EOF
docker compose restart odoo
# Re-smoke
```

**Module not in installed state:**
```bash
docker exec <CONTAINER> odoo -c /etc/odoo/odoo.conf -d <DB> -i <module> --stop-after-init
docker restart <CONTAINER>
# Re-smoke
```

Only report success to the user after a green smoke test.

### When to Upgrade vs. Full Rebuild

| Situation | Action |
|---|---|
| Python, XML, CSV change | `upgrade + restart` |
| New module added to `depends` | `upgrade + restart` |
| New column on table with no existing rows | `upgrade + restart` |
| `_sql_constraints` conflict with existing data | full rebuild |
| Required field without default on populated table | full rebuild |
| User asks for a fresh start | full rebuild |

Full rebuild: `make rebuild-demo` or `make rebuild`

---

## Bug-Fix Loop

After the user verifies the initial deployment, they may report bugs or request
changes. Handle each prompt in this tight loop:

1. **Read the error** — look at logs if needed: `docker logs <CONTAINER> --tail 50`
2. **Fix the code**
3. **Run the deployment cycle** (upgrade + restart + smoke)
4. **Report result** — "Fixed and deployed. Please re-verify."
5. **Repeat** as needed

No openspec ceremony for bug fixes. No new tasks.md entry needed.
Just fix, deploy, verify.

---

## Project Detection

### Odoo Executable
```bash
docker exec <CONTAINER> odoo -d <DB> ...     # correct
docker exec <CONTAINER> odoo-bin -d <DB> ... # wrong
```

### Worktree Detection
`.git` is a FILE in worktrees, a DIRECTORY in the main repo.
In worktrees, container and DB names differ from project name.
Always read from `docker-compose.override.yml` and `odoo.conf`.

### Version Detection
```bash
grep "image: odoo" docker-compose.yml | grep -oE '[0-9]+\.[0-9]+'
```

### Edition Detection
```bash
grep -q "enterprise" docker-compose.yml && echo "EE" || echo "CE"
```

---

## Language Environment (Phase 1)

Phase 1 runs in English only. This is correct and intentional.
- No translation files generated
- No language packs installed
- `admin` and `demo` users remain in English

Translations are a Phase 2 (`/odoo-harden`) concern.

---

## Error Handling

### Test Failures
1. Read the test output
2. Fix the code or test
3. Re-run tests
4. Re-smoke if tests passed

### Docker Issues
```bash
docker compose ps                     # check container state
docker compose logs <container>       # check logs
docker compose restart                # restart if needed
```

### Upgrade Errors
If `--stop-after-init` exits with error:
```bash
docker logs <CONTAINER> --tail 100
```
Look for Python tracebacks or XML parse errors. Fix and retry.

---

## Completion

When Phase 1 DoD is satisfied:

```markdown
## Phase 1 Complete

**Change:** <change-name>
**Module:** <module-name>

### Phase 1 DoD
- [x] All tasks complete
- [x] Module installs without errors
- [x] Existing tests pass
- [x] Smoke test passed

**URL:** https://<project>.opencode.socialcloud.ch/web/login
**Credentials:** admin / admin

Please verify the feature. Describe any bugs or changes needed.

When this feature is done:
- Run `/odoo-finalize` to archive and push
- Continue with the next feature by describing it
- Run `/odoo-harden` when ready to go live (hardens the whole project)
```
