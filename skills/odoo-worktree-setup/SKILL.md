---
name: odoo-worktree-setup
description: Set up an Odoo git worktree for development - configures container, database, Caddy routing, and environment
license: MIT
metadata:
  author: opencode
  version: "1.0"
---

# Odoo Worktree Setup

Detect whether the current workspace is a git worktree and ensure it is fully configured for Odoo development.

**Invoke this at the start of every `odoo-implement` run.** It is idempotent — safe to run multiple times.

---

## Step 1: Detect Worktree

```bash
# .git is a FILE in worktrees, a DIRECTORY in the main repo
if [ -f .git ]; then
    echo "worktree"
else
    echo "main"
fi
```

**If not a worktree:** Skip this skill entirely. Continue with normal flow.

**If a worktree:** Extract identifiers:

```bash
WORKSPACE_ID=$(basename "$PWD")
# e.g. "happy-knight"

PROJECT_NAME=$(grep "container_name:" docker-compose.yml | head -1 | awk '{print $2}' | sed 's/odoo-//')
# e.g. "newsassistant"

CONTAINER_NAME="odoo-${PROJECT_NAME}-${WORKSPACE_ID}"
# e.g. "odoo-newsassistant-happy-knight"

DB_NAME="${PROJECT_NAME}_${WORKSPACE_ID//-/_}"
# e.g. "newsassistant_happy_knight"

DOMAIN="${PROJECT_NAME}-${WORKSPACE_ID}.opencode.socialcloud.ch"
# e.g. "newsassistant-happy-knight.opencode.socialcloud.ch"

MAIN_PROJECT_DIR=$(cat .git | grep gitdir | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
# e.g. "/home/debian/projects/newsassistant"
```

---

## Step 2: Verify and Fix Each Component

Work through each component. **Auto-fix silently** — only report if something can't be fixed.

### 2a. Environment File

```bash
# Check
ls .env 2>/dev/null

# Fix: copy from main project
cp "${MAIN_PROJECT_DIR}/.env" .env
```

### 2b. docker-compose.override.yml

```bash
# Check
ls docker-compose.override.yml 2>/dev/null
```

If missing, create it:

```yaml
services:
  odoo-<PROJECT_NAME>:
    container_name: odoo-<PROJECT_NAME>-<WORKSPACE_ID>
    environment:
      - DB_NAME=<DB_NAME>
```

### 2c. odoo.conf database settings

```bash
# Check
grep "db_name" odoo.conf
```

The `db_name` and `db_filter` must match `DB_NAME`. If not, update them:

```bash
sed -i "s/^db_name = .*/db_name = ${DB_NAME}/" odoo.conf
sed -i "s/^db_filter = .*/db_filter = ${DB_NAME}/" odoo.conf
```

### 2d. odoo.conf worker settings

For worktrees, reduce workers to avoid resource contention:

```ini
workers = 2
max_cron_threads = 1

[queue_job]
channels = root:1
```

Check the current values and update if they exceed these limits.

### 2e. Caddy route

```bash
CADDY_CONF="${MAIN_PROJECT_DIR}/caddy-worktrees.conf"

# Check if route exists
grep -q "${CONTAINER_NAME}" "${CADDY_CONF}" 2>/dev/null
```

If missing, append:

```
<DOMAIN> {
    @websocket {
        path /websocket*
    }
    reverse_proxy @websocket <CONTAINER_NAME>:8072
    reverse_proxy <CONTAINER_NAME>:8069
}
```

Then reload Caddy:

```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## Step 3: Start Container

```bash
docker compose ps | grep -q "${CONTAINER_NAME}" || docker compose up -d
sleep 5
```

---

## Step 4: Initialize Database (if needed)

```bash
# Check if database exists
docker exec postgres psql -U opencode -lqt | grep -q "${DB_NAME}"
```

If the database does not exist, initialize it:

```bash
docker exec ${CONTAINER_NAME} odoo -d ${DB_NAME} -i newsassistant,newsfeed \
    --stop-after-init --http-port=8098
```

Use the modules from the `addons/` directory.

---

## Step 5: Verify

Run all checks and confirm everything is working:

```bash
# Container running
docker ps | grep ${CONTAINER_NAME}

# Env vars present
docker exec ${CONTAINER_NAME} env | grep -E "JINA|INFOMANIAK"

# Site accessible
curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}/web/login
# Must return 200

# CSS assets loading
ASSET_URL=$(curl -s https://${DOMAIN}/web/login | grep -oE '/web/assets/[^"]+\.css' | head -1)
curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}${ASSET_URL}"
# Must return 200
```

**If assets return 500** (filestore missing after rebuild), clear and restart:

```bash
docker exec ${CONTAINER_NAME} odoo -d ${DB_NAME} -u base \
    --stop-after-init --http-port=8098
docker restart ${CONTAINER_NAME}
sleep 5
```

---

## Output

On success, report:

```
## Worktree Ready

**Workspace:** <WORKSPACE_ID>
**Container:** <CONTAINER_NAME>  (running)
**Database:** <DB_NAME>
**URL:** https://<DOMAIN>/web/login  (200 OK, assets loading)
**API keys:** JINA ✓  INFOMANIAK ✓
```

On failure, report what failed and what was attempted.

---

## Naming Conventions Reference

| Item | Pattern | Example |
|------|---------|---------|
| Workspace ID | `basename $PWD` | `happy-knight` |
| Container | `odoo-<project>-<workspace>` | `odoo-newsassistant-happy-knight` |
| Database | `<project>_<workspace_underscored>` | `newsassistant_happy_knight` |
| URL | `<project>-<workspace>.opencode.socialcloud.ch` | `newsassistant-happy-knight.opencode.socialcloud.ch` |
| Caddy conf | `<main_project>/caddy-worktrees.conf` | `/home/debian/projects/newsassistant/caddy-worktrees.conf` |
