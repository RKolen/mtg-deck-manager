"""
Interactive game package (Phase B).

Split from the former monolithic game.py:
  interactive.py  — player actions, combat flow, opponent AI
  spell_stack.py  — casting, storm copies, spell resolution
  runtime.py      — zones, mana, logging, client serialisation
  helpers.py      — shared pure helpers
  session.py      — create_game / session store
"""

from engine.game.interactive import InteractiveGame
from engine.game.session import create_game, get_game, remove_game

__all__ = [
    "InteractiveGame",
    "create_game",
    "get_game",
    "remove_game",
]
