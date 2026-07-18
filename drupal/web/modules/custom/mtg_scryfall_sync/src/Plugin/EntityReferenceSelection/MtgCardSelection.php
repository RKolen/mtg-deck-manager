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
    $usd = $card->hasField('field_price_usd') ? $card->get('field_price_usd')->value : NULL;
    $eur = $card->hasField('field_price_eur') ? $card->get('field_price_eur')->value : NULL;
    $usdFoil = $card->hasField('field_price_usd_foil') ? $card->get('field_price_usd_foil')->value : NULL;
    $eurFoil = $card->hasField('field_price_eur_foil') ? $card->get('field_price_eur_foil')->value : NULL;

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
    if ($usd !== NULL && $usd !== '') {
      $meta[] = '$' . number_format((float) $usd, 2);
    }
    if ($eur !== NULL && $eur !== '') {
      $meta[] = '€' . number_format((float) $eur, 2);
    }
    if ($usdFoil !== NULL && $usdFoil !== '') {
      $meta[] = 'foil $' . number_format((float) $usdFoil, 2);
    }
    if ($eurFoil !== NULL && $eurFoil !== '') {
      $meta[] = 'foil €' . number_format((float) $eurFoil, 2);
    }
    $hasNonFoil = ($usd !== NULL && $usd !== '') || ($eur !== NULL && $eur !== '');
    $hasFoil = ($usdFoil !== NULL && $usdFoil !== '') || ($eurFoil !== NULL && $eurFoil !== '');
    if (!$hasNonFoil && !$hasFoil) {
      $meta[] = 'no price';
    }

    if ($meta !== []) {
      $parts[] = '(' . implode(' · ', $meta) . ')';
    }

    return implode(' ', $parts);
  }

  /**
   * Highest available non-foil price for sorting.
   */
  private static function bestPrice(mixed $node): float {
    if (!$node instanceof NodeInterface || $node->bundle() !== 'mtg_card') {
      return 0.0;
    }
    if (!$node->hasField('field_price_usd') || !$node->hasField('field_price_eur')) {
      return 0.0;
    }
    $usd = (float) ($node->get('field_price_usd')->value ?? 0);
    $eur = (float) ($node->get('field_price_eur')->value ?? 0);
    return max($usd, $eur);
  }

}
