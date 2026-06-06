# AGENTS.md - MTG Deck Manager

This file covers the full MTG Deck Manager project: Drupal 11 headless backend
(`drupal/`) and Gatsby + TypeScript frontend (`mtg-app/`).

## Overview

The `drupal/` directory contains the Drupal 11 headless CMS. All Drupal/PHP
work is done here and requires DDEV for local development. The `mtg-app/`
directory contains the Gatsby + TypeScript frontend. See `plan.md` for the
full architecture and phase breakdown.

---

## Critical Rules (Non-Negotiable)

### 1. NO Emojis - NEVER

Never use emojis in any source or markup files in this directory (including
`.php`, `.twig`, `.yml`, `.md`, `.ts`, `.tsx`, and `.py`). Emojis can break
encoding, tooling, and copy-paste in some environments. Use plain text labels
instead.

### 2. DDEV Is Always Required

All commands that interact with the Drupal installation, Composer, Drush,
or any optional infrastructure services must be prefixed with `ddev`.
Never run these commands bare on the host machine.

Note: Milvus is not in the current stack but is retained here as a reference
for potential future use in deck/card similarity analysis.

```bash
# Start the environment first
ddev start

# Composer
ddev composer install
ddev composer require drupal/some_module
ddev composer update

# Drush
ddev drush cr
ddev drush updb
ddev drush cex
ddev drush cim

ddev exec <command>
```

After making structural changes you may need to rebuild:

```bash
ddev rebuild
```

### 3. PHP Code Quality Standards

All custom PHP code in `drupal/web/modules/custom/` must pass both quality
tools before committing.

**PHPCS with Drupal coding standard:**

```bash
ddev exec vendor/bin/phpcs --standard=Drupal,DrupalPractice \
  web/modules/custom
```

**PHPStan at minimum level 6:**

```bash
ddev exec vendor/bin/phpstan analyse \
  --level=6 \
  web/modules/custom
```

Rules:

- Never use `// phpcs:ignore` or `// phpstan-ignore` unless absolutely
  unavoidable; always fix the underlying issue instead.
- PHPStan level 6 enforces strict null checks and type inference. Add
  proper type hints and null guards rather than suppressing errors.
- Drupal coding standard requires proper docblocks for all hook
  implementations and public methods.

### 4. Drupal Contrib Patch Policy

Never directly edit files in `web/modules/contrib/`. When a bug is found in a
contrib module, follow this resolution order:

1. **Check for a module update** — run `ddev composer outdated drupal/module_name`
   and review the changelog. The fix may already exist in a newer release.
2. **Search the issue queue** — look on drupal.org for an open issue covering
   the bug. A patch or merge request may already be available for download.
3. **Apply a local patch** — only if steps 1 and 2 yield nothing:
   - Save the patch file to `patches/`.
   - Register it in `composer.json` under `extra.patches`.
   - Use Composer patch tooling so it reapplies automatically after updates.

This keeps contrib upgrades reproducible and prevents local hotfixes from
being lost on reinstall or update.

### 5. JSON:API Field Exposure

Every JSON:API resource config (`jsonapi_extras.jsonapi_resource_config.*.yml`)
must explicitly list **every** field on that content type. Fields not needed by
the frontend must have `disabled: true`. Fields needed by the frontend must have
`disabled: false`.

`jsonapi_extras` does not hide unknown fields by default — omitting a field
from the config leaves it exposed. The only reliable way to lock down a field
is to declare it with `disabled: true`.

Rules:

- Never expose a field that is not consumed by the frontend.
- When adding a new content type, enumerate all fields and disable unused ones.
- When adding a new field to an existing type, explicitly add it to the resource
  config (`disabled: true` if not yet used, `disabled: false` if immediately
  needed).
- After any change, run `ddev drush cex` and commit the updated YAML.
- Verify with `ddev drush cr` then inspect the live response to confirm only
  expected attributes appear.

### 6. One-Time Scripts

Scripts used for one-off data migrations or fixes must be placed in
`drupal/scripts/`, which is gitignored. Never commit one-time scripts to the
repository.

### 7. Form Displays

Every field on every content type, paragraph type, media type, and taxonomy
term must be placed in the `content` section of all relevant form displays. No
field may remain in the `hidden` section — all fields must be visible and
editable in the Drupal admin UI.

After adding a field, always verify it appears in the form display at
`/admin/structure/types/manage/{type}/form-display` and export the updated
config with `ddev drush cex`.

### 8. Never Commit or Push

Never run `git add`, `git commit`, `git push`, or any other git write command.
All commits and pushes are made exclusively by the developer. Only suggest what
should be committed and with what message if asked.

### 9. Documentation Must Track Code

| Change Type | Documentation to Update |
|-------------|------------------------|
| New custom module | this AGENTS.md, relevant `docs/` file if integration-facing |
| New DDEV service | this AGENTS.md infrastructure section |
| Changed infrastructure | `docs/architecture.md` |

### 10. Pylint Score: 10.00/10 Required

All code must achieve a perfect 10.00/10 Pylint score. Never use:

- `# pylint: disable=...`
- `# noqa`
- `# pragma` comments

Instead, fix the underlying issue. If Pylint complains, there is usually a
legitimate code quality issue to address.

Any style warnings are considered violations and must be fixed.

- never edit `pyproject.toml`
- never edit `pylintrc`

### 11. Full Pylint Output for Big Changes

For significant changes, always run the full Pylint checks:

```bash
python3 -m pylint mtg-sim/
```

Never use flags or pipes.
No issue is acceptable even if score is 10/10.

**All pylint output lines must be zero — including R0801 (duplicate-code).**
Never dismiss any warning as "informational only". If pylint reports it, fix it.
Duplicate code goes in in a shared file as a shared fixture helper.

