"""
Interactive game package (Phase B).

Split from the former monolithic game.py:
  interactive.py  — player actions, combat flow, opponent AI
  spell_stack.py  — hand casting, suspend, stack placement
  spell_stack_placement.py — stack placement (storm/cascade)
  spell_stack_graveyard.py / spell_stack_resolve.py — alternate casts and resolution
  runtime.py      — zones, mana, logging, client serialisation
  helpers.py      — shared pure helpers
  session.py      — create_game / session store
"""

from engine.game.interactive import InteractiveGame
from engine.game.session import _GameConfig, create_game, get_game, remove_game

__all__ = [
    "_GameConfig",
    "InteractiveGame",
    "create_game",
    "get_game",
    "remove_game",
]
