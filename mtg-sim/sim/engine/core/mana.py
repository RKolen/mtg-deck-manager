"""
Mana system for the MTG rules engine.

Provides three main types:
  Mana       — a single mana symbol in a pool (colored, colorless, or snow)
  ManaCost   — a parsed spell cost, e.g. {2}{W}{U}
  ManaPool   — a player's current floating mana, paid from and drained each step
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_COLORED = frozenset({"W", "U", "B", "R", "G"})
_ALL_COLORS = frozenset({"W", "U", "B", "R", "G", "C", "S"})

_TOKEN_RE = re.compile(r"\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Mana — a single symbol in a pool
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Mana:
    """One unit of mana floating in a player's mana pool.

    color must be one of W U B R G (colored), C (colorless, CR 106.1c),
    or S (snow, CR 106.1d). Frozen so Mana instances are hashable and
    can be stored in sets.
    """

    color: str

    def __post_init__(self) -> None:
        if self.color not in _ALL_COLORS:
            raise ValueError(f"Invalid mana color: {self.color!r}")


W = Mana("W")
U = Mana("U")
B = Mana("B")
R = Mana("R")
G = Mana("G")
C = Mana("C")
S = Mana("S")


def mana_of(color: str) -> Mana:
    """Return the singleton Mana constant for the given color letter."""
    _singletons = {"W": W, "U": U, "B": B, "R": R, "G": G, "C": C, "S": S}
    if color not in _singletons:
        raise ValueError(f"Invalid mana color: {color!r}")
    return _singletons[color]


# ---------------------------------------------------------------------------
# ManaCost — parsed representation of a spell's mana cost
# ---------------------------------------------------------------------------

@dataclass
class ManaCost:
    """Structured representation of a Scryfall mana cost string.

    Use ManaCost.parse("{2}{W}{U}") rather than constructing directly.
    Each field maps to a distinct cost category; the pay() method on
    ManaPool handles all of them in the correct CR priority order.
    """

    generic: int = 0
    colorless: int = 0
    pips: dict[str, int] = field(default_factory=dict)
    hybrid: list[frozenset[str]] = field(default_factory=list)
    two_hybrid: list[str] = field(default_factory=list)
    phyrexian: list[str] = field(default_factory=list)
    x_count: int = 0
    snow: int = 0

    @staticmethod
    def parse(cost_string: str) -> ManaCost:
        """Parse a Scryfall mana cost string into a ManaCost.

        Handles: generic ({0}–{20}), colored ({W}{U}{B}{R}{G}), colorless ({C}),
        snow ({S}), variable ({X}), hybrid ({W/U}), two-hybrid ({2/W}),
        and Phyrexian ({W/P}).
        """
        cost = ManaCost()
        for token in _TOKEN_RE.findall(cost_string.upper()):
            if token.isdigit():
                cost.generic += int(token)
            elif token == "X":
                cost.x_count += 1
            elif token == "C":
                cost.colorless += 1
            elif token == "S":
                cost.snow += 1
            elif token in _COLORED:
                cost.pips[token] = cost.pips.get(token, 0) + 1
            elif "/" in token:
                _parse_hybrid_token(cost, token)
        return cost

    @property
    def mana_value(self) -> int:
        """Total mana value (CMC). X counts as 0 per CR 107.3b."""
        return (
            self.generic
            + self.colorless
            + sum(self.pips.values())
            + len(self.hybrid)
            + len(self.two_hybrid) * 2
            + len(self.phyrexian)
            + self.snow
        )

    @property
    def color_identity(self) -> frozenset[str]:
        """Set of all colors referenced in this cost."""
        colors: set[str] = set(self.pips.keys())
        for hybrid_pair in self.hybrid:
            colors |= hybrid_pair
        colors.update(self.two_hybrid)
        colors.update(self.phyrexian)
        return frozenset(colors)

    @property
    def is_free(self) -> bool:
        """True when the cost requires zero mana of any kind."""
        return self.mana_value == 0 and self.x_count == 0

    def __str__(self) -> str:
        parts: list[str] = []
        if self.x_count:
            parts.extend(["{X}"] * self.x_count)
        if self.generic:
            parts.append(f"{{{self.generic}}}")
        if self.colorless:
            parts.extend(["{C}"] * self.colorless)
        if self.snow:
            parts.extend(["{S}"] * self.snow)
        for color, count in self.pips.items():
            parts.extend([f"{{{color}}}"] * count)
        for pair in self.hybrid:
            parts.append("{" + "/".join(sorted(pair)) + "}")
        for color in self.two_hybrid:
            parts.append(f"{{2/{color}}}")
        for color in self.phyrexian:
            parts.append(f"{{{color}/P}}")
        return "".join(parts)


def _parse_hybrid_token(cost: ManaCost, token: str) -> None:
    """Parse a slash-containing token into the appropriate ManaCost field."""
    parts = token.split("/")
    if len(parts) != 2:
        return
    a, b = parts
    if b == "P":
        cost.phyrexian.append(a)
    elif a.isdigit():
        cost.two_hybrid.append(b)
    else:
        cost.hybrid.append(frozenset({a, b}))


# ---------------------------------------------------------------------------
# ManaPool — floating mana available to a player this step
# ---------------------------------------------------------------------------

@dataclass
class ManaPool:
    """A player's floating mana for the current step or phase.

    Mana is added when lands tap or mana abilities resolve, and drained
    at the end of each step (CR 106.4).

    All payment methods work on a copy of the pool and only commit the
    change when payment succeeds, so the pool is never left in a
    partially-paid state.
    """

    pool: list[Mana] = field(default_factory=list)

    def add(self, *mana: Mana) -> None:
        """Add one or more Mana instances to the pool."""
        self.pool.extend(mana)

    def add_color(self, color: str, count: int = 1) -> None:
        """Add `count` mana of a single color by letter (e.g. 'G')."""
        self.pool.extend(mana_of(color) for _ in range(count))

    def empty(self) -> None:
        """Drain all floating mana (called at end of each step, CR 106.4)."""
        self.pool.clear()

    def total(self) -> int:
        """Total number of mana floating in the pool."""
        return len(self.pool)

    def of_color(self, color: str) -> int:
        """Count of a specific color currently in the pool."""
        return sum(1 for m in self.pool if m.color == color)

    def can_pay(self, cost: ManaCost) -> bool:
        """Return True if the pool can satisfy this cost without spending mana."""
        return ManaPool(pool=list(self.pool)).pay(cost)

    def pay(self, cost: ManaCost) -> bool:
        """Attempt to pay a ManaCost from this pool.

        Returns True and spends the mana on success.
        Returns False and leaves the pool unchanged on failure.

        Payment order (CR 601.2f priority):
          1. Colorless {C} — only colorless mana qualifies
          2. Colored pips — exact color match required
          3. Snow {S} — only snow mana qualifies
          4. Hybrid — best-available color chosen greedily
          5. Two-hybrid {2/W} — colored if available, else 2 generic
          6. Phyrexian {W/P} — colored if available; life paid externally
          7. Generic — any mana; colorless preferred to preserve colored

        Phyrexian alternative (2 life) is tracked outside this method
        because life payment requires a GameState reference.
        """
        working = list(self.pool)
        ok = (
            _drain_exact(working, "C", cost.colorless)
            and all(_drain_exact(working, c, n) for c, n in cost.pips.items())
            and _drain_exact(working, "S", cost.snow)
            and all(_drain_hybrid(working, h) for h in cost.hybrid)
            and all(_drain_two_hybrid(working, c) for c in cost.two_hybrid)
            and _drain_generic(working, cost.generic)
        )
        _drain_phyrexian(working, cost.phyrexian)
        if ok:
            self.pool = working
        return ok


# ---------------------------------------------------------------------------
# Internal payment helpers — all mutate `working` in place
# ---------------------------------------------------------------------------

def _drain_exact(working: list[Mana], color: str, count: int) -> bool:
    """Remove `count` mana of exact `color`; return False if insufficient."""
    for _ in range(count):
        mana = next((m for m in working if m.color == color), None)
        if mana is None:
            return False
        working.remove(mana)
    return True


def _drain_hybrid(working: list[Mana], options: frozenset[str]) -> bool:
    """Remove one mana matching any color in `options`, most-available first."""
    for color in sorted(options, key=lambda c: -sum(1 for m in working if m.color == c)):
        mana = next((m for m in working if m.color == color), None)
        if mana is not None:
            working.remove(mana)
            return True
    return False


def _drain_two_hybrid(working: list[Mana], color: str) -> bool:
    """Pay one colored mana or two generic mana for a {2/W}-type symbol."""
    mana = next((m for m in working if m.color == color), None)
    if mana is not None:
        working.remove(mana)
        return True
    if len(working) >= 2:
        working.pop()
        working.pop()
        return True
    return False


def _drain_phyrexian(working: list[Mana], colors: list[str]) -> None:
    """Pay the colored half of Phyrexian costs if available; else caller pays life."""
    for color in colors:
        mana = next((m for m in working if m.color == color), None)
        if mana is not None:
            working.remove(mana)


def _drain_generic(working: list[Mana], count: int) -> bool:
    """Remove any `count` mana; colorless preferred to preserve colored mana."""
    for _ in range(count):
        if not working:
            return False
        colorless = next((m for m in working if m.color in ("C", "S")), None)
        working.remove(colorless if colorless is not None else working[0])
    return True
