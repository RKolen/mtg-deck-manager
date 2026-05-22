"""
Keyword actions (Mill, Scry, Surveil, Fight, Proliferate, ...).

Most resolve as Effect subclasses in engine/cards/effects.py (Phase G).
Wire action verbs here only when they need keyword-specific stack timing.
"""

from __future__ import annotations

# Integration queue: see plan.md Phase E (action category, 72 entries).
