"""Unit tests for engine/core/mana.py and engine/cards/oracle_parse.is_affordable."""

from dataclasses import FrozenInstanceError

import pytest

from engine.cards.oracle_parse import is_affordable as spell_is_affordable
from engine.core.mana import (
    G,
    W,
    Mana,
    ManaCost,
    ManaPool,
    mana_of,
)
from tests.conftest import make_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pool(*colors: str) -> ManaPool:
    """Build a ManaPool containing exactly the listed color letters."""
    p = ManaPool()
    for c in colors:
        p.add(mana_of(c))
    return p


def cost(s: str) -> ManaCost:
    """Parse a mana cost string into a ManaCost."""
    return ManaCost.parse(s)


# ---------------------------------------------------------------------------
# Mana singleton
# ---------------------------------------------------------------------------

def test_mana_singletons_are_frozen():
    """Frozen dataclass prevents attribute assignment."""
    with pytest.raises(FrozenInstanceError):
        setattr(W, "color", "B")


def test_mana_invalid_color_raises():
    """Mana constructor rejects unknown color letters."""
    with pytest.raises(ValueError):
        Mana("Z")


def test_mana_of_returns_correct_singleton():
    """mana_of maps color letters to the module-level singleton instances."""
    assert mana_of("W") is W
    assert mana_of("G") is G


# ---------------------------------------------------------------------------
# ManaCost.parse
# ---------------------------------------------------------------------------

def test_parse_empty():
    """Empty string produces a zero-cost ManaCost that is_free."""
    c = cost("")
    assert c.mana_value == 0
    assert c.is_free


def test_parse_generic():
    """Generic mana {3} sets generic=3 and mana_value=3."""
    c = cost("{3}")
    assert c.generic == 3
    assert c.mana_value == 3


def test_parse_colored_pips():
    """{W}{U} sets pips correctly and totals to 2."""
    c = cost("{W}{U}")
    assert c.pips == {"W": 1, "U": 1}
    assert c.mana_value == 2


def test_parse_mixed():
    """{2}{W}{U} gives generic=2, two colored pips, mana_value=4."""
    c = cost("{2}{W}{U}")
    assert c.generic == 2
    assert c.pips == {"W": 1, "U": 1}
    assert c.mana_value == 4


def test_parse_colorless_pip():
    """{C} sets colorless=1 (cannot be paid with colored mana, CR 106.1c)."""
    c = cost("{C}")
    assert c.colorless == 1
    assert c.mana_value == 1


def test_parse_snow():
    """Two snow symbols set snow=2."""
    c = cost("{S}{S}")
    assert c.snow == 2
    assert c.mana_value == 2


def test_parse_variable_x():
    """{X} counts as 0 for mana value (CR 107.3b)."""
    c = cost("{X}{X}{R}")
    assert c.x_count == 2
    assert c.pips == {"R": 1}
    assert c.mana_value == 1


def test_parse_hybrid():
    """{W/U} adds one frozenset to hybrid list; mana_value=1."""
    c = cost("{W/U}")
    assert len(c.hybrid) == 1
    assert frozenset({"W", "U"}) in c.hybrid
    assert c.mana_value == 1


def test_parse_two_hybrid():
    """{2/W} adds W to two_hybrid list; mana_value=2."""
    c = cost("{2/W}")
    assert "W" in c.two_hybrid
    assert c.mana_value == 2


def test_parse_phyrexian():
    """{G/P} adds G to phyrexian list; mana_value=1."""
    c = cost("{G/P}")
    assert "G" in c.phyrexian
    assert c.mana_value == 1


def test_parse_double_black():
    """{B}{B} sets pips={B:2}, mana_value=2."""
    c = cost("{B}{B}")
    assert c.pips == {"B": 2}
    assert c.mana_value == 2


def test_color_identity_colored():
    """color_identity extracts all colors from pips."""
    c = cost("{2}{W}{U}")
    assert c.color_identity == frozenset({"W", "U"})


def test_color_identity_hybrid():
    """color_identity includes both sides of a hybrid pip."""
    c = cost("{W/U}")
    assert "W" in c.color_identity and "U" in c.color_identity


