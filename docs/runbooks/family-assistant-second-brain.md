# 🧠 Family Second Brain & AI Intelligence Runbook

This runbook documents the architecture, data flows, operational commands, cron pipelines, disaster recovery, and verification suites for the private, zero-cloud Family Second Brain and Open WebUI household assistant.

---

## 🏛️ Architecture & Principles

```
                  ┌────────────────────────────────────────────────────────┐
                  │                   Mobile Capture                       │
                  │  (Android: Microsoft To Do, Paprika, Obsidian Mobile) │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                      ┌───────────────────────┴────────────────────────┐
                      ▼                                                ▼
         ┌──────────────────────────┐                    ┌──────────────────────────┐
         │     Cloud / App APIs     │                    │  Local Mobile Capture    │
         │ (Graph API, Cal, Paprika)│                    │  (_Sync/Quick Add.md)    │
         └────────────┬─────────────┘                    └─────────────┬────────────┘
                      │                                                │
                      ▼                                                ▼
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │                      Homelab Sync Engine (WSL2 / Hosts)                      │
     │  - sync-todo-to-vault.py (every 15m)                                         │
     │  - sync-google-calendar-to-vault.py (every 15m)                              │
     │  - sync-paprika-to-vault.py (every 30m)                                      │
     │  - process-quick-add-outbox.py (every 5m)                                    │
     └──────────────────────────────────────┬───────────────────────────────────────┘
                                            │
                                            ▼
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │                      Obsidian Personal Vault ("Durable Memory")              │
     │  /mnt/c/Users/dtheurer/Obsidian/Vault/Personal/                              │
     │  ├── _Sync/ (todo-groceries.md, todo-family.md, calendar-family.md, etc.)     │
     │  ├── Recipes/ (13 Paprika markdown recipe archives)                          │
     │  ├── Maintenance/ (7 recurring vehicle & home seasonal service schedules)    │
     │  └── Daily/ (YYYY-MM-DD.md daily AI synthesized briefings)                   │
     └──────────────────────────────────────┬───────────────────────────────────────┘
                                            │
                                            ▼
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │                     Inference & RAG Engine (CT 104)                          │
     │  IP: 192.168.40.246                                                          │
     │  - Ollama Engine (11434): llama3.2:3b (100% offload to Quadro M1200 VRAM)   │
     │  - Open WebUI (3000): Model `family-assistant`                               │
     │  - Inlet Filter: second_brain_filter (deterministic pre-injection)            │
     │  - Tools: 5 registered function tools (To Do, Cal, Recipes, Maint, Health)   │
     └──────────────────────────────────────┬───────────────────────────────────────┘
                                            │
                                            ▼
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │                      Delivery & Push Alerts                                  │
     │  - generate-daily-briefing.py (daily 07:00 AM)                               │
     │  - Pushover HTML alerts with obsidian:// deep links                          │
     └──────────────────────────────────────────────────────────────────────────────┘
```

### Core Invariants
1. **Zero-Cloud Privacy**: All LLM inference, embedding generation, prompt context, and vault data stay strictly on local homelab hardware.
2. **Deterministic Context Pre-Injection ("Inlet Filter")**: Rather than relying on small 3B models to generate synthetic multi-turn JSON tool calls, `second_brain_filter.py` intercepts incoming user prompts and automatically injects live To Do items, calendar events, recipes, maintenance schedules, and homelab health into the context block.
3. **Decoupled Capture ("Mirror, Don't Proxy")**: Family members use native mobile apps (Microsoft To Do, Paprika, Google Calendar) without change. Background crons mirror data into static Markdown.
4. **Zero Unencrypted Secrets**: All credentials, tokens, and OAuth keys are encrypted using SOPS + age (`family-assistant-secrets.enc.yaml`).

---

## ⏰ Cron Automation Schedule

The active crontab on the system runs the following autonomous pipelines:

| Schedule | Interval | Target Script | Function |
| :--- | :---: | :--- | :--- |
| `*/15 * * * *` | 15 min | `sync-todo-to-vault.py` | Sync active Microsoft To Do lists to `_Sync/todo-*.md` |
| `*/15 * * * *` | 15 min | `sync-google-calendar-to-vault.py` | Sync Google Family Calendar to `_Sync/calendar-family.md` |
| `*/30 * * * *` | 30 min | `sync-paprika-to-vault.py` | Sync Paprika recipes, meal plans & groceries to `_Sync/` and `Recipes/` |
| `*/5 * * * *` | 5 min | `process-quick-add-outbox.py` | Process pending `- [ ]` checkboxes in `_Sync/Quick Add.md` |
| `0 7 * * *` | 07:00 AM | `generate-daily-briefing.py` | Generate daily briefing in `Daily/YYYY-MM-DD.md` & push to Pushover |
| `0 3 * * *` | 03:00 AM | `manage-family-secrets.py backup` | Encrypt & backup updated OAuth tokens to Git repository |

