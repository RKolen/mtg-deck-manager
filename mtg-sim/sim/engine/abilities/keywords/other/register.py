"""Register ability_other triggers when a permanent enters the battlefield."""

from __future__ import annotations

from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.other.cipher import (
    CipherEffect,
    has_cipher,
    is_cipher_instant_or_sorcery_cast,
)
from engine.abilities.keywords.other.evolve import (
    EvolveEffect,
    has_evolve,
    is_evolve_creature_enters,
)
from engine.abilities.keywords.other.exploit import (
    ExploitEffect,
    has_exploit,
    is_source_etb_exploit,
)
from engine.core.game_object import Permanent
from engine.rules.triggers import TriggerKey, TriggerRegistry, TriggerSpec


def trigger_registration_count(
    registry: TriggerRegistry,
    permanent: Permanent,
    *,
    trigger_key: TriggerKey | None = None,
) -> int:
    """Return how many triggers are registered for a permanent."""
    return registry.registration_count(permanent, trigger_key=trigger_key)


def register_permanent_other_keywords(
    permanent: Permanent,
    registry: TriggerRegistry,
) -> None:
    """Scan oracle text and register triggers for wired ability_other keywords."""
    oracle = permanent.oracle_text or ''
    if not oracle:
        return

    if has_evolve(permanent):
        registry.register(
            permanent,
            TriggerKey.ENTERS_BATTLEFIELD,
            TriggerSpec(is_evolve_creature_enters, effect=EvolveEffect()),
        )

    if has_exploit(permanent):
        clause = clause_after_ability_word(oracle, 'Exploit')
        registry.register(
            permanent,
            TriggerKey.ENTERS_BATTLEFIELD,
            TriggerSpec(
                is_source_etb_exploit,
                effect=ExploitEffect(clause) if clause else ExploitEffect(''),
            ),
        )

    if has_cipher(permanent):
        clause = clause_after_ability_word(oracle, 'Cipher')
        registry.register(
            permanent,
            TriggerKey.SPELL_CAST,
            TriggerSpec(
                is_cipher_instant_or_sorcery_cast,
                effect=CipherEffect(clause or ''),
            ),
        )
