<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Plugin\EntityReferenceSelection;

use Drupal\Component\Utility\Html;
use Drupal\Core\Entity\Attribute\EntityReferenceSelection;
use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\node\NodeInterface;
use Drupal\node\Plugin\EntityReferenceSelection\NodeSelection;

/**
 * Autocomplete selection that includes set code and price in the label.
 */
#[EntityReferenceSelection(
  id: 'mtg_card:node',
  label: new TranslatableMarkup('MTG card (set + price)'),
  entity_types: ['node'],
  group: 'mtg_card',
  weight: 0,
)]
final class MtgCardSelection extends NodeSelection {

  /**
   * {@inheritdoc}
   */
  public function getReferenceableEntities($match = NULL, $match_operator = 'CONTAINS', $limit = 0): array {
    $target_type = $this->getConfiguration()['target_type'];

    $query = $this->buildEntityQuery($match, $match_operator);
    if ($limit > 0) {
      $query->range(0, $limit);
    }

    $result = $query->execute();
    if ($result === []) {
      return [];
    }

    $options = [];
    $entities = $this->entityTypeManager->getStorage($target_type)->loadMultiple($result);

    // Prefer printings that have a market price so $0 promos sink.
    uasort($entities, static function ($a, $b): int {
      $pa = self::bestPrice($a);
      $pb = self::bestPrice($b);
      return $pb <=> $pa;
    });

    foreach ($entities as $entity_id => $entity) {
      if (!$entity instanceof NodeInterface || $entity->bundle() !== 'mtg_card') {
        continue;
      }
      $options[$entity->bundle()][$entity_id] = Html::escape(self::formatLabel($entity));
    }

    return $options;
  }

  /**
   * Builds a readable autocomplete label with set and price.
   *
   * Used for both dropdown matches and the filled-in widget value.
   */
  public static function formatLabel(NodeInterface $card): string {
    $name = $card->label() ?? 'Unknown';
    $set = $card->hasField('field_set_code')
      ? trim((string) ($card->get('field_set_code')->value ?? ''))
      : '';
    $setName = $card->hasField('field_set_name')
      ? trim((string) ($card->get('field_set_name')->value ?? ''))
      : '';
    $cn = $card->hasField('field_collector_number')
      ? trim((string) ($card->get('field_collector_number')->value ?? ''))
      : '';
    $parts = [$name];
    $meta = [];
    if ($set !== '') {
      $setLabel = strtoupper($set);
      if ($setName !== '') {
        $setLabel .= ' ' . $setName;
      }
      if ($cn !== '') {
        $setLabel .= ' #' . $cn;
      }
      $meta[] = $setLabel;
    }
    elseif ($setName !== '') {
      $meta[] = $setName . ($cn !== '' ? ' #' . $cn : '');
    }
    // "~" marks a price converted from USD because there is no EUR one.
    [$eur, $eurEstimated] = self::eurPrice($card, FALSE);
    [$eurFoil, $foilEstimated] = self::eurPrice($card, TRUE);
    if ($eur !== NULL) {
      $meta[] = ($eurEstimated ? '~' : '') . '€' . number_format($eur, 2);
    }
    if ($eurFoil !== NULL) {
      $meta[] = 'foil ' . ($foilEstimated ? '~' : '') . '€' . number_format($eurFoil, 2);
    }
    if ($eur === NULL && $eurFoil === NULL) {
      $meta[] = 'no price';
    }

    if ($meta !== []) {
      $parts[] = '(' . implode(' · ', $meta) . ')';
    }

    return implode(' ', $parts);
  }

  /**
   * Non-foil EUR price for sorting, 0 when there is none.
   */
  private static function bestPrice(mixed $node): float {
    if (!$node instanceof NodeInterface || $node->bundle() !== 'mtg_card') {
      return 0.0;
    }
    return self::eurPrice($node, FALSE)[0] ?? 0.0;
  }

  /**
   * EUR price of one finish, converted from USD when no EUR price exists.
   *
   * @param \Drupal\node\NodeInterface $card
   *   The mtg_card printing.
   * @param bool $foil
   *   TRUE for the foil finish.
   *
   * @return array{0: float|null, 1: bool}
   *   The price (NULL when unpriced) and whether it was converted from USD.
   */
  private static function eurPrice(NodeInterface $card, bool $foil): array {
    $suffix = $foil ? '_foil' : '';
    $eur = $card->hasField("field_price_eur$suffix") ? (float) ($card->get("field_price_eur$suffix")->value ?? 0) : 0.0;
    if ($eur > 0) {
      return [$eur, FALSE];
    }
    $usd = $card->hasField("field_price_usd$suffix") ? (float) ($card->get("field_price_usd$suffix")->value ?? 0) : 0.0;
    if ($usd > 0) {
      return [\Drupal::service('mtg_scryfall_sync.exchange_rate')->convert($usd, TRUE), TRUE];
    }
    return [NULL, FALSE];
  }

}
