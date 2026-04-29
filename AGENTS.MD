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

### 5. Documentation Must Track Code

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