---

## 🛠️ Operational Commands & Runbook

### 1. Verification Suite (Regression Testing)
Run the automated 5-point evaluation suite against Open WebUI:

```bash
.venv/bin/python3 mcp/homelab/scripts/eval-family-assistant.py --model family-assistant
```

Expected result: 5/5 Passed (100.0%) across Groceries, Calendar, Recipes, Maintenance, and Homelab Fleet Health.

### 2. Manual Daily Briefing & Pushover Test
Generate the daily morning briefing and send it to your phone via Pushover:

```bash
# Preview briefing in stdout (dry-run)
.venv/bin/python3 mcp/family-assistant/scripts/briefing/generate-daily-briefing.py --dry-run

# Live generation (writes to Daily/YYYY-MM-DD.md and fires Pushover alert)
.venv/bin/python3 mcp/family-assistant/scripts/briefing/generate-daily-briefing.py
```

### 3. Outbox Processing (`_Sync/Quick Add.md`)
Test or trigger processing of items added from mobile:

```bash
# Preview items to process without modifying lists
.venv/bin/python3 mcp/family-assistant/scripts/outbox/process-quick-add-outbox.py --dry-run

# Process and dispatch pending items
.venv/bin/python3 mcp/family-assistant/scripts/outbox/process-quick-add-outbox.py
```

**Plain-Text Zero-Effort Capture (No Checkboxes or Tags Needed)**:
Type anything directly under `## 📥 Pending Outbox` in plain text. The local AI (`llama3.2:3b` on CT 104) automatically classifies and routes each item:

* **Groceries**: `Cinnamon rolls` or `Milk, eggs, butter` -> added to Microsoft To Do Groceries.
* **Tasks**: `Call accountant about taxes` or `Fix leaking sprinkler` -> added to Microsoft To Do Tasks.
* **Calendar**: `Dentist on Thursday at 2:30pm` -> scheduled in Google Family Calendar.
* **Recipe**: `https://pinchofyum.com/recipe-url` -> imported directly to Paprika Recipe Manager.
* *(Legacy tags like `[groc]`, `[todo]`, `[cal]`, `[recipe]` and checkboxes `- [ ]` remain fully supported if preferred).*

### 4. Sync Open WebUI Tools & Filter
Synchronize local Python tools and the global filter function to Open WebUI:

```bash
# Sync tools and valves
.venv/bin/python3 mcp/homelab/scripts/manage-openwebui.py sync_tools

# Inspect tool valves
.venv/bin/python3 mcp/homelab/scripts/manage-openwebui.py inspect_valves --tool-id microsoft_to_do_groceries_manager
```

### 5. Secrets Backup & Restore (SOPS + age)

```bash
# Check status of credentials against encrypted backup
.venv/bin/python3 mcp/family-assistant/scripts/backup/manage-family-secrets.py status

# Backup all ~/.config/homelab-todo/ tokens into encrypted Git bundle
.venv/bin/python3 mcp/family-assistant/scripts/backup/manage-family-secrets.py backup

# Restore credentials onto a new workstation or recovery environment
.venv/bin/python3 mcp/family-assistant/scripts/backup/manage-family-secrets.py restore --force
```

---

## 🔒 Secret Files Catalog

All credentials in `~/.config/homelab-todo/` are encrypted into `infrastructure/secrets/family-assistant-secrets.enc.yaml`:

| Filename | Purpose | Sensitive Fields Redacted |
| :--- | :--- | :--- |
| `config.json` | Master config | User IDs, default paths |
| `google_credentials.json` | Google Cloud OAuth App | `client_id`, `client_secret` |
| `google_token.json` | Live Google Calendar OAuth | `token`, `refresh_token` |
| `google_calendar.json` | Family Calendar ID | `calendar_id` |
| `token_cache.json` | Microsoft Graph / To Do Token Cache | `access_token`, `refresh_token` |
| `paprika.json` | Paprika Cloud Sync account | `email`, `password` |
| `paprika_cache.json` | Local cache of Paprika categories | Cached metadata |
| `pushover.json` | Pushover mobile alerting | `user_key`, `api_token` |
| `openwebui.json` | Open WebUI CT 104 API access | `api_key` |
