<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint;

use Drupal\Core\Entity\ContentEntityInterface;
use Symfony\Component\Validator\Constraint;
use Symfony\Component\Validator\ConstraintValidator;

/**
 * Validates the DeckCopyLimit constraint.
 *
 * Checks both field_main_cards and field_sideboard_cards on a deck node.
 * The allowed copy count per card is determined by:
 *   1. "Basic Land" in field_type_line          -> unlimited
 *   2. "A deck can have any number" in oracle   -> unlimited
 *   3. "A deck can have up to N" in oracle      -> N copies
 *   4. Default                                  -> 4 copies.
 */
class DeckCopyLimitValidator extends ConstraintValidator {

  /**
   * Regex: cards explicitly allowed in any quantity.
   */
  private const ANY_NUMBER_PATTERN = '/a deck can have any number/i';

  /**
   * Regex: cards with a custom numeric limit (e.g. Seven Dwarves -> 7).
   */
  private const CUSTOM_LIMIT_PATTERN = '/a deck can have up to (\d+)/i';

  /**
   * {@inheritdoc}
   *
   * @param \Drupal\Core\Entity\ContentEntityInterface $entity
   *   The deck node being validated.
   * @param \Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint\DeckCopyLimit $constraint
   *   The constraint definition.
   */
  public function validate(mixed $entity, Constraint $constraint): void {
    // Only applies to deck nodes.
    if (!$entity instanceof ContentEntityInterface || $entity->bundle() !== 'deck') {
      return;
    }

    /** @var \Drupal\mtg_scryfall_sync\Plugin\Validation\Constraint\DeckCopyLimit $constraint */

    // Collect all referenced card IDs from both fields.
    $all_refs = array_merge(
      $this->collectRefs($entity, 'field_main_cards'),
      $this->collectRefs($entity, 'field_sideboard_cards'),
    );

    if (empty($all_refs)) {
      return;
    }

    // Count occurrences per card node ID.
    $counts = array_count_values($all_refs);

    foreach ($counts as $card_id => $count) {
      $card = \Drupal::entityTypeManager()->getStorage('node')->load($card_id);
      if (!$card instanceof ContentEntityInterface) {
        continue;
      }

      $max = $this->maxAllowed($card);
      if ($count > $max) {
        $this->context->addViolation($constraint->tooManyCopies, [
          '%count' => $count,
          '%name' => $card->label(),
          '%max' => $max === PHP_INT_MAX ? 'unlimited' : $max,
        ]);
      }
    }
  }

  /**
   * Collects target entity IDs for a multi-value entity_reference field.
   *
   * @param \Drupal\Core\Entity\ContentEntityInterface $entity
   *   The deck node.
   * @param string $field_name
   *   The field to read from.
   *
   * @return int[]
   *   Flat list of referenced entity IDs (may contain duplicates).
   */
  private function collectRefs(ContentEntityInterface $entity, string $field_name): array {
    if (!$entity->hasField($field_name)) {
      return [];
    }
    $ids = [];
    foreach ($entity->get($field_name) as $item) {
      if (!empty($item->target_id)) {
        $ids[] = (int) $item->target_id;
      }
    }
    return $ids;
  }

  /**
   * Returns the maximum number of copies allowed for a given card node.
   *
   * @param \Drupal\Core\Entity\ContentEntityInterface $card
   *   The mtg_card node.
   *
   * @return int
   *   Maximum allowed copies. PHP_INT_MAX means unlimited.
   */
  private function maxAllowed(ContentEntityInterface $card): int {
    $type_line = (string) $card->get('field_type_line')->value;
    $oracle = (string) $card->get('field_oracle_text')->value;

    // Rule 1: Basic lands are unlimited.
    if (preg_match('/\bBasic\b.*\bLand\b/i', $type_line)) {
      return PHP_INT_MAX;
    }

    // Rule 2: "A deck can have any number of cards named X.".
    if (preg_match(self::ANY_NUMBER_PATTERN, $oracle)) {
      return PHP_INT_MAX;
    }

    // Rule 3: "A deck can have up to N cards named X.".
    if (preg_match(self::CUSTOM_LIMIT_PATTERN, $oracle, $matches)) {
      return (int) $matches[1];
    }

    // Rule 4: Standard four-copy rule.
    return 4;
  }

}
