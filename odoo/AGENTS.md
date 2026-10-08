# Odoo Workflow System — Agent Guidelines

This document is for **LLMs and AI agents** who need to understand, use, or modify
the global Odoo development workflow system.

---

## What Is This?

A **two-phase development workflow** for Odoo that provides consistent patterns,
quality gates, and tooling across all projects.

```
PHASE 1 — VIBE CODING (per feature, repeated N times)
─────────────────────────────────────────────────────
/odoo-explore   ──▶  openspec-explore   + reference-phase1.md
/odoo-implement ──▶  openspec-propose + openspec-apply + Phase 1 DoD + deploy cycle
/odoo-finalize  ──▶  openspec-archive + git commit + push

PHASE 2 — HARDENING (once, before go-live)
──────────────────────────────────────────
/odoo-harden    ──▶  openspec-propose (harden-driven schema) + openspec-apply
                     Full 10-category project audit → remediation tasks
                     Rebuild + tests + translations + user setup + smoke
/odoo-finalize  ──▶  openspec-archive + git commit + push
```

### Phase 1 Loop

```
for each feature:
    /odoo-explore    → think through the feature
    /odoo-implement  → propose → implement → deploy → bug-fix loop
    /odoo-finalize   → archive change → commit → push
```

### Phase 2 (once before go-live)

```
/odoo-harden     → full project audit → fix everything → rebuild → smoke
/odoo-finalize   → archive hardening change → commit → push
```

---

## File Locations

```
~/.config/opencode/
├── odoo/
│   ├── AGENTS.md              ← You are here (meta-instructions)
│   ├── reference-phase1.md    ← Fast-coding reference (mixins, widgets, standards, deploy)
│   └── reference-phase2.md    ← Full DoD, 10-category audit, coverage, translations
│
└── skills/
    ├── odoo-explore/          ← Wraps openspec-explore + reference-phase1.md
    ├── odoo-implement/        ← Phase 1: propose + apply + deploy + bug-fix loop
    ├── odoo-harden/           ← Phase 2: whole-project audit + remediation
    ├── odoo-finalize/         ← Wraps openspec-archive + git commit + push
    ├── odoo-worktree-setup/   ← Worktree container/DB/Caddy/env setup (called by odoo-implement)
    ├── odoo-guidelines/       ← Addon house rules (Python/ORM, fields, XML, reports, security, tests)
    ├── odoo-web-guidelines/   ← static/ house rules (JS, Owl templates, SCSS)
    ├── odoo-security/         ← Security audit material (used by review + harden)
    └── odoo-review/           ← Review a diff/commit/PR against the house rules

~/.local/share/openspec/schemas/
└── harden-driven/             ← Global openspec schema for hardening changes
    ├── schema.yaml
    └── templates/
        ├── audit.md
        └── harden-tasks.md
```

### Reference File Purposes

| File | Phase | When to Read |
|---|---|---|
| `reference-phase1.md` | 1 | During explore and implement — fast-coding context |
| `reference-phase2.md` | 2 | During harden — full DoD, audit specs, workflows |

---

## How the Skills Work

### Wrapping Strategy

Odoo skills **wrap** OpenSpec skills rather than replacing them:

```
odoo-explore   ──▶  openspec-explore   + reference-phase1.md context
odoo-implement ──▶  openspec-propose + openspec-apply + Phase 1 DoD
odoo-harden    ──▶  openspec-propose (harden-driven) + openspec-apply + Phase 2 DoD
odoo-finalize  ──▶  openspec-archive + git commit + push

Supporting skills (not OpenSpec wrappers):
odoo-worktree-setup ──▶ worktree container/DB/Caddy/env setup (idempotent, called by odoo-implement)
odoo-guidelines     ──▶ Odoo addon house rules (Python/ORM, fields, XML, reports, security, tests)
odoo-web-guidelines ──▶ static/ house rules (JS, Owl, SCSS)
odoo-security       ──▶ security audit material (used by odoo-review and odoo-harden)
odoo-review         ──▶ dispatch a diff/commit/PR across guidelines + security
```

OpenSpec skill improvements automatically benefit the Odoo workflow.
Odoo-specific behavior is additive, not a fork.

### Phase 1 Definition of Done

`/odoo-implement` enforces these checks (lightweight):

1. All tasks in `tasks.md` are `[x]`
2. Module installs without errors
3. Existing tests pass (no coverage gate)
4. Smoke test passes (login 200, assets 200)

Environment is English-only. No translations installed.

### Phase 2 Definition of Done

`/odoo-harden` enforces these checks (zero tolerance):

1. All 10 audit categories resolved across all modules
2. Version bumped in all modified `__manifest__.py` files
3. Pre-commit passes (if `.pre-commit-config.yaml` exists)
4. Fresh instance rebuilt with demo data
5. All modules install without errors
6. All tests green
7. Coverage ≥ 80% across all modules
8. FR + DE languages installed and module translations loaded
9. `admin` and `demo` users switched to German (de_DE)
10. Smoke test passes
11. Login URL and credentials reported to user

