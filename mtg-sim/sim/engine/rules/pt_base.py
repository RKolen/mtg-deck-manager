"""Printed power/toughness helpers without game_object imports."""


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def raw_power_toughness(perm: object) -> tuple[int, int]:
    """Printed P/T without the CardInfo toughness floor (layers and SBAs)."""
    if getattr(perm, 'face_down', False):
        return 2, 2
    counters = getattr(perm, 'counters', {})
    if 'prototype_power' in counters:
        return (
            int(counters['prototype_power']),
            int(counters['prototype_toughness']),
        )
    card_info = getattr(perm, 'card_info', None)
    if card_info is not None:
        try:
            power = int(card_info.pt.split('/', maxsplit=1)[0])
        except (ValueError, TypeError, IndexError):
            power = 0
        try:
            toughness = int(card_info.pt.split('/', maxsplit=1)[1])
        except (ValueError, TypeError, IndexError):
            toughness = 0
        return power, toughness
    source = getattr(perm, 'source', None)
    if source is not None and hasattr(source, 'power') and hasattr(source, 'toughness'):
        return _parse_int(source.power), _parse_int(source.toughness)
    return 0, 0
