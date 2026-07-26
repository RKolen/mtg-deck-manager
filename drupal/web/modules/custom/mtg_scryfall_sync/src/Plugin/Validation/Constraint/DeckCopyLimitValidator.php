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
 *   1. "Basic Land" in field_type_line          -> unlimited copies
 *   2. "A deck can have any number" in oracle   -> unlimited copies
 *   3. "A deck can have up to N" in oracle      -> N copies
 *   4. "A deck can have only one" in oracle     -> 1 copy
 *   5. Commander / EDH / Tiny Leaders / TLR     -> 1 copy (singleton)
 *   6. Tiny Leaders / TLR nonlands              -> mana value <= 3
 *   7. Default constructed                      -> 4 copies (main + sideboard)
 *
 * Deck / sideboard total sizes are intentionally not hard-blocked so oversized
 * lists and casual wishboards remain editable.
 */
class DeckCopyLimitValidator extends ConstraintValidator {

  private const ANY_NUMBER_PATTERN = '/a deck can have any number/i';
  private const CUSTOM_LIMIT_PATTERN = '/a deck can have up to (\d+)/i';
  private const ONLY_ONE_PATTERN = '/a deck can have only one/i';
  private const TINY_LEADERS_MAX_MANA_VALUE = 3;

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

    // Aggregate quantity per card (main+sideboard combined).
    $cardQuantities = [];

    foreach ($entity->get('field_deck_cards') as $item) {
      /** @var \Drupal\paragraphs\Entity\Paragraph|null $para */
      $para = $item->entity;
      if ($para === NULL) {
        continue;
      }

      $qty = (int) ($para->hasField('field_quantity') ? $para->get('field_quantity')->value : 1);
      $cardRef = $para->hasField('field_card') ? $para->get('field_card') : NULL;
      if ($cardRef === NULL || $cardRef->isEmpty()) {
        continue;
      }

      $cardId = (int) $cardRef->target_id;
      $cardQuantities[$cardId] = ($cardQuantities[$cardId] ?? 0) + $qty;
    }

    if ($cardQuantities === []) {
      return;
    }

    $formatLabel = $this->formatLabel($entity);
    $normalizedFormat = $this->normalizeFormat($formatLabel);
    $defaultMax = $this->isSingletonFormat($normalizedFormat) ? 1 : 4;
    $enforceMaxMv = $this->isTinyLeadersFormat($normalizedFormat);
    $cards = \Drupal::entityTypeManager()->getStorage('node')->loadMultiple(array_keys($cardQuantities));

    foreach ($cardQuantities as $cardId => $totalQty) {
      $card = $cards[$cardId] ?? NULL;
      if (!$card instanceof ContentEntityInterface) {
        continue;
      }

      $max = $this->maxAllowed($card, $defaultMax);
      if ($totalQty > $max) {
        $this->context->addViolation($constraint->tooManyCopies, [
          '%count' => $totalQty,
          '%name' => $card->label(),
          '%max' => $max === PHP_INT_MAX ? 'unlimited' : $max,
        ]);
      }

      if ($enforceMaxMv && !$this->isLegalManaValue($card)) {
        $cmc = $card->hasField('field_cmc') ? (float) $card->get('field_cmc')->value : 0.0;
        $this->context->addViolation($constraint->manaValueTooHigh, [
          '%name' => $card->label(),
          '%cmc' => $cmc,
          '%format' => $formatLabel !== '' ? $formatLabel : 'Tiny Leaders',
          '%max' => self::TINY_LEADERS_MAX_MANA_VALUE,
        ]);
      }
    }
  }

  /**
   * Raw format label from the deck node.
   */
  private function formatLabel(ContentEntityInterface $deck): string {
    if ($deck->hasField('field_format') && !$deck->get('field_format')->isEmpty()) {
      return (string) $deck->get('field_format')->value;
    }
    return '';
  }

  /**
   * Normalize a format label for comparisons.
   */
  private function normalizeFormat(string $format): string {
    $normalized = strtolower(trim(preg_replace('/[:\-]+/', ' ', $format) ?? $format));
    return preg_replace('/\s+/', ' ', $normalized) ?? $normalized;
  }

  private function isSingletonFormat(string $normalized): bool {
    return in_array($normalized, [
      'edh',
      'commander',
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
    ], TRUE);
  }

  private function isTinyLeadersFormat(string $normalized): bool {
    return in_array($normalized, [
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
    ], TRUE);
  }

  private function isLegalManaValue(ContentEntityInterface $card): bool {
    $type_line = (string) $card->get('field_type_line')->value;
    if (preg_match('/\bland\b/i', $type_line)) {
      return TRUE;
    }
    $cmc = $card->hasField('field_cmc') ? (float) $card->get('field_cmc')->value : 0.0;
    return $cmc <= self::TINY_LEADERS_MAX_MANA_VALUE;
  }

  private function maxAllowed(ContentEntityInterface $card, int $defaultMax): int {
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
    if (preg_match(self::ONLY_ONE_PATTERN, $oracle)) {
      return 1;
    }
    return $defaultMax;
  }

}
