<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Drupal\Core\Entity\ContentEntityInterface;
use Drupal\Core\Field\Plugin\Field\FieldType\EntityReferenceItem;
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
 *   7. Commander / Tiny Leaders / Brawl         -> hard main-deck size
 *      (Rulebreaker cards may exceed the cap)
 *   8. Default constructed                      -> 4 copies (main + sideboard)
 */
class DeckCopyLimitValidator extends ConstraintValidator {

  private const ANY_NUMBER_PATTERN = '/a deck can have any number/i';
  private const CUSTOM_LIMIT_PATTERN = '/a deck can have up to (\d+)/i';
  private const ONLY_ONE_PATTERN = '/a deck can have only one/i';
  private const RULEBREAKER_PATTERN = '/rulebreaker/i';
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

    // Aggregate quantity per card (main+sideboard combined for copy limits).
    $cardQuantities = [];
    $mainQuantities = [];

    foreach ($entity->get('field_deck_cards')->referencedEntities() as $para) {
      $qty = (int) ($para->hasField('field_quantity') ? $para->get('field_quantity')->value : 1);
      if (!$para->hasField('field_card') || $para->get('field_card')->isEmpty()) {
        continue;
      }
      $cardIds = $para->get('field_card')->getValue();
      $cardId = (int) ($cardIds[0]['target_id'] ?? 0);
      if ($cardId < 1) {
        continue;
      }
      $cardQuantities[$cardId] = ($cardQuantities[$cardId] ?? 0) + $qty;
      $is_sideboard = $para->hasField('field_is_sideboard')
        && (bool) $para->get('field_is_sideboard')->value;
      if (!$is_sideboard) {
        $mainQuantities[$cardId] = ($mainQuantities[$cardId] ?? 0) + $qty;
      }
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

    $this->validateMainDeckSize(
      $constraint,
      $normalizedFormat,
      $formatLabel,
      $mainQuantities,
      $cards,
    );
  }

  /**
   * Raw format label from the deck node.
   */
  private function formatLabel(ContentEntityInterface $deck): string {
    if ($deck->hasField('field_format_term') && !$deck->get('field_format_term')->isEmpty()) {
      $item = $deck->get('field_format_term')->first();
      if ($item instanceof EntityReferenceItem && $item->entity !== NULL) {
        return (string) $item->entity->label();
      }
    }
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

  /**
   * Whether the format is singleton (one copy of each card).
   */
  private function isSingletonFormat(string $normalized): bool {
    return in_array($normalized, [
      'edh',
      'commander',
      'predh',
      'pauper commander',
      'historic brawl',
      'gladiator',
      'canadian highlander',
      'canlander',
      'duel commander',
      'duel',
      'brawl',
      'standard brawl',
      'oathbreaker',
      'tiny leader',
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
    ], TRUE);
  }

  /**
   * Whether the format is Tiny Leaders or Tiny Leaders Reborn.
   */
  private function isTinyLeadersFormat(string $normalized): bool {
    return in_array($normalized, [
      'tiny leader',
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
    ], TRUE);
  }

  /**
   * Whether a card is legal for Tiny Leaders mana-value rules.
   */
  private function isLegalManaValue(ContentEntityInterface $card): bool {
    $type_line = (string) $card->get('field_type_line')->value;
    if (preg_match('/\bland\b/i', $type_line)) {
      return TRUE;
    }
    $cmc = $card->hasField('field_cmc') ? (float) $card->get('field_cmc')->value : 0.0;
    return $cmc <= self::TINY_LEADERS_MAX_MANA_VALUE;
  }

  /**
   * Maximum copies allowed for a card in the current format.
   */
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

  /**
   * Enforces a hard main-deck size for Commander-family formats.
   *
   * @param \Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint\DeckCopyLimit $constraint
   *   The constraint definition.
   * @param string $normalized
   *   Normalized format label.
   * @param string $format_label
   *   Raw format label for the violation message.
   * @param array<int, int> $main_quantities
   *   Main-deck quantity keyed by card nid.
   * @param array<int, \Drupal\Core\Entity\ContentEntityInterface|null> $cards
   *   Loaded card nodes keyed by nid.
   */
  private function validateMainDeckSize(
    DeckCopyLimit $constraint,
    string $normalized,
    string $format_label,
    array $main_quantities,
    array $cards,
  ): void {
    $max = $this->mainHardMax($normalized);
    if ($max === NULL) {
      return;
    }

    $main_total = 0;
    $non_rulebreaker = 0;
    foreach ($main_quantities as $card_id => $qty) {
      $main_total += $qty;
      $card = $cards[$card_id] ?? NULL;
      if ($card instanceof ContentEntityInterface && $this->hasRulebreaker($card)) {
        continue;
      }
      $non_rulebreaker += $qty;
    }

    if ($non_rulebreaker > $max) {
      $this->context->addViolation($constraint->tooManyCards, [
        '%count' => $main_total,
        '%format' => $format_label !== '' ? $format_label : 'this format',
        '%max' => $max,
      ]);
    }
  }

  /**
   * Hard main-deck maximum, or NULL when constructed (60+, no maximum).
   */
  private function mainHardMax(string $normalized): ?int {
    if ($this->isTinyLeadersFormat($normalized)) {
      return 49;
    }
    if (in_array($normalized, [
      'standard brawl',
      'oathbreaker',
    ], TRUE)) {
      return $this->usesCommanderCard($normalized) ? 59 : 60;
    }
    if (in_array($normalized, [
      'edh',
      'commander',
      'predh',
      'pauper commander',
      'historic brawl',
      'gladiator',
      'canadian highlander',
      'canlander',
      'duel commander',
      'duel',
      'brawl',
    ], TRUE)) {
      return $this->usesCommanderCard($normalized) ? 99 : 100;
    }
    return NULL;
  }

  /**
   * Whether the format uses a designated commander card.
   */
  private function usesCommanderCard(string $normalized): bool {
    return in_array($normalized, [
      'edh',
      'commander',
      'tiny leader',
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
      'duel commander',
      'pauper commander',
      'predh',
      'brawl',
      'standard brawl',
      'historic brawl',
      'oathbreaker',
    ], TRUE);
  }

  /**
   * Whether a card's oracle text includes Rulebreaker.
   */
  private function hasRulebreaker(ContentEntityInterface $card): bool {
    if (!$card->hasField('field_oracle_text')) {
      return FALSE;
    }
    $oracle = (string) $card->get('field_oracle_text')->value;
    return (bool) preg_match(self::RULEBREAKER_PATTERN, $oracle);
  }

}
