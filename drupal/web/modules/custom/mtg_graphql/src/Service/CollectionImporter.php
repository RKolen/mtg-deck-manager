<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;

/**
 * Imports collection rows onto exact printings.
 *
 * Each row is matched by Scryfall ID, then set code with collector number,
 * then set code with name, then name alone (cheapest regular printing).
 */
final class CollectionImporter {

  /**
   * Set codes skipped when only a name is given (promos, lists, Secret Lair).
   */
  private const SPECIAL_SETS = '/^(plst|sld|slc|slz|p[a-z0-9]{3}|30a|wc\d\d|mb2)$/';

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly Connection $database,
    private readonly CollectionEnsurer $collectionEnsurer,
  ) {}

  /**
   * Matches rows and, when applying, adds them to the collection.
   *
   * @param list<array<string, mixed>> $rows
   *   Rows with name, quantity, foil, scryfallId, setCode, collectorNumber,
   *   quantityTrade and binderLocation.
   * @param bool $apply
   *   FALSE only reports matches (dry run).
   *
   * @return list<array<string, mixed>>
   *   One result per row: row, status, matchedBy, card.
   */
  public function import(array $rows, bool $apply): array {
    $results = [];
    foreach (array_values($rows) as $index => $row) {
      [$card, $matchedBy] = $this->match($row);
      $quantity = max(0, (int) ($row['quantity'] ?? 1));
      if (!$card instanceof NodeInterface || $quantity < 1) {
        $results[] = [
          'row' => $index,
          'status' => $card instanceof NodeInterface ? 'skipped' : 'not_found',
          'matchedBy' => $matchedBy,
          'card' => $card,
        ];
        continue;
      }
      if ($apply) {
        $this->collectionEnsurer->addCopies($card, $quantity, !empty($row['foil']));
        $trade = max(0, (int) ($row['quantityTrade'] ?? 0));
        $location = isset($row['binderLocation']) ? (string) $row['binderLocation'] : NULL;
        if ($trade > 0 || ($location !== NULL && trim($location) !== '')) {
          $collectionRow = $this->collectionEnsurer->loadByCard($card);
          if ($collectionRow instanceof NodeInterface) {
            $current = (int) ($collectionRow->get('field_quantity_trade')->value ?? 0);
            $this->collectionEnsurer->setTrade($collectionRow, $current + $trade, $location);
          }
        }
      }
      $results[] = [
        'row' => $index,
        'status' => $apply ? 'added' : 'matched',
        'matchedBy' => $matchedBy,
        'card' => $card,
      ];
    }
    return $results;
  }

  /**
   * Finds the printing for one row.
   *
   * @param array<string, mixed> $row
   *   Import row.
   *
   * @return array{0: \Drupal\node\NodeInterface|null, 1: string}
   *   The printing (or NULL) and how it was matched.
   */
  private function match(array $row): array {
    $scryfallId = trim((string) ($row['scryfallId'] ?? ''));
    $setCode = strtolower(trim((string) ($row['setCode'] ?? '')));
    $number = ltrim(trim((string) ($row['collectorNumber'] ?? '')), '0');
    $name = trim((string) ($row['name'] ?? ''));

    if ($scryfallId !== '') {
      $card = $this->first(['field_scryfall_id' => $scryfallId]);
      if ($card) {
        return [$card, 'scryfall_id'];
      }
    }
    if ($setCode !== '' && $number !== '') {
      foreach ($this->candidates($name, $setCode) as $card) {
        if (ltrim((string) $card->get('field_collector_number')->value, '0') === $number) {
          return [$card, 'set_number'];
        }
      }
    }
    if ($name === '') {
      return [NULL, 'none'];
    }
    if ($setCode !== '') {
      $card = $this->cheapest($this->candidates($name, $setCode), FALSE);
      if ($card) {
        return [$card, 'set_name'];
      }
    }
    $card = $this->cheapest($this->candidates($name, ''), TRUE);
    return [$card, $card ? 'name' : 'none'];
  }

  /**
   * Printings matching a name and/or set code.
   *
   * @return \Drupal\node\NodeInterface[]
   *   Candidate mtg_card nodes.
   */
  private function candidates(string $name, string $setCode): array {
    $query = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'mtg_card');
    if ($name !== '') {
      $query->condition($query->orConditionGroup()
        ->condition('title', $name)
        ->condition('title', $this->database->escapeLike($name) . ' // %', 'LIKE'));
    }
    if ($setCode !== '') {
      $query->condition('field_set_code', $setCode);
    }
    if ($name === '' && $setCode === '') {
      return [];
    }
    $ids = $query->range(0, 500)->execute();
    return array_values(array_filter(
      $this->entityTypeManager->getStorage('node')->loadMultiple($ids),
      fn($n) => $n instanceof NodeInterface,
    ));
  }

  /**
   * Cheapest priced printing, preferring regular sets when asked.
   *
   * @param \Drupal\node\NodeInterface[] $cards
   *   Candidates.
   * @param bool $preferRegular
   *   Skip promo, list and Secret Lair printings when others exist.
   */
  private function cheapest(array $cards, bool $preferRegular): ?NodeInterface {
    if ($preferRegular) {
      $regular = array_filter($cards, fn(NodeInterface $c) => !preg_match(
        self::SPECIAL_SETS,
        (string) $c->get('field_set_code')->value,
      ));
      $cards = $regular !== [] ? $regular : $cards;
    }
    usort($cards, function (NodeInterface $a, NodeInterface $b): int {
      $pa = $a->get('field_price_eur')->value;
      $pb = $b->get('field_price_eur')->value;
      $pa = $pa === NULL ? PHP_FLOAT_MAX : (float) $pa;
      $pb = $pb === NULL ? PHP_FLOAT_MAX : (float) $pb;
      return $pa <=> $pb;
    });
    return $cards[0] ?? NULL;
  }

  /**
   * First mtg_card matching the given properties.
   *
   * @param array<string, string> $properties
   *   Entity properties.
   */
  private function first(array $properties): ?NodeInterface {
    $found = $this->entityTypeManager->getStorage('node')
      ->loadByProperties(['type' => 'mtg_card'] + $properties);
    $card = reset($found);
    return $card instanceof NodeInterface ? $card : NULL;
  }

}
