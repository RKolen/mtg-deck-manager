"""
Ability words (Landfall, Magecraft, Raid, …).

Ability words have no rules meaning alone; triggers register on ETB via
register_permanent_ability_words().
"""

from engine.abilities.keywords.ability_words.detect import (
    ALL_ABILITY_WORDS,
    has_ability_word,
    has_ability_word_card,
)
from engine.abilities.keywords.ability_words.register import (
    register_permanent_ability_words,
)

__all__ = [
    'ALL_ABILITY_WORDS',
    'has_ability_word',
    'has_ability_word_card',
    'register_permanent_ability_words',
]
