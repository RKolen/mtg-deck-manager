"""Log detail helpers for announced casts."""

from __future__ import annotations

from engine.game.cast_announce_validate import PaidCastModifiers


def announce_cast_detail_suffix(
    mods: PaidCastModifiers,
    sacrificed_name: str,
) -> str:
    """Return parenthetical tags describing optional costs for a cast log line."""
    tags: list[str] = []
    for label, active in (
        ('miracle', mods.miracle),
        ('spectacle', mods.spectacle),
        ('morph', mods.morph),
        ('disguise', mods.disguise),
        ('dash', mods.dash),
        ('blitz', mods.blitz),
        ('cleave', mods.copy_casts.cleave),
        ('conspire', mods.copy_casts.conspire),
        ('demonstrate', mods.copy_casts.demonstrate),
        ('freerunning', mods.freerunning),
        ('overloaded', mods.overloaded),
        ('bestow', mods.bestow),
        ('entwined', mods.entwined),
        ('buyback', mods.buyback),
        ('mutate', mods.mutate),
    ):
        if active:
            tags.append(label)
    if mods.replicate_times:
        tags.append(f'replicate x{mods.replicate_times}')
    if mods.kicker_times:
        tags.append(f'kicked x{mods.kicker_times}')
    if mods.emerge:
        tags.append(f'emerge, sacrificed {sacrificed_name}')
    if mods.casualty:
        tags.append(f'casualty, sacrificed {sacrificed_name}')
    if mods.bargain:
        tags.append(f'bargain, sacrificed {sacrificed_name}')
    if mods.spree_modes:
        tags.append(f'spree modes {list(mods.spree_modes)}')
    if not tags:
        return ''
    return f" ({', '.join(tags)})"
