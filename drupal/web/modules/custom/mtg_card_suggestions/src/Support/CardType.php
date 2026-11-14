<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Support;

/**
 * Card type checks shared by the suggestion services.
 */
final class CardType {

  /**
   * Whether a card is a land, judged by its front face.
   *
   * A spell // land card (modal double-faced card) is a spell that can be
   * played as a land; a Pathway (Land // Land) is a land.
   *
   * @param string $typeLine
   *   The card's full type line, faces separated by " // ".
   *
   * @return bool
   *   TRUE when the front face is a land.
   */
  public static function isLand(string $typeLine): bool {
    $front = explode(' // ', $typeLine)[0];
    return preg_match('/\bland\b/i', $front) === 1;
  }

}
