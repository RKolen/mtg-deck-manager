# MTG Deck Manager

A personal Magic: The Gathering deck management web application. Migrates
existing Excel/ODS spreadsheets to a full-stack web app with a Drupal 11
headless backend and a Next.js + TypeScript frontend.

---

## What It Does

- **Card database** — 100,000+ MTG cards imported from the Scryfall bulk data
  API (`default_cards`), stored as Drupal content nodes and synced weekly via
  cron.
- **Collection binder** — browse the full card pool, filter by color/type/CMC,
  view card detail with Scryfall artwork and oracle text, track owned and foil
  quantities.
- **Deck builder** — create and edit 60-card decks (or any format), add cards
  from the full card pool, set quantities, manage a sideboard.
- **Deck analysis** — replicates the spreadsheet analysis engine in TypeScript:
  - Mana curve (CMC histogram + average CMC)
  - Card type distribution
  - Effective mana sources per colour (lands = 1, mana producers = 0.5)
  - Fetchland colour attribution derived from oracle text
  - Utility land exclusion (Tabernacle, Maze of Ith, etc. correctly excluded)
  - Mana Color Distribution: sources % vs pip demand % per colour
  - Hypergeometric hand probability (chance of drawing N sources by turn T)
  - Mana/coloured-card ratio
- **Deck import** — drag-and-drop XLSX/ODS files, parse client-side, fuzzy-match
  card names (including smart-quote normalisation), review unmatched cards, and
  POST the complete deck in one operation.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + TypeScript |
| Backend | Drupal 11 (headless GraphQL) |
| PHP | 8.4 |
| Database | MySQL 8 |
| Local dev | DDEV |
| Card data source | Scryfall bulk data API |
| Charts | Recharts |
| HTTP client | Axios + TanStack React Query |
| XLSX parsing | xlsx.js (client-side) |

---

## Local Development

### Prerequisites

- [DDEV](https://ddev.readthedocs.io/) v1.24+
- Node.js 20+
- [Ollama](https://ollama.com/) installed on the host

### Quick Start

```bash
cp .env.example .env        # configure ports and URLs (gitignored)
./start.sh                  # start DDEV, Ollama, Milvus, and Next.js
./start.sh --stop           # stop all services
```

Logs are written to `.frontend.log` and `.ollama.log` in the project root.

### Manual Setup (first time only)

```bash
# Backend
cd drupal
ddev composer install
ddev drush cim   # import configuration
ddev drush cr    # rebuild cache

# Frontend
cd mtg-app
cp .env.example .env.local   # adjust credentials if needed
npm install
```

Drupal admin: https://mtg-deck-manager.ddev.site/user

Frontend: http://localhost:8001

### Environment Variables (`mtg-app/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_DRUPAL_URL` | `https://mtg-deck-manager.ddev.site` | Drupal base URL |
| `NEXT_PUBLIC_DRUPAL_USER` | `admin` | GraphQL basic-auth username |
| `NEXT_PUBLIC_DRUPAL_PASS` | `admin` | GraphQL basic-auth password |
| `NEXT_PUBLIC_SIM_URL` | `http://localhost:8002` | Python sim service (port matches root `SIM_PORT`) |

---

## Code Quality (Drupal)

All custom PHP in `drupal/web/modules/custom/` must pass before committing:

```bash
# Drupal coding standard
ddev exec vendor/bin/phpcs --standard=Drupal,DrupalPractice web/modules/custom

# Static analysis (level 6)
ddev exec vendor/bin/phpstan analyse --level=6 web/modules/custom
```

---

## Directory Layout

```text
drupal/          Drupal 11 headless backend (DDEV project root)
  composer.json  Dependencies + patch registry
  config/sync/   Drupal configuration (version-controlled)
  patches/       Patches for contrib modules
  web/modules/
    contrib/     Downloaded modules (never edit directly)
    custom/
      mtg_scryfall_sync/  Scryfall bulk import + weekly cron resync

mtg-app/         Next.js + TypeScript frontend
  src/
    pages/       Route pages (collection, decks/[id], import)
    components/  Shared React components
    services/    drupalApi.ts — GraphQL client (JSON:API-shaped adapters)
    utils/       deckAnalysis.ts — pure analysis functions
    types/       Shared TypeScript types (drupal.ts)
```

---

## Custom Drupal Modules

| Module | Path | Purpose |
|---|---|---|
| `mtg_scryfall_sync` | `web/modules/custom/mtg_scryfall_sync` | Scryfall bulk import and weekly cron resync |