### 10 Audit Categories (Phase 2)

| # | Category |
|---|---|
| 1 | Manifest Integrity |
| 2 | Python Code Correctness |
| 3 | Security |
| 4 | XML / View Quality |
| 5 | Performance |
| 6 | Structural Completeness |
| 7 | Maintainability |
| 8 | Documentation |
| 9 | Tooling Compliance |
| 10 | Standard Pattern Compliance |

Full details: `reference-phase2.md`

### The `harden-driven` OpenSpec Schema

A globally available schema at `~/.local/share/openspec/schemas/harden-driven/`.
Tier 2 (user-global) in the openspec resolver — available to every project
without per-project configuration.

Artifacts:
- `audit.md` — full project audit (no deps)
- `harden-tasks.md` — remediation task checklist (depends on audit)

Usage:
```bash
openspec new change "project-hardening" --schema harden-driven
```

---

## How to Modify This System

### Adding a New Skill

1. Create directory: `~/.config/opencode/skills/odoo-<name>/`
2. Create `SKILL.md` with the required YAML frontmatter (`name` and `description`).
   `license` and `metadata` are optional — some skills include them:

```yaml
---
name: odoo-<name>
description: Brief description (1-1024 chars)
---
```

3. **Restart OpenCode server** (required for skill discovery)

### Modifying Phase 1 Reference

1. Edit `~/.config/opencode/odoo/reference-phase1.md`
2. No server restart needed — read at runtime

### Modifying Phase 2 Reference / DoD

1. Edit `~/.config/opencode/odoo/reference-phase2.md`
2. If enforcement logic changes, update `odoo-harden/SKILL.md`
3. **Restart OpenCode server** if SKILL.md was changed

### Modifying the `harden-driven` Schema

1. Edit `~/.local/share/openspec/schemas/harden-driven/schema.yaml`
2. Validate: `openspec schema validate harden-driven`
3. No server restart needed — schema is read by openspec CLI at runtime

### Updating Standard Mixin / Widget Reference

1. Edit the relevant section in `reference-phase1.md`
2. If new patterns were discovered from `~/shared/odoo-src/`, update both
   `reference-phase1.md` (quick-reference) and `reference-phase2.md` (audit checks)

---

## Server Restart Requirement

**Required after modifying any `SKILL.md`:**

```bash
# systemd service:
sudo systemctl restart opencode

# Manual:
opencode serve
```

Changes to `reference-phase1.md`, `reference-phase2.md`, `AGENTS.md`, and
`schema.yaml` do NOT require restart — they are read at runtime.

---

## Project Detection

Odoo projects are identified by:
1. `docker-compose.yml` with `image: odoo:<version>`
2. `addons/` directory with Odoo modules

**Version:** parsed from the Docker image tag (e.g., `odoo:<version>`); supported: 17.0–20.0
**Edition:** CE = no enterprise volume; EE = enterprise addons volume mounted
**Container/DB:** always read from `docker-compose.override.yml` and `odoo.conf`

---

## Test Execution

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

Key points:
- Use `docker run` (not `docker compose exec`) for test isolation
- Use unique DB names with timestamp suffix
- Use `-T` flag with `docker compose exec` for non-interactive execution
- `--no-http` does NOT work reliably in Odoo 18+

---

## Troubleshooting

### Skill Not Found

1. Check: `ls ~/.config/opencode/skills/odoo-*/SKILL.md`
2. Verify YAML frontmatter has `name` and `description`
3. Verify `name` matches directory name
4. **Restart OpenCode server**

### harden-driven Schema Not Found

```bash
openspec schema validate harden-driven
ls ~/.local/share/openspec/schemas/harden-driven/
```

### Phase 1 Smoke Failure

1. Read logs: `docker logs <CONTAINER> --tail 50`
2. Fix error, re-upgrade, re-smoke
3. For asset 500: clear asset cache (see `reference-phase1.md`)

### Version History

| Date | Change |
|---|---|
| 2026-10-08 | Added Odoo 20 to supported versions and shared sources |
| 2026-10-08 | Documented odoo-guidelines / odoo-web-guidelines / odoo-security / odoo-review / odoo-worktree-setup |
| 2026-05-03 | Two-phase redesign: implement (Phase 1) + harden (Phase 2) |
| 2026-05-03 | Added harden-driven global openspec schema |
| 2026-05-03 | Split reference.md into reference-phase1.md + reference-phase2.md |
| 2026-05-03 | Added standard mixin/widget quick-reference to Phase 1 |
| 2026-05-03 | Added deployment cycle (upgrade/restart/smoke) to implement skill |
| 2026-04-19 | Added Makefile standard for rebuild/test/smoke operations |
| 2026-04-14 | Initial creation of global Odoo workflow system |
