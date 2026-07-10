"""Integration tests for Phase G scripted spell resolution in the game loop."""

import json

from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS
from engine.cards.deck_script_store import (
    DeckMatchupScripts,
    prepare_game_card_scripts,
    sync_deck_scripts,
)
from engine.core.game_object import CardObject
from engine.game import create_game
from engine.game.helpers import HandCastContext, card_to_client
from tests.conftest import (
    cast_announce_options,
    make_creature,
    make_deck,
    make_instant,
    make_land,
    put_lands_on_battlefield,
)


def test_lightning_bolt_script_resolves_in_game_loop():
    """Built-in Lightning Bolt script deals damage instead of regex burn."""
    bolt = make_instant(
        "Lightning Bolt",
        mana_cost="{R}",
        oracle="Lightning Bolt deals 3 damage to any target.",
    )
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        card_scripts=dict(BUILTIN_CARD_SCRIPTS),
    )
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=bolt),
    ]
    data = game.action_cast(0, target_player=1)
    assert "error" not in data
    assert data["opponentLife"] == 17
    assert "Lightning Bolt: dealt 3" in " ".join(
        entry.detail for entry in game.state.log if entry.action == "resolve"
    )


def test_scripted_destroy_uses_card_effect_not_regex_removal():
    """Terminate script destroys a targeted creature on resolve."""
    terminate = make_instant(
        "Terminate",
        mana_cost="{B}{R}",
        oracle="Destroy target creature. It can't be regenerated.",
    )
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        card_scripts=dict(BUILTIN_CARD_SCRIPTS),
    )
    game.action_keep()
    victim = make_creature("Target", 4, 4)
    victim_perm = game.state.zones.enter_battlefield(
        CardObject(controller_idx=1, owner_idx=1, card_info=victim),
        1,
        "test_setup",
    )
    put_lands_on_battlefield(game, 1, land_info=make_land("Swamp", "B"))
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=terminate),
    ]
    data = game.action_cast(0, target_uid=str(victim_perm.obj_id))
    assert "error" not in data
    assert victim_perm not in game.state.zones.battlefield


def test_runtime_deck_sync_seeds_builtin_without_persisting_deck_title(
    tmp_path,
    monkeypatch,
):
    """Runtime cache sync uses source_id only; titles are not written to disk."""
    monkeypatch.setenv("DECK_SCRIPT_CACHE_DIR", str(tmp_path))
    bolt = make_instant("Lightning Bolt", oracle="Lightning Bolt deals 3 damage.")
    sync_deck_scripts("nid:7", [bolt], title="Private Deck Name")
    manifest_path = tmp_path / "player" / "7.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_id"] == "nid:7"
    assert "title" not in manifest
    assert "Lightning Bolt" in manifest["cards"]


def test_prepare_game_scripts_merges_caches_by_source_id_only(tmp_path, monkeypatch):
    """Player and meta caches merge by source_id; filenames use nid/slug only."""
    monkeypatch.setenv("DECK_SCRIPT_CACHE_DIR", str(tmp_path))
    bolt = make_instant("Lightning Bolt", oracle="Lightning Bolt deals 3 damage.")
    doom = make_instant("Doom Blade", oracle="Destroy target creature.")
    merged = prepare_game_card_scripts(
        DeckMatchupScripts(
            player_deck_nid=9,
            player_cards=[bolt],
            player_title="",
            meta_format="Modern",
            meta_archetype="Synthetic",
            opponent_cards=[doom],
        ),
    )
    assert "Lightning Bolt" in merged
    assert "Doom Blade" in merged
    assert (tmp_path / "player" / "9.json").exists()
    assert (tmp_path / "meta" / "modern" / "synthetic.json").exists()
    player_manifest = json.loads((tmp_path / "player" / "9.json").read_text(encoding="utf-8"))
    assert "title" not in player_manifest


def test_molten_collapse_modal_damage_mode_in_game_loop():
    """Scripted Modal respects modal_mode_index when the spell resolves."""
    collapse = make_instant(
        "Molten Collapse",
        mana_cost="{B}{R}",
        oracle=(
            "Choose one —\n"
            "• Destroy target creature or planeswalker.\n"
            "• Molten Collapse deals 3 damage to any target."
        ),
    )
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        card_scripts=dict(BUILTIN_CARD_SCRIPTS),
    )
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Swamp", "B"))
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=collapse),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(modal_mode_index=1),
    )
    assert "error" not in data
    assert data["opponentLife"] == 17


def test_collective_brutality_modal_drain_mode_in_game_loop():
    """Scripted Collective Brutality drain mode drains life on resolve."""
    brutality = make_instant(
        "Collective Brutality",
        mana_cost="{1}{B}{B}",
        oracle=(
            "Choose one —\n"
            "• Target opponent reveals their hand. You choose an instant or "
            "sorcery card from it. That player discards that card.\n"
            "• Target creature gets -2/-2 until end of turn.\n"
            "• Target opponent loses 2 life and you gain 2 life."
        ),
    )
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        card_scripts=dict(BUILTIN_CARD_SCRIPTS),
    )
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Swamp", "B"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=brutality),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(modal_mode_index=2),
    )
    assert "error" not in data
    assert data["opponentLife"] == 18
    assert data["playerLife"] == 22


def test_card_to_client_exposes_script_and_modal_flags():
    """Hand serialisation advertises scripted spells and modal mode counts."""
    collapse = make_instant(
        "Molten Collapse",
        oracle=(
            "Choose one —\n"
            "• Destroy target creature or planeswalker.\n"
            "• Molten Collapse deals 3 damage to any target."
        ),
    )
    bolt = make_instant("Lightning Bolt", oracle="Lightning Bolt deals 3 damage.")
    game = create_game(
        make_deck(lands=20),
        make_deck(lands=20),
        card_scripts=dict(BUILTIN_CARD_SCRIPTS),
    )
    ctx = HandCastContext(game=game.state)
    modal_data = card_to_client(0, collapse, 10, ctx)
    bolt_data = card_to_client(1, bolt, 10, ctx)
    assert modal_data["hasScript"] is True
    assert modal_data["hasScriptedModal"] is True
    assert modal_data["scriptedModalModes"] == 2
    assert bolt_data["hasScript"] is True
    assert bolt_data["hasScriptedModal"] is False
    assert bolt_data["scriptedModalModes"] == 0


def test_oracle_infer_sync_writes_modal_script_at_runtime(tmp_path, monkeypatch):
    """Unknown modal spells infer scripts into the gitignored runtime cache."""
    monkeypatch.setenv("DECK_SCRIPT_CACHE_DIR", str(tmp_path))
    charm = make_instant(
        "Custom Charm",
        oracle=(
            "Choose one —\n"
            "• Destroy target creature.\n"
            "• Custom Charm deals 2 damage to any target."
        ),
    )
    scripts = sync_deck_scripts("nid:11", [charm])
    assert "Custom Charm" in scripts
    manifest = json.loads((tmp_path / "player" / "11.json").read_text(encoding="utf-8"))
    assert manifest["card_sources"]["Custom Charm"] == "inferred"
