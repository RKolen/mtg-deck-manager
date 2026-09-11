<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Symfony\Component\Validator\Constraint;

/**
 * Enforces MTG per-card copy limits on the deck node.
 *
 * Reads card slots from field_deck_cards (paragraph--deck_card entities).
 * - Basic lands are unlimited.
 * - Cards with "a deck can have any number" in oracle are unlimited.
 * - Cards with "a deck can have up to N" in oracle allow N copies.
 * - Cards with "a deck can have only one" in oracle allow 1 copy.
 * - Singleton formats (Commander, Brawl, Tiny Leaders, and similar)
 *   default to 1 copy.
 * - Tiny Leaders / TLR nonland cards must have mana value 3 or less.
 * - Commander / Tiny Leaders / Brawl main-deck size is a hard maximum
 *   (99 / 49 / 59 plus commander). Cards with "rulebreaker" in oracle
 *   may exceed that maximum.
 * - All other constructed decks default to 4 copies (main + sideboard),
 *   counted by oracle name across printings.
 * - Restricted cards (Scryfall) are limited to 1 copy.
 * - Constructed main-deck and sideboard totals stay soft (60+ / 15).
 *
 * @Constraint(
 *   id = "DeckCopyLimit",
 *   label = @Translation("Deck copy limit", context = "Validation"),
 *   type = "entity"
 * )
 */
class DeckCopyLimit extends Constraint {

  /**
   * Violation when a card exceeds the format copy limit.
   */
  public string $tooManyCopies = 'The deck contains %count copies of "%name", but the maximum allowed is %max.';

  /**
   * Violation when a Tiny Leaders nonland exceeds mana value 3.
   */
  public string $manaValueTooHigh = '"%name" has mana value %cmc, but %format allows a maximum of %max for nonland cards.';

  /**
   * Violation when a hard-cap format exceeds its main-deck size.
   */
  public string $tooManyCards = 'The main deck contains %count cards, but %format allows a maximum of %max (except cards with Rulebreaker).';

}
