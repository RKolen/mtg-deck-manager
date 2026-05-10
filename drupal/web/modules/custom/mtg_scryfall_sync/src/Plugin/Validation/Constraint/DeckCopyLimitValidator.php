<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Drupal\Core\Entity\ContentEntityInterface;
use Symfony\Component\Validator\Constraint;
use Symfony\Component\Validator\ConstraintValidator;

/**
 * Validates the DeckCopyLimit constraint on a deck node.
 *
 * Reads card slots from field_deck_cards (paragraph--deck_card entities).
 * Rules enforced:
 *   1. Sideboard total must not exceed 15 cards.
 *   2. "Basic Land" in field_type_line          -> unlimited copies
 *   3. "A deck can have any number" in oracle   -> unlimited copies
 *   4. "A deck can have up to N" in oracle      -> N copies
 *   5. Default                                  -> 4 copies (main + sideboard combined).
 */
class DeckCopyLimitValidator extends ConstraintValidator {

  private const ANY_NUMBER_PATTERN = '/a deck can have any number/i';
  private const CUSTOM_LIMIT_PATTERN = '/a deck can have up to (\d+)/i';
  private const MAX_SIDEBOARD = 15;

  /**
   * {@inheritdoc}
   *
   * @param \Drupal\Core\Entity\ContentEntityInterface $entity
   *   The deck node being validated.
   * @param \Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint\DeckCopyLimit $constraint
   *   The constraint definition.
   */
  public function validate(mixed $entity, Constraint $constraint): void {
    if (!$entity instanceof ContentEntityInterface || $entity->bundle() !== 'deck') {
      return;
    }

    if (!$entity->hasField('field_deck_cards')) {
      return;
    }

    /** @var \Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint\DeckCopyLimit $constraint */

    // Aggregate quantity per card (main+sideboard combined) and total sideboard count.
    $cardQuantities = [];
    $sideboardTotal = 0;

    foreach ($entity->get('field_deck_cards') as $item) {
      /** @var \Drupal\paragraphs\Entity\Paragraph|null $para */
      $para = $item->entity;
      if ($para === NULL) {
        continue;
      }

      $qty = (int) ($para->hasField('field_quantity') ? $para->get('field_quantity')->value : 1);
      $isSideboard = (bool) ($para->hasField('field_is_sideboard') ? $para->get('field_is_sideboard')->value : FALSE);
      $cardRef = $para->hasField('field_card') ? $para->get('field_card') : NULL;
      if ($cardRef === NULL || $cardRef->isEmpty()) {
        continue;
      }

      $cardId = (int) $cardRef->target_id;
      $cardQuantities[$cardId] = ($cardQuantities[$cardId] ?? 0) + $qty;

      if ($isSideboard) {
        $sideboardTotal += $qty;
      }
    }

    // Rule 1: sideboard size.
    if ($sideboardTotal > self::MAX_SIDEBOARD) {
      $this->context->addViolation($constraint->sideboardTooLarge, [
        '%count' => $sideboardTotal,
        '%max' => self::MAX_SIDEBOARD,
      ]);
    }

    // Rules 2-5: per-card copy limits.
    if (empty($cardQuantities)) {
      return;
    }

    $cards = \Drupal::entityTypeManager()->getStorage('node')->loadMultiple(array_keys($cardQuantities));

    foreach ($cardQuantities as $cardId => $totalQty) {
      $card = $cards[$cardId] ?? NULL;
      if (!$card instanceof ContentEntityInterface) {
        continue;
      }
      $max = $this->maxAllowed($card);
      if ($totalQty > $max) {
        $this->context->addViolation($constraint->tooManyCopies, [
          '%count' => $totalQty,
          '%name' => $card->label(),
          '%max' => $max === PHP_INT_MAX ? 'unlimited' : $max,
        ]);
      }
    }
  }

  private function maxAllowed(ContentEntityInterface $card): int {
    $type_line = (string) $card->get('field_type_line')->value;
    $oracle = (string) $card->get('field_oracle_text')->value;

    if (preg_match('/\bBasic\b.*\bLand\b/i', $type_line)) {
      return PHP_INT_MAX;
    }
    if (preg_match(self::ANY_NUMBER_PATTERN, $oracle)) {
      return PHP_INT_MAX;
    }
    if (preg_match(self::CUSTOM_LIMIT_PATTERN, $oracle, $matches)) {
      return (int) $matches[1];
    }
    return 4;
  }

}
