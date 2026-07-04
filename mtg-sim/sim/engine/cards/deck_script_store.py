"""Per-deck card script cache — synced from Drupal decks at runtime (Phase G).

JSON files live under ``data/deck_scripts/`` (gitignored). When a deck changes in
the database the fingerprint changes and the cache entry is refreshed, seeding
new cards from built-in templates while preserving any existing per-card scripts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck_registry import CardInfo
from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS
from engine.cards.effect_serde import EffectDict, effects_from_json, effects_to_json
from engine.cards.effects import CardEffect
from engine.cards.llm_script_generator import generate_card_script_json
from engine.cards.oracle_infer import infer_effects_from_oracle
from engine.cards.script_coverage import (
    DeckScriptCoverageReport,
    ScriptSource,
    build_coverage_report,
    parse_script_source,
)

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[2] / 'data' / 'deck_scripts'


@dataclass(frozen=True)
class DeckScriptSyncResult:
    """Scripts plus coverage metadata from one deck sync."""

    scripts: dict[str, tuple[CardEffect, ...]]
    coverage: DeckScriptCoverageReport


def deck_script_cache_root() -> Path:
    """Return the root directory for deck script JSON caches."""
    configured = os.environ.get('DECK_SCRIPT_CACHE_DIR', '').strip()
    root = Path(configured) if configured else _DEFAULT_CACHE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", '-', lowered)
    return lowered.strip('-') or 'deck'


def deck_fingerprint(cards: list[CardInfo]) -> str:
    """Hash deck composition so cache invalidates when the DB deck changes."""
    parts = sorted(
        f"{card.name}|{card.quantity}|{int(card.sideboard)}|{card.oracle_text}"
        for card in cards
    )
    digest = hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()
    return digest[:16]


def _unique_card_names(cards: list[CardInfo]) -> list[str]:
    return sorted({card.name for card in cards if card.name})


@dataclass(frozen=True)
class DeckScriptManifest:
    """On-disk JSON manifest for one deck's card scripts."""

    source_id: str
    title: str
    fingerprint: str
    updated_at: str
    cards: dict[str, list[EffectDict]]
    card_sources: dict[str, ScriptSource]

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest for on-disk JSON storage."""
        return {
            'source_id': self.source_id,
            'title': self.title,
            'fingerprint': self.fingerprint,
            'updated_at': self.updated_at,
            'cards': self.cards,
            'card_sources': self.card_sources,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeckScriptManifest:
        """Load manifest from parsed JSON."""
        return cls(
            source_id=str(data['source_id']),
            title=str(data.get('title', '')),
            fingerprint=str(data['fingerprint']),
            updated_at=str(data.get('updated_at', '')),
            cards={
                str(name): list(effects)
                for name, effects in (data.get('cards') or {}).items()
            },
            card_sources={
                str(name): parse_script_source(str(source))
                for name, source in (data.get('card_sources') or {}).items()
            },
        )


def _manifest_path(source_id: str) -> Path:
    if source_id.startswith('nid:'):
        nid = source_id.split(':', 1)[1]
        return deck_script_cache_root() / 'player' / f'{nid}.json'
    if source_id.startswith('meta:'):
        _, fmt, archetype = source_id.split(':', 2)
        return deck_script_cache_root() / 'meta' / fmt.lower() / f'{_slugify(archetype)}.json'
    safe = _slugify(source_id)
    return deck_script_cache_root() / 'other' / f'{safe}.json'


def _load_manifest(path: Path) -> DeckScriptManifest | None:
    if not path.exists():
        return None
    return DeckScriptManifest.from_dict(json.loads(path.read_text(encoding='utf-8')))


def _save_manifest(path: Path, manifest: DeckScriptManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding='utf-8')


def _manifest_to_scripts(manifest: DeckScriptManifest) -> dict[str, tuple[CardEffect, ...]]:
    return {
        name: effects_from_json(effects)
        for name, effects in manifest.cards.items()
    }


def _coverage_from_manifest(
    cards: list[CardInfo],
    manifest: DeckScriptManifest,
) -> DeckScriptCoverageReport:
    return build_coverage_report(cards, manifest.card_sources)


@dataclass(frozen=True)
class CardScriptSeed:
    """One card's seeded script JSON and how it was produced."""

    effects: list[EffectDict] | None
    source: ScriptSource


def _seed_non_creature_script(
    card: CardInfo,
    previous_cards: dict[str, list[EffectDict]],
) -> CardScriptSeed:
    """Resolve a non-creature script from cache, builtin, infer, or LLM."""
    if card.name in previous_cards:
        return CardScriptSeed(list(previous_cards[card.name]), 'cached')
    builtin = BUILTIN_CARD_SCRIPTS.get(card.name)
    if builtin is not None:
        return CardScriptSeed(effects_to_json(builtin), 'builtin')
    inferred = infer_effects_from_oracle(card)
    if inferred is not None:
        return CardScriptSeed(effects_to_json(inferred), 'inferred')
    llm_script = generate_card_script_json(card)
    if llm_script is not None:
        return CardScriptSeed(llm_script, 'llm')
    return CardScriptSeed(None, 'unscripted')


def seed_card_script(
    card: CardInfo,
    previous_cards: dict[str, list[EffectDict]],
) -> CardScriptSeed:
    """Resolve script JSON for one card and record how it was sourced."""
    if card.is_land:
        return CardScriptSeed(None, 'skipped_land')
    if card.is_creature:
        return CardScriptSeed(None, 'skipped_creature')
    return _seed_non_creature_script(card, previous_cards)


