"""Compatibility shim for the Phase B engine cutover."""

from engine.game import InteractiveGame, create_game, get_game, remove_game

__all__ = ["InteractiveGame", "create_game", "get_game", "remove_game"]