def test_str_round_trip_simple():
    """__str__ produces a parseable string with the same mana_value."""
    assert ManaCost.parse("{2}{W}{U}").mana_value == 4


# ---------------------------------------------------------------------------
# ManaPool.pay — basic cases
# ---------------------------------------------------------------------------

def test_pay_generic_from_colored():
    """Generic mana can be paid from any color source."""
    p = pool("R", "R", "R")
    assert p.pay(cost("{3}"))
    assert p.total() == 0


def test_pay_exact_colored():
    """Colored pips consume the matching mana from the pool."""
    p = pool("W", "U")
    assert p.pay(cost("{W}{U}"))
    assert p.total() == 0


def test_pay_colored_insufficient():
    """Mismatched color returns False and leaves the pool unchanged."""
    p = pool("W")
    assert not p.pay(cost("{U}"))
    assert p.total() == 1


def test_pay_generic_insufficient():
    """Too little mana for generic requirement returns False."""
    p = pool("R")
    assert not p.pay(cost("{2}"))
    assert p.total() == 1


def test_pay_mixed():
    """Mixed generic + colored cost paid correctly."""
    p = pool("W", "W", "U")
    assert p.pay(cost("{1}{W}{U}"))
    assert p.total() == 0


def test_pay_colorless_only_from_c():
    """{C} can only be paid with colorless {C} mana (CR 106.1c)."""
    p = pool("C")
    assert p.pay(cost("{C}"))
    assert p.total() == 0


def test_pay_colorless_refuses_colored():
    """Colored mana cannot satisfy a {C} requirement."""
    p = pool("W")
    assert not p.pay(cost("{C}"))


def test_pay_hybrid_uses_available():
    """Hybrid pip is paid with whichever color is available."""
    p = pool("U")
    assert p.pay(cost("{W/U}"))
    assert p.total() == 0


def test_pay_phyrexian_with_color():
    """Phyrexian mana paid with matching color consumes it."""
    p = pool("G")
    assert p.pay(cost("{G/P}"))
    assert p.total() == 0


def test_pay_phyrexian_no_color_zero_mana():
    """Phyrexian paid with life (tracked externally) requires no mana."""
    p = pool()
    assert p.pay(cost("{G/P}"))
    assert p.total() == 0


def test_pay_prefers_colorless_for_generic():
    """Generic cost uses colorless mana first to preserve colored mana."""
    p = pool("C", "W")
    assert p.pay(cost("{1}"))
    assert p.of_color("W") == 1
    assert p.of_color("C") == 0


# ---------------------------------------------------------------------------
# ManaPool.can_pay — does not spend mana
# ---------------------------------------------------------------------------

def test_can_pay_does_not_spend():
    """can_pay returns True without removing mana from the pool."""
    p = pool("R", "R")
    result = p.can_pay(cost("{R}{R}"))
    assert result
    assert p.total() == 2


def test_can_pay_false_does_not_change_pool():
    """can_pay returns False without modifying the pool on failure."""
    p = pool("W")
    assert not p.can_pay(cost("{U}"))
    assert p.total() == 1


# ---------------------------------------------------------------------------
# spell_is_affordable
# ---------------------------------------------------------------------------

def test_affordable_bolt_with_mana():
    """Lightning Bolt is affordable when the player has 1 mana."""
    bolt = make_card("Lightning Bolt", "Instant", cmc=1, mana_cost="{R}")
    assert spell_is_affordable(bolt, 1)


def test_affordable_bolt_without_mana():
    """Lightning Bolt is not affordable with 0 mana available."""
    bolt = make_card("Lightning Bolt", "Instant", cmc=1, mana_cost="{R}")
    assert not spell_is_affordable(bolt, 0)


def test_affordable_phyrexian_zero_mana():
    """Phyrexian mana card is castable with 0 mana (pay 2 life instead)."""
    growth = make_card("Mutagenic Growth", "Instant", cmc=1, mana_cost="{G/P}")
    assert spell_is_affordable(growth, 0)


def test_affordable_land_never():
    """Lands are played, not cast — always returns False."""
    land = make_card("Plains", "Basic Land — Plains", cmc=0)
    assert not spell_is_affordable(land, 10)