#### 11.1 Pyright / Pylance (strict) required

Static types are enforced with **Pyright** (same engine as Pylance). Config:
`mtg-sim/sim/pyrightconfig.json`.

Install dev tools and run checks from the repo root:

```bash
chmod +x mtg-sim/check.sh
./mtg-sim/check.sh
```

Or manually:

```bash
mtg-sim/.venv/bin/pip install -r mtg-sim/sim/requirements-dev.txt
mtg-sim/.venv/bin/pyright mtg-sim/sim
```

Pyright must report **0 errors**. Cursor/VS Code should use
`mtg-sim/.venv` and strict analysis (see `.vscode/settings.json`).

For section 11, never dismiss type or pylint findings as pre-existing; fix them.

### 12. No Hardcoded Configuration Values

Never hardcode values that should be configurable. This includes:

- API keys, base URLs, or model names for AI services
- Wiki URLs for RAG system
- Default themes or display settings
- Any value that users should be able to configure

Instead, use the centralized configuration system in `src/config/`:

```python
# Wrong - hardcoded value
model: str = "gpt-3.5-turbo"

# Correct - use empty string, configure via config file or env
model: str = ""
```

The configuration system supports defaults through config files or environment
variables. See `src/config/config_types.py` for the configuration schema.

---

## Project Setup

### First-Time Setup

```bash
ddev config --project-type=drupal11 --docroot=web
ddev start
ddev composer install
ddev launch
```

### Applying Configuration

```bash
ddev drush cim   # import config
ddev drush cr    # rebuild Drupal cache
```

---

## Custom Modules

| Module | Path | Purpose |
|--------|------|---------|


## Environment files

| File | Purpose |
|------|---------|
| **`.env`** (repo root) | Single source of truth: ports, Ollama model, Drupal credentials, Forge paths. Used by `start.sh`, `mtg-sim/sim`, and `mtg-sim/sidecar`. |
| **`mtg-sim/sim/.env`** | Optional overrides only (e.g. machine-specific `FORGE_JAR`). Loaded after root `.env`. |

Forge LLM pilot work (rules + decision hooks) lives in the sibling clone
`../forge` on branch `mtg/llm-pilot`. See [docs/forge-llm-pilots.md](docs/forge-llm-pilots.md) (git-ignored).
| **`mtg-app/.env.development`** | Gatsby-only (`GATSBY_*`). `GATSBY_SIM_URL` port must match root `SIM_PORT`. |
| **`drupal/.ddev/config.yaml`** | Committed DDEV config with **empty** `web_environment` placeholders only. |
| **`drupal/.ddev/config.local.yaml`** | Local DDEV overrides (gitignored). Copy from `config.local.yaml.example`; set `MTG_SIM_SERVICE_URL`, `OLLAMA_*` from root `.env`. |

Template: copy `/.env.example` to `/.env`. If a port is already in use locally,
pick a free one and keep `GATSBY_SIM_URL`, `MTG_SIM_SERVICE_URL`, and `SIM_PORT`
aligned.

Do not use `mtg-sim/.env` (removed).

## Host Services (outside DDEV)

Ollama and the MTG AI sidecar run on the host to keep GPU/CPU inference out of
DDEV containers. Start everything with `./start.sh` from the repo root.

| Service | Path | Purpose |
|---------|------|---------|
| Ollama | host `OLLAMA_PORT` | LLM inference (qwen3:4b for pilots, nomic for embeddings) |
| AI sidecar | `mtg-sim/sidecar/` | FastAPI boundary: `/pilot-pick`, `/generate` — proxies to host Ollama |
| Sim API | `mtg-sim/sim/` | Forge/Python simulations; uses `SIDECAR_URL` for opponent/player pilots |

Simulation pilots:
- **Player deck** — `field_notes` on the deck node (same role as your heroic pilot prompt).
- **Gauntlet opponent** — `field_pilot_prompt` on the `meta_deck` node, with built-in
  fallbacks in `mtg-sim/sim/pilot_prompts.py` when the Drupal field is empty.

Drupal reaches host Ollama via `host.docker.internal` (not the deprecated DDEV
Ollama container). `MTG_SIM_SERVICE_URL` must match root `.env` `SIM_PORT` in
DDEV `web_environment`.

**Before running simulations:** `./start.sh` must have started the host sim
service. Drupal proxies `/api/simulate` to that service; if it is not running
you get a network or 503 error. Verify with:

```bash
curl http://localhost:$SIM_PORT/health
ddev exec curl -s http://host.docker.internal:$SIM_PORT/health
```

## Quick Reference

| Task | Command |
|------|---------|
| Start environment | `ddev start` |
| Stop environment | `ddev stop` |
| Rebuild | `ddev rebuild` |
| Install dependencies | `ddev composer install` |
| Add a module | `ddev composer require drupal/module_name` |
| Clear caches | `ddev drush cr` |
| Run DB updates | `ddev drush updb` |
| Export config | `ddev drush cex` |
| Import config | `ddev drush cim` |
| PHPCS check | `ddev exec vendor/bin/phpcs --standard=Drupal,DrupalPractice web/modules/custom` |
| PHPStan check | `ddev exec vendor/bin/phpstan analyse --level=6 web/modules/custom` |

---

## Directory Layout

```text
drupal/
|-- composer.json        # Dependency manifest + patch registry
|-- patches/             # Patch files for contrib modules
|-- web/
|   `-- modules/
|       |-- contrib/     # Downloaded modules - never edit directly
|       `-- custom/      # Custom modules - all PHP must pass PHPCS + PHPStan
|           `-- mtg_scryfall_sync/   # Scryfall bulk import + weekly cron resync
`-- private/             # Private files (git-ignored sensitive data)
```
