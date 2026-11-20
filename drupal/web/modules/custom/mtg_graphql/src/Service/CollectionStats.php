<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Database\Statement\FetchAs;
use Drupal\mtg_graphql\CollectionStatsCalculator;

/**
 * Reads the data for the collection statistics page in three flat queries.
 */
final class CollectionStats {

  public function __construct(
    private readonly Connection $database,
  ) {}

  /**
   * Statistics for the collection page.
   *
   * @param bool $eur
   *   TRUE to value in EUR, FALSE for USD.
   * @param float $usdToEur
   *   Euros per US dollar.
   * @param bool $includeTrade
   *   FALSE leaves trade copies out.
   * @param float $cutoff
   *   Per-copy price splitting valuable cards from bulk.
   *
   * @return array<string, mixed>
   *   Data keyed like the CollectionStats GraphQL type.
   */
  public function compute(bool $eur, float $usdToEur, bool $includeTrade, float $cutoff): array {
    return CollectionStatsCalculator::compute(
      $this->rows(),
      $this->deckNeeds(),
      $this->setSizes(),
      $eur,
      $usdToEur,
      $includeTrade,
      $cutoff,
    );
  }

  /**
   * Published collection rows with set, rarity and prices.
   *
   * @return array<int, array<string, mixed>>
   *   Rows for CollectionStatsCalculator::compute().
   */
  private function rows(): array {
    $query = $this->database->select('node_field_data', 'cc');
    $query->condition('cc.type', 'collection_card');
    $query->condition('cc.status', 1);
    $query->join('node__field_card', 'fc', 'fc.entity_id = cc.nid');
    $query->join('node_field_data', 'cd', 'cd.nid = fc.field_card_target_id');
    $query->addField('cd', 'nid', 'card');
    $query->addField('cd', 'title', 'title');
    $joins = [
      'regular' => ['cc', 'field_quantity_owned'],
      'foil' => ['cc', 'field_quantity_foil'],
      'trade' => ['cc', 'field_quantity_trade'],
      'setCode' => ['cd', 'field_set_code'],
      'setName' => ['cd', 'field_set_name'],
      'rarity' => ['cd', 'field_rarity'],
      'eur' => ['cd', 'field_price_eur'],
      'eurFoil' => ['cd', 'field_price_eur_foil'],
      'usd' => ['cd', 'field_price_usd'],
      'usdFoil' => ['cd', 'field_price_usd_foil'],
    ];
    foreach ($joins as $alias => [$base, $field]) {
      $table = 'j_' . $alias;
      $query->leftJoin("node__$field", $table, "$table.entity_id = $base.nid");
      $query->addField($table, $field . '_value', $alias);
    }
    return $query->execute()->fetchAll(FetchAs::Associative);
  }

  /**
   * Copies of each card name used per deck.
   *
   * Main deck and sideboard slots plus commander and partner; maybeboards
   * are not counted.
   *
   * @return array<int, array{deck: string, card: string, quantity: int}>
   *   One row per deck and card name.
   */
  private function deckNeeds(): array {
    $slots = $this->database->query(
      "SELECT d.title AS deck, c.title AS card, SUM(COALESCE(q.field_quantity_value, 1)) AS quantity
       FROM {node_field_data} d
       INNER JOIN {node__field_deck_cards} dc ON dc.entity_id = d.nid
       INNER JOIN {paragraph__field_card} pc ON pc.entity_id = dc.field_deck_cards_target_id
       INNER JOIN {node_field_data} c ON c.nid = pc.field_card_target_id
       LEFT JOIN {paragraph__field_quantity} q ON q.entity_id = dc.field_deck_cards_target_id
       WHERE d.type = 'deck'
       GROUP BY d.nid, d.title, c.title"
    )->fetchAll(FetchAs::Associative);
    $commanders = $this->database->query(
      "SELECT d.title AS deck, c.title AS card, 1 AS quantity
       FROM {node_field_data} d
       INNER JOIN {node__field_commander} cm ON cm.entity_id = d.nid
       INNER JOIN {node_field_data} c ON c.nid = cm.field_commander_target_id
       WHERE d.type = 'deck'
       UNION ALL
       SELECT d.title, c.title, 1
       FROM {node_field_data} d
       INNER JOIN {node__field_partner} p ON p.entity_id = d.nid
       INNER JOIN {node_field_data} c ON c.nid = p.field_partner_target_id
       WHERE d.type = 'deck'"
    )->fetchAll(FetchAs::Associative);
    return array_map(fn(array $r) => [
      'deck' => (string) $r['deck'],
      'card' => (string) $r['card'],
      'quantity' => (int) $r['quantity'],
    ], [...$slots, ...$commanders]);
  }

  /**
   * Printings per set code in the card database.
   *
   * @return array<string, int>
   *   Counts keyed by set code.
   */
  private function setSizes(): array {
    return array_map('intval', $this->database->query(
      "SELECT s.field_set_code_value, COUNT(*)
       FROM {node__field_set_code} s
       INNER JOIN {node_field_data} n ON n.nid = s.entity_id AND n.type = 'mtg_card'
       GROUP BY s.field_set_code_value"
    )->fetchAllKeyed());
  }

}
