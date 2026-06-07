"""Unit tests for Forge [Pilot] log parsing."""

from __future__ import annotations

from forge_verbose_parser import _parse_forge_verbose_output


def test_parse_tagged_pilot_notes_by_side() -> None:
    """Tagged pilot lines split into player vs opponent note lists."""
    stdout = "\n".join([
        "[Pilot] Ai(1)-Heroic: active",
        "[Pilot] Ai(2)-Ruby Storm: active",
        "[Pilot] Ai(1)-Heroic: mulligan: Keep — lethal turn 3",
        "[Pilot] Ai(2)-Ruby Storm: mulligan: Keep — need reducer",
        "[Pilot] Ai(1)-Heroic: T2 spell: Hoplite — go wide",
        "[Pilot] Ai(2)-Ruby Storm: T3 spell: Manamorphose — dig",
        "Game Result: Game 1 ended in 100 ms. Ai(1)-Heroic has won!",
    ])
    results = _parse_forge_verbose_output(stdout, "Heroic")
    assert len(results) == 1
    log = results[0].log
    assert log is not None
    assert len(log.player_pilot_notes) == 3
    assert len(log.opponent_pilot_notes) == 3
    assert any("Hoplite" in note for note in log.player_pilot_notes)
    assert any("Manamorphose" in note for note in log.opponent_pilot_notes)
    assert any("Ai(1)-Heroic" in note for note in log.player_pilot_notes)


def test_parse_pilot_hand_size_from_spell_lines() -> None:
    """Hand size in board stats comes from [hand:N] tags on pilot spell lines."""
    stdout = "\n".join([
        "Turn: Turn 4 (Ai(1)-Heroic)",
        "[Pilot] Ai(1)-Heroic: T4 spell: Temur Battle Rage [hand:5]",
        "[Pilot] Ai(1)-Heroic: T4 spell: Prey's Vengeance [hand:4]",
        "Turn: Turn 4 (Ai(2)-Ruby Storm)",
        "Game Result: Game 1 ended in 100 ms. Ai(1)-Heroic has won!",
    ])
    results = _parse_forge_verbose_output(stdout, "Heroic")
    assert len(results) == 1
    turns = results[0].log.turns if results[0].log else []
    player_turn = next(ev for ev in turns if ev.player == 0)
    assert player_turn.hand_size == 4


def test_parse_pilot_hand_cards_from_spell_lines() -> None:
    """Hand card names appear in turn stats from [cards:...] pilot tags."""
    stdout = "\n".join([
        "Turn: Turn 4 (Ai(1)-Heroic)",
        "[Pilot] Ai(1)-Heroic: T4 spell: Temur Battle Rage [hand:3] "
        "[cards:Monastery Swiftspear, Temur Battle Rage, Mutagenic Growth]",
        "Turn: Turn 4 (Ai(2)-Ruby Storm)",
        "Game Result: Game 1 ended in 100 ms. Ai(1)-Heroic has won!",
    ])
    results = _parse_forge_verbose_output(stdout, "Heroic")
    turns = results[0].log.turns if results[0].log else []
    player_turn = next(ev for ev in turns if ev.player == 0)
    assert player_turn.hand_size == 3
    assert "Monastery Swiftspear" in player_turn.board.hand_cards


def test_parse_pilot_mulligan_counts() -> None:
    """Mulligan stats come from pilot Keep/Mulligan lines, not hand size."""
    stdout = "\n".join([
        "[Pilot] Ai(1)-Heroic: mulligan: Mulligan — no turn-1 play",
        "[Pilot] Ai(1)-Heroic: mulligan: Keep — two lands and Hoplite",
        "[Pilot] Ai(2)-Ruby Storm: mulligan: Keep — reducer plus land",
        "Mulligan: Ai(1)-Heroic has kept a hand of 7 cards",
        "Mulligan: Ai(2)-Ruby Storm has kept a hand of 7 cards",
        "Game Result: Game 1 ended in 100 ms. Ai(1)-Heroic has won!",
    ])
    results = _parse_forge_verbose_output(stdout, "Heroic")
    assert len(results) == 1
    assert results[0].player_mulligan == 1
    assert results[0].opponent_mulligan == 0
