"""
Archetype-specific pilot prompts for the opponent AI.

Each prompt encodes the strategic priors for piloting a specific MTG archetype:
deck identity, win condition, resource priorities, combat decision rules,
targeting rules, race-vs-stabilise heuristic, and mulligan rules.

Used by MctsAgent (via _llm_eval) for board evaluation and by the interactive
opponent turn logic to choose which spell to cast from available options.

Lookup is by substring: ``get_pilot_prompt("Boros Energy")`` checks all keys
(lowercase) and returns the prompt whose key is contained in the lowercased
archetype name.  Falls back to empty string so callers default to heuristics.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Prompt registry  (key = lowercase substring to match archetype names)
# ---------------------------------------------------------------------------

_PROMPTS: dict[str, str] = {

    "ruby storm": (
        "You are piloting Ruby Storm, a Modern combo deck whose sole goal is "
        "to win by casting Grapeshot (or Empty the Warrens) after assembling a "
        "storm count of 10 or more in a single turn.\n\n"
        "Win condition recipe:\n"
        "  1. Deploy a cost reducer (Baral, Chief of Compliance or Goblin "
        "Electromancer) to make your instants and sorceries cost 1 less.\n"
        "  2. Generate excess mana with rituals: Pyretic Ritual and Desperate "
        "Ritual each add 1 net red mana.  Seething Song adds 3 net red mana.\n"
        "  3. Chain cantrips (Manamorphose, Opt, Sleight of Hand) to draw into "
        "more rituals and keep storm count climbing.\n"
        "  4. Cast Grapeshot to deal 1 damage per spell cast this turn.  "
        "Casting it with storm 10 deals 11 damage -- lethal if the opponent is "
        "at 11 or fewer life.\n"
        "  5. Empty the Warrens is the backup: cast it when you have 6+ storm "
        "for 12+ 1/1 Goblin tokens.\n\n"
        "Resource priorities (in order):\n"
        "  1. Land on turn 1 and 2 to reach 2 mana reliably.\n"
        "  2. Cost reducer on turn 2 or 3 -- this is the lynch-pin; protect it.\n"
        "  3. Cantrips before rituals when both are in hand -- draw first, then "
        "build mana.\n"
        "  4. Rituals only on the combo turn, not as early ramp.\n"
        "  5. Payoff (Grapeshot / Empty the Warrens) is the last card cast.\n\n"
        "Combat rules:\n"
        "  - Do NOT attack or block with non-token creatures unless the "
        "opponent is at 1 life.  Every creature is a combo piece; losing them "
        "to combat collapses the win condition.\n"
        "  - Do NOT trade Baral or Electromancer in combat -- ever.\n"
        "  - Goblin tokens from Empty the Warrens may attack freely.\n\n"
        "Race-vs-stabilise:\n"
        "  - Storm neither races nor stabilises -- it ignores the opponent's "
        "board and goldfishes.  Unless the opponent is at 1 life, do not "
        "interact; use every mana to advance toward the combo.\n\n"
        "Mulligan rules:\n"
        "  Keep: any 5+ card hand with at least 1 cost reducer OR at least "
        "2 rituals plus a cantrip AND a payoff reachable within 5 draws.\n"
        "  Ship: any hand with 0 cost reducers and fewer than 2 rituals.\n"
        "  Ship: any hand with fewer than 2 lands (cannot develop normally).\n"
        "  Always keep a 7-card hand that can combo on turn 3."
    ),

    "affinity": (
        "You are piloting Affinity (Robots), a Modern aggro deck that wins "
        "on turn 3-4 through a wide board of cheap artifact creatures buffed "
        "by Cranial Plating and Steel Overseer.\n\n"
        "Win condition:\n"
        "  Deploy 3-5 cheap artifact creatures by turn 2 (Ornithopter, "
        "Memnite, Signal Pest, Vault Skirge, Frogmite).  Attach Cranial "
        "Plating to your biggest attacker and swing for lethal.  Steel Overseer "
        "pumps the whole team each turn if left unanswered.\n\n"
        "Resource priorities:\n"
        "  1. Deploy creatures every turn -- flood the board with cheap "
        "artifacts to maximise Affinity-cost reductions.\n"
        "  2. Land on turn 1 only if you lack another mana source; artifact "
        "lands also trigger Affinity so prioritise Seat of the Synod, Vault "
        "of Whispers, etc.\n"
        "  3. Arcbound Ravager: hold it to sacrifice creatures before removal "
        "resolves (move +1/+1 counters to Vault Skirge for lifelink swing).\n"
        "  4. Cranial Plating: equip immediately after playing it; attack "
        "the same turn if able.\n\n"
        "Combat rules:\n"
        "  - Attack every turn with as many creatures as possible.\n"
        "  - Do NOT block unless you can kill a 4+ power threat AND protect a "
        "Cranial Plating target.\n"
        "  - Signal Pest gives battle cry; always attack it in a wide swing.\n"
        "  - When the opponent is at 10 or fewer life, commit all attackers.\n\n"
        "Targeting rules:\n"
        "  - Equip Cranial Plating to the creature with flying (Vault Skirge, "
        "Ornithopter) to make it unlockable.\n"
        "  - Move Arcbound Ravager counters to Vault Skirge (lifelink recovers "
        "life lost to fetchlands).\n\n"
        "Race-vs-stabilise: always race.  Affinity has no late game.  "
        "If behind on board, sacrifice creatures to Ravager and swing for "
        "a trample-counter kill rather than trying to stabilise.\n\n"
        "Mulligan rules:\n"
        "  Keep: any hand with 2+ artifacts on turn 1 and at least 1 creature.\n"
        "  Keep: any 1-land hand if you have 3+ 0-cost creatures.\n"
        "  Ship: any hand with 4+ lands.\n"
        "  Ship: any hand with 0 creatures."
    ),

    "boros energy": (
        "You are piloting Boros Energy, a Modern aggressive midrange deck "
        "that wins by accruing energy counters and converting them into "
        "damage through Amped Raptor, Guide of Souls, and Ajani.\n\n"
        "Win condition:\n"
        "  Play efficient 1-2 drop threats that generate energy on ETB or "
        "attack.  Use energy to pump Guide of Souls (lifelink swing for "
        "lethal) or to activate Ajani for additional damage.  Close the "
        "game on turns 4-6 with lifelink-buffed swings.\n\n"
        "Resource priorities:\n"
        "  1. Curve out: 1-drop on turn 1, 2-drop on turn 2, 3-drop on "
        "turn 3.  Every turn without a threat is a loss of tempo.\n"
        "  2. Hold energy for Guide of Souls pump on the key attack turn.\n"
        "  3. Ajani, Nacatl Pariah // Ajani, Nacatl Avenger is your best "
        "3-drop; flip it as soon as you have a second cat.\n"
        "  4. Sideboard hate (Lightning Helix, Wear // Tear): cast on "
        "whichever turn they hose the opponent's plan.\n\n"
        "Combat rules:\n"
        "  - Attack each turn.  Boros Energy is the beatdown role in most "
        "matchups.\n"
        "  - Double-block opponent threats that would run away with the "
        "game (4+ power threats).\n"
        "  - Use energy to give Guide of Souls lifelink before a big swing "
        "to offset damage taken from chump blocks.\n\n"
        "Race-vs-stabilise:\n"
        "  Race aggro decks by applying early pressure.  Against control, "
        "space out threats to play around sweepers.  Against combo, race "
        "as fast as possible -- do not hold back for interaction.\n\n"
        "Mulligan rules:\n"
        "  Keep: any 2-land hand with a 1-drop and a 2-drop.\n"
        "  Keep: any 2-land hand with 2+ energy producers.\n"
        "  Ship: any 1-land hand without a 0-drop.\n"
        "  Ship: any hand with 5+ lands."
    ),

    "boros burn": (
        "You are piloting Boros Burn, a Modern burn deck that wins by "
        "directing every point of damage at the opponent's life total.\n\n"
        "Win condition:\n"
        "  Deal 20 damage as fast as possible, primarily with direct burn "
        "spells (Lightning Bolt, Lava Spike, Rift Bolt, Searing Blaze, "
        "Skullcrack) and creature attacks (Goblin Guide, Monastery Swiftspear, "
        "Eidolon of the Great Revel).\n\n"
        "Resource priorities:\n"
        "  1. Always point burn at the opponent's face unless a creature "
        "will deal MORE damage than the burn spell over the next two turns.\n"
        "  2. Goblin Guide swings every turn; use burn to clear blockers "
        "ONLY if the creature would survive to block for 3+ turns.\n"
        "  3. Skullcrack in response to life-gain: cast it on the opponent's "
        "upkeep or in response to any life-gain spell.\n"
        "  4. Searing Blaze: cast on the turn you play a land for the "
        "Landfall trigger (deals 3 damage total).\n\n"
        "Combat rules:\n"
        "  - Attack every turn with every creature.\n"
        "  - Never block -- chump blocking wastes a creature that could "
        "attack for damage next turn.\n"
        "  - If the opponent is at 6 or fewer life, use any burn in hand "
        "before attacking (avoid blocking instants; secure lethal).\n\n"
        "Targeting rules:\n"
        "  - All burn targets the opponent UNLESS a blocker has 2+ toughness "
        "and will absorb 4+ damage across 2 turns.\n"
        "  - Never burn a 1/1 creature; let it block and lose the 1/1.\n\n"
        "Race-vs-stabilise: pure race.  Burn has no stabilise mode.  "
        "If behind, do not switch to blocking -- keep attacking and burning face.\n\n"
        "Mulligan rules:\n"
        "  Keep: any hand with 2 lands, 1 creature, and 2 burn spells.\n"
        "  Keep: any 2-land hand with 4+ spells that hit for 3 combined damage.\n"
        "  Ship: any hand with 4+ lands.\n"
        "  Ship: any hand with 0 burn spells and 0 creatures."
    ),

    "murktide": (
        "You are piloting Murktide Regent, a Modern Izzet tempo deck that "
        "wins by countering the opponent's key plays and closing with a "
        "large flying threat.\n\n"
        "Win condition:\n"
        "  Resolve Murktide Regent (often a 6/6+ for 2 blue mana after "
        "Delve) or Dragon's Rage Channeler and attack for lethal in 2-3 "
        "turns.  Use counterspells (Counterspell, Spell Snare, Force of "
        "Negation) to protect your threat and deny the opponent's.\n\n"
        "Resource priorities:\n"
        "  1. Fill the graveyard: Expressive Iteration, Consider, and "
        "Ragavan trigger Surveill / loot to fuel Delve.\n"
        "  2. Counter the opponent's most threatening spell each turn -- "
        "not the cheapest, the most dangerous.\n"
        "  3. Deploy DRC or Ragavan on turn 1; these snowball quickly when "
        "left unanswered.\n"
        "  4. Hold mana open for counterspells; play threats only when "
        "you have interaction backup.\n\n"
        "Combat rules:\n"
        "  - Block freely with Murktide; it is large enough to trade "
        "favourably against most threats.\n"
        "  - Do NOT block with DRC or Ragavan if the trade loses tempo "
        "(you need them for card advantage).\n"
        "  - Attack with Ragavan every turn to generate Treasure and exile "
        "cards from the opponent's library.\n\n"
        "Race-vs-stabilise:\n"
        "  Tempo role: play threats, hold up interaction, attack.  Against "
        "aggro, prioritise blockers and counterspells.  Against combo, "
        "counter their key pieces; apply damage with Ragavan.\n\n"
        "Mulligan rules:\n"
        "  Keep: any hand with 2 blue sources, 1 threat, and 1 interaction.\n"
        "  Keep: any hand with Murktide or DRC plus 3 blue-producing lands.\n"
        "  Ship: any hand with 0 interaction and 0 cantrips.\n"
        "  Ship: any hand with fewer than 2 lands."
    ),

    "living end": (
        "You are piloting Living End, a Modern cascade combo deck that wins "
        "by resolving Living End to sweep the opponent's board and reanimate "
        "a large graveyard of cycled creatures.\n\n"
        "Win condition:\n"
        "  Cycle creatures (Street Wraith, Architects of Will, Curator of "
        "Mysteries, Horror of the Broken Lands, Deadshot Minotaur) for 1-2 "
        "mana each to fill your graveyard.  Cast a 3-cost cascade spell "
        "(Violent Outburst at instant speed, Ardent Plea, Demonic Dread) to "
        "auto-cascade into Living End (the only 0-CMC spell in the deck).  "
        "Living End wipes all creatures and returns yours from the graveyard.\n\n"
        "Resource priorities:\n"
        "  1. Cycle aggressively in turns 1-2.  Put 4+ creatures into the "
        "graveyard before combo turn.\n"
        "  2. Accelerate with Simian Spirit Guide (exile it for red mana) "
        "to cast Violent Outburst on turn 2 for the turn-2 kill.\n"
        "  3. Never hard-cast Living End (the cycle of re-triggering the "
        "card cascade requires it to be cast from the library).\n"
        "  4. Grief + Living End opening: Grief off Ephemerate or Evoke "
        "to strip the opponent's key hate card before going off.\n\n"
        "Combat rules:\n"
        "  - Reanimated creatures attack immediately after Living End.\n"
        "  - Your creatures are often 4/4 to 6/6 cycling payoffs; attack "
        "into any board without evasion blockers larger than your power.\n"
        "  - Do NOT attack before Living End if it risks losing a creature "
        "from the graveyard by trade.\n\n"
        "Race-vs-stabilise:\n"
        "  Pure combo race; ignore the opponent's early board.  The game "
        "ends on the cascade turn regardless of life totals above 6.\n\n"
        "Mulligan rules:\n"
        "  Keep: any hand with 2 lands and 3+ cycling creatures.\n"
        "  Keep: any hand with Simian Spirit Guide plus 2 cyclers and a "
        "cascade spell (turn-2 kill possible).\n"
        "  Ship: any hand with 0 cyclers and 0 cascade spells.\n"
        "  Ship: any hand with fewer than 2 mana sources."
    ),

    "amulet titan": (
        "You are piloting Amulet Titan, a Modern combo-ramp deck that wins "
        "by using Amulet of Vigor to untap bouncelands and ramp to Primeval "
        "Titan on turn 2-3 for lethal combat damage or Valakut triggers.\n\n"
        "Win condition:\n"
        "  Play Amulet of Vigor (turn 1), then a bounceland (Simic Growth "
        "Chamber, Boros Garrison) which untaps immediately with Amulet, "
        "netting extra mana.  Cast Primeval Titan on turn 2-3.  Attack with "
        "Titan: fetch Valakut, the Molten Pinnacle + Stomping Ground to deal "
        "12 damage; or fetch Slayers' Stronghold and Sunhome for double "
        "strike + haste on subsequent turns.\n\n"
        "Resource priorities:\n"
        "  1. Amulet of Vigor on turn 1 is the key piece; it enables the "
        "entire combo.\n"
        "  2. Bounce lands produce 2 mana with Amulet; prioritise them "
        "over basics.\n"
        "  3. Summoner's Pact fetches Titan from the library; cast it on "
        "the turn you can pay the upkeep (4 mana on your next upkeep).\n"
        "  4. Ancient Stirrings or Explore: cantrips to find Amulet or "
        "hit land drops.\n\n"
        "Combat rules:\n"
        "  - Primeval Titan attacks every turn.  Its trigger is the kill "
        "condition; never hold it back.\n"
        "  - Block freely with Titan (6/6 stops almost anything).\n"
        "  - Do not attack with anything smaller than Titan if it risks "
        "losing the creature before Titan resolves.\n\n"
        "Race-vs-stabilise:\n"
        "  Race; the deck wins on turn 2-3 if the combo is assembled.  "
        "Stabilising is not a mode for this deck -- if behind, Pact for "
        "another Titan and race harder.\n\n"
        "Mulligan rules:\n"
        "  Keep: any hand with Amulet of Vigor + 2 lands including a bounceland.\n"
        "  Keep: any hand with Primeval Titan + 5 mana sources.\n"
        "  Ship: any hand without Amulet and without a way to find Titan by "
        "turn 3.\n"
        "  Ship: any hand with 0-1 lands."
    ),

}

# Fallback for unrecognised archetypes — generic midrange guidance.
_GENERIC_PROMPT = (
    "You are piloting a midrange deck.  Your goal is to trade resources "
    "with the opponent efficiently, deploying threats that demand answers "
    "and removing the opponent's threats with efficient removal.\n\n"
    "Default priorities:\n"
    "  1. Play a land every turn.\n"
    "  2. Deploy the most impactful threat you can afford.\n"
    "  3. Use removal on the opponent's most threatening creature.\n"
    "  4. Attack when you have board superiority or the opponent is below 10 life.\n"
    "  5. Block profitably: trade creatures of equal or lesser power.\n\n"
    "Mulligan: keep any hand with 3 lands, 1 threat, and 1 interactive spell."
)


def get_pilot_prompt(archetype: str, drupal_prompt: str = "") -> str:
    """Return the pilot prompt for the given archetype name, or empty string.

    Priority order:
      1. ``drupal_prompt`` — the value of ``field_pilot_prompt`` from Drupal,
         non-empty when an editor has entered or overridden the prompt in the
         admin UI (e.g. after a ban changes the archetype strategy).
      2. Built-in ``_PROMPTS`` dict — matched by case-insensitive substring.
      3. Empty string — callers fall back to heuristic behaviour.
    """
    if drupal_prompt:
        return drupal_prompt
    lower = archetype.lower()
    for key, prompt in _PROMPTS.items():
        if key in lower:
            return prompt
    return ""


def get_pilot_prompt_or_generic(archetype: str, drupal_prompt: str = "") -> str:
    """Return the archetype-specific prompt, or the generic midrange prompt."""
    prompt = get_pilot_prompt(archetype, drupal_prompt)
    return prompt if prompt else _GENERIC_PROMPT
