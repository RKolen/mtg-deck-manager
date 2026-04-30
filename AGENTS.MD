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

Never use emojis in any `.php`, `.twig`, `.yml`, or `.md` files in this
directory. This is a hard requirement shared with the rest of the project.

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
