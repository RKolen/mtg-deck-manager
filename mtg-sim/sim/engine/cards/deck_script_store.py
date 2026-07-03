"""Per-deck card script cache — synced from Drupal decks at runtime (Phase G).

JSON files live under ``data/deck_scripts/`` (gitignored). When a deck changes in
the database the fingerprint changes and the cache entry is refreshed, seeding
new cards from built-in templates while preserving any existing per-card scripts.
"""

from __future__ import annotations

import hashlib
import json
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
from engine.cards.oracle_infer import infer_effects_from_oracle

_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[2] / 'data' / 'deck_scripts'


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest for on-disk JSON storage."""
        return {
            'source_id': self.source_id,
            'title': self.title,
            'fingerprint': self.fingerprint,
            'updated_at': self.updated_at,
            'cards': self.cards,
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


def _seed_card_script(
    card: CardInfo,
    previous_cards: dict[str, list[EffectDict]],
) -> list[EffectDict] | None:
    if card.name in previous_cards:
        return list(previous_cards[card.name])
    builtin = BUILTIN_CARD_SCRIPTS.get(card.name)
    if builtin is not None:
        return effects_to_json(builtin)
    inferred = infer_effects_from_oracle(card)
    if inferred is not None:
        return effects_to_json(inferred)
    return None


def sync_deck_scripts(
    source_id: str,
    cards: list[CardInfo],
    *,
    title: str = '',
) -> dict[str, tuple[CardEffect, ...]]:
    """Load or refresh the script cache for a deck; return resolved CardEffects."""
    path = _manifest_path(source_id)
    fingerprint = deck_fingerprint(cards)
    existing = _load_manifest(path)
    if existing is not None and existing.fingerprint == fingerprint:
        return _manifest_to_scripts(existing)

    previous_cards = existing.cards if existing is not None else {}
    cards_by_name = {card.name: card for card in cards if card.name}
    card_entries: dict[str, list[EffectDict]] = {}
    for name in _unique_card_names(cards):
        card = cards_by_name[name]
        seeded = _seed_card_script(card, previous_cards)
        if seeded is not None:
            card_entries[name] = seeded

    manifest = DeckScriptManifest(
        source_id=source_id,
        title=title,
        fingerprint=fingerprint,
        updated_at=datetime.now(timezone.utc).isoformat(),
        cards=card_entries,
    )
    _save_manifest(path, manifest)
    return _manifest_to_scripts(manifest)


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
    player_scripts = sync_player_deck_scripts(
        matchup.player_deck_nid,
        matchup.player_cards,
        title=matchup.player_title,
    )
    opponent_scripts = sync_meta_deck_scripts(
        matchup.meta_format,
        matchup.meta_archetype,
        matchup.opponent_cards,
    )
    merged = dict(opponent_scripts)
    merged.update(player_scripts)
    return merged
