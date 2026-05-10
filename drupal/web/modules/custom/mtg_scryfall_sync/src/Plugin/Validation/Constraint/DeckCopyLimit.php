<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Symfony\Component\Validator\Constraint;

/**
 * Enforces MTG deck construction rules on the deck node.
 *
 * Reads card slots from field_deck_cards (paragraph--deck_card entities).
 * - Sideboard may not exceed 15 cards.
 * - Basic lands are unlimited.
 * - Cards with "a deck can have any number" in oracle are unlimited.
 * - Cards with "a deck can have up to N" in oracle allow N copies.
 * - All other cards are limited to 4 copies (main + sideboard combined).
 *
 * @Constraint(
 *   id = "DeckCopyLimit",
 *   label = @Translation("Deck copy limit", context = "Validation"),
 *   type = "entity"
 * )
 */
class DeckCopyLimit extends Constraint {

  public string $tooManyCopies = 'The deck contains %count copies of "%name", but the maximum allowed is %max.';

  public string $sideboardTooLarge = 'The sideboard contains %count cards, but the maximum is %max.';

}
