<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Symfony\Component\Validator\Constraint;

/**
 * Enforces the four-copy rule on deck main-deck and sideboard fields.
 *
 * Cards with "Basic Land" in their type line are unlimited.
 * Cards whose oracle text contains "A deck can have any number" are unlimited.
 * Cards whose oracle text contains "A deck can have up to N" allow N copies.
 * All other cards are limited to 4 copies across main deck and sideboard
 * combined (matching competitive Magic rules).
 *
 * @Constraint(
 *   id = "DeckCopyLimit",
 *   label = @Translation("Deck copy limit", context = "Validation"),
 *   type = "entity"
 * )
 */
class DeckCopyLimit extends Constraint {

  /**
   * Violation message for the four-copy rule.
   */
  public string $tooManyCopies = 'The deck contains %count copies of "%name", but the maximum allowed is %max.';

}
