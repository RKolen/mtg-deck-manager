"""Deck script coverage reporting (Phase G)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from deck_registry import CardInfo

ScriptSource = Literal[
    'cached',
    'builtin',
    'inferred',
    'llm',
    'unscripted',
    'skipped_creature',
    'skipped_land',
]

_SCRIPTED_SOURCES: frozenset[ScriptSource] = frozenset({
    'cached',
    'builtin',
    'inferred',
    'llm',
})


@dataclass(frozen=True)
class DeckScriptCoverageReport:
    """Summary of how a deck's unique cards were scripted during sync."""

    total_unique_cards: int
    scripted_unique_cards: int
    unscripted_spell_names: tuple[str, ...]
    by_source: dict[str, int] = field(default_factory=dict)

    @property
    def scripted_pct(self) -> float:
        """Fraction of unique cards with a structured script (0.0–1.0)."""
        if self.total_unique_cards <= 0:
            return 0.0
        return self.scripted_unique_cards / self.total_unique_cards

    def to_dict(self) -> dict[str, object]:
        """Serialize for API responses and logging."""
        return {
            'totalUniqueCards': self.total_unique_cards,
            'scriptedUniqueCards': self.scripted_unique_cards,
            'scriptedPct': round(self.scripted_pct, 4),
            'bySource': dict(self.by_source),
            'unscriptedSpellNames': list(self.unscripted_spell_names),
        }


def build_coverage_report(
    cards: list[CardInfo],
    source_by_name: dict[str, ScriptSource],
) -> DeckScriptCoverageReport:
    """Build a coverage report from per-card script sources."""
    cards_by_name = {card.name: card for card in cards if card.name}
    unique_names = sorted(cards_by_name)
    by_source: dict[str, int] = {}
    unscripted: list[str] = []
    scripted = 0
    spell_count = 0
    for name in unique_names:
        card = cards_by_name[name]
        if card.is_land:
            source: ScriptSource = 'skipped_land'
        elif card.is_creature:
            source = 'skipped_creature'
        else:
            spell_count += 1
            source = source_by_name.get(name, 'unscripted')
        by_source[source] = by_source.get(source, 0) + 1
        if source in _SCRIPTED_SOURCES:
            scripted += 1
        elif source == 'unscripted':
            unscripted.append(name)
    return DeckScriptCoverageReport(
        total_unique_cards=spell_count or len(unique_names),
        scripted_unique_cards=scripted,
        unscripted_spell_names=tuple(unscripted),
        by_source=by_source,
    )