def _seed_card_script(
    card: CardInfo,
    previous_cards: dict[str, list[EffectDict]],
) -> list[EffectDict] | None:
    seed = seed_card_script(card, previous_cards)
    return seed.effects


def _build_synced_manifest(
    source_id: str,
    cards: list[CardInfo],
    *,
    title: str,
    fingerprint: str,
    previous_cards: dict[str, list[EffectDict]],
) -> DeckScriptManifest:
    """Seed scripts for all unique cards and build a manifest."""
    cards_by_name = {card.name: card for card in cards if card.name}
    card_entries: dict[str, list[EffectDict]] = {}
    source_by_name: dict[str, ScriptSource] = {}
    for name in _unique_card_names(cards):
        card = cards_by_name[name]
        seed = seed_card_script(card, previous_cards)
        source_by_name[name] = seed.source
        if seed.effects is not None:
            card_entries[name] = seed.effects
    return DeckScriptManifest(
        source_id=source_id,
        title=title,
        fingerprint=fingerprint,
        updated_at=datetime.now(timezone.utc).isoformat(),
        cards=card_entries,
        card_sources=dict(source_by_name),
    )


def sync_deck_scripts_with_coverage(
    source_id: str,
    cards: list[CardInfo],
    *,
    title: str = '',
) -> DeckScriptSyncResult:
    """Sync deck scripts and return coverage metadata."""
    path = _manifest_path(source_id)
    fingerprint = deck_fingerprint(cards)
    existing = _load_manifest(path)
    if existing is not None and existing.fingerprint == fingerprint:
        scripts = _manifest_to_scripts(existing)
        coverage = _coverage_from_manifest(cards, existing)
        return DeckScriptSyncResult(scripts=scripts, coverage=coverage)

    previous_cards = existing.cards if existing is not None else {}
    manifest = _build_synced_manifest(
        source_id,
        cards,
        title=title,
        fingerprint=fingerprint,
        previous_cards=previous_cards,
    )
    coverage = build_coverage_report(cards, manifest.card_sources)
    _save_manifest(path, manifest)
    logger.info(
        'Deck script sync %s: %.0f%% scripted (%d/%d unique cards)',
        source_id,
        coverage.scripted_pct * 100,
        coverage.scripted_unique_cards,
        coverage.total_unique_cards,
    )
    return DeckScriptSyncResult(
        scripts=_manifest_to_scripts(manifest),
        coverage=coverage,
    )


def sync_deck_scripts(
    source_id: str,
    cards: list[CardInfo],
    *,
    title: str = '',
) -> dict[str, tuple[CardEffect, ...]]:
    """Load or refresh the script cache for a deck; return resolved CardEffects."""
    return sync_deck_scripts_with_coverage(
        source_id,
        cards,
        title=title,
    ).scripts


def sync_player_deck_scripts(
    deck_nid: int,
    cards: list[CardInfo],
    *,
    title: str = '',
) -> dict[str, tuple[CardEffect, ...]]:
    """Sync scripts for a player deck identified by Drupal node ID."""
    return sync_deck_scripts(f'nid:{deck_nid}', cards, title=title)


def sync_meta_deck_scripts(
    fmt: str,
    archetype: str,
    cards: list[CardInfo],
) -> dict[str, tuple[CardEffect, ...]]:
    """Sync scripts for a meta archetype deck."""
    return sync_deck_scripts(f'meta:{fmt}:{archetype}', cards, title=archetype)


@dataclass(frozen=True)
class DeckMatchupScripts:
    """Inputs for syncing player + meta deck script caches for one game."""

    player_deck_nid: int
    player_cards: list[CardInfo]
    player_title: str
    meta_format: str
    meta_archetype: str
    opponent_cards: list[CardInfo]


def prepare_game_card_scripts(matchup: DeckMatchupScripts) -> dict[str, tuple[CardEffect, ...]]:
    """Sync player + opponent deck caches and merge for one game session."""
    return prepare_game_card_scripts_with_coverage(matchup).scripts


@dataclass(frozen=True)
class GameCardScriptsResult:
    """Merged card scripts and per-deck coverage for a matchup."""

    scripts: dict[str, tuple[CardEffect, ...]]
    player_coverage: DeckScriptCoverageReport
    opponent_coverage: DeckScriptCoverageReport

    @property
    def coverage_payload(self) -> dict[str, object]:
        """API-friendly coverage summary for both decks."""
        return {
            'player': self.player_coverage.to_dict(),
            'opponent': self.opponent_coverage.to_dict(),
        }


def prepare_game_card_scripts_with_coverage(
    matchup: DeckMatchupScripts,
) -> GameCardScriptsResult:
    """Sync caches, merge scripts, and return coverage for both decks."""
    player_result = sync_deck_scripts_with_coverage(
        f'nid:{matchup.player_deck_nid}',
        matchup.player_cards,
        title=matchup.player_title,
    )
    opponent_result = sync_deck_scripts_with_coverage(
        f'meta:{matchup.meta_format}:{matchup.meta_archetype}',
        matchup.opponent_cards,
        title=matchup.meta_archetype,
    )
    logger.debug(
        'Matchup script coverage player=%.0f%% opponent=%.0f%%',
        player_result.coverage.scripted_pct * 100,
        opponent_result.coverage.scripted_pct * 100,
    )
    merged = dict(opponent_result.scripts)
    merged.update(player_result.scripts)
    return GameCardScriptsResult(
        scripts=merged,
        player_coverage=player_result.coverage,
        opponent_coverage=opponent_result.coverage,
    )
