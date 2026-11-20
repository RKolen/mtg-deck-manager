<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Database\Statement\FetchAs;
use Drupal\mtg_graphql\CollectionStatsCalculator;
use Drupal\mtg_graphql\StatsDetailCalculator;

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
   * @return array<int, array{deck: string, nid?: int, card: string, quantity: int}>
   *   One row per deck and card name.
   */
  private function deckNeeds(): array {
    $slots = $this->database->query(
      "SELECT d.nid, d.title AS deck, c.title AS card, SUM(COALESCE(q.field_quantity_value, 1)) AS quantity
       FROM {node_field_data} d
       INNER JOIN {node__field_deck_cards} dc ON dc.entity_id = d.nid
       INNER JOIN {paragraph__field_card} pc ON pc.entity_id = dc.field_deck_cards_target_id
       INNER JOIN {node_field_data} c ON c.nid = pc.field_card_target_id
       LEFT JOIN {paragraph__field_quantity} q ON q.entity_id = dc.field_deck_cards_target_id
       WHERE d.type = 'deck'
       GROUP BY d.nid, d.title, c.title"
    )->fetchAll(FetchAs::Associative);
    $commanders = $this->database->query(
      "SELECT d.nid, d.title AS deck, c.title AS card, 1 AS quantity
       FROM {node_field_data} d
       INNER JOIN {node__field_commander} cm ON cm.entity_id = d.nid
       INNER JOIN {node_field_data} c ON c.nid = cm.field_commander_target_id
       WHERE d.type = 'deck'
       UNION ALL
       SELECT d.nid, d.title, c.title, 1
       FROM {node_field_data} d
       INNER JOIN {node__field_partner} p ON p.entity_id = d.nid
       INNER JOIN {node_field_data} c ON c.nid = p.field_partner_target_id
       WHERE d.type = 'deck'"
    )->fetchAll(FetchAs::Associative);
    return array_map(fn(array $r) => [
      'deck' => (string) $r['deck'],
      'nid' => (int) $r['nid'],
      'card' => (string) $r['card'],
      'quantity' => (int) $r['quantity'],
    ], [...$slots, ...$commanders]);
  }

  /**
   * Statistics for one deck, or NULL when the node is not a deck.
   *
   * @param int $nid
   *   Deck node ID.
   * @param bool $eur
   *   TRUE to value in EUR.
   * @param float $usdToEur
   *   Euros per US dollar.
   *
   * @return array<string, mixed>|null
   *   Data keyed like the DeckStats GraphQL type.
   */
  public function deck(int $nid, bool $eur, float $usdToEur): ?array {
    $deck = $this->database->query(
      "SELECT nid, title FROM {node_field_data} WHERE nid = :nid AND type = 'deck'",
      [':nid' => $nid],
    )->fetchAssoc();
    if (!$deck) {
      return NULL;
    }
    $slots = $this->deckSlots($nid);
    $names = array_values(array_unique(array_column($slots, 'title')));
    $owned = [];
    $cheapest = [];
    $otherDecks = [];
    if ($names) {
      $owned = array_map('intval', $this->database->query(
        "SELECT c.title, SUM(COALESCE(o.field_quantity_owned_value, 0) + COALESCE(f.field_quantity_foil_value, 0))
         FROM {node_field_data} cc
         INNER JOIN {node__field_card} fc ON fc.entity_id = cc.nid
         INNER JOIN {node_field_data} c ON c.nid = fc.field_card_target_id
         LEFT JOIN {node__field_quantity_owned} o ON o.entity_id = cc.nid
         LEFT JOIN {node__field_quantity_foil} f ON f.entity_id = cc.nid
         WHERE cc.type = 'collection_card' AND cc.status = 1 AND c.title IN (:names[])
         GROUP BY c.title",
        [':names[]' => $names],
      )->fetchAllKeyed());
      foreach ($this->database->query(
        "SELECT c.title,
           MIN(NULLIF(e.field_price_eur_value, 0)) AS eur, MIN(NULLIF(ef.field_price_eur_foil_value, 0)) AS eurFoil,
           MIN(NULLIF(u.field_price_usd_value, 0)) AS usd, MIN(NULLIF(uf.field_price_usd_foil_value, 0)) AS usdFoil
         FROM {node_field_data} c
         LEFT JOIN {node__field_price_eur} e ON e.entity_id = c.nid
         LEFT JOIN {node__field_price_eur_foil} ef ON ef.entity_id = c.nid
         LEFT JOIN {node__field_price_usd} u ON u.entity_id = c.nid
         LEFT JOIN {node__field_price_usd_foil} uf ON uf.entity_id = c.nid
         WHERE c.type = 'mtg_card' AND c.title IN (:names[])
         GROUP BY c.title",
        [':names[]' => $names],
      )->fetchAll(FetchAs::Associative) as $row) {
        $cheapest[$row['title']] = $row;
      }
      foreach ($this->deckNeeds() as $need) {
        if ($need['nid'] !== $nid && in_array($need['card'], $names, TRUE)) {
          $otherDecks[$need['card']][$need['nid']] = TRUE;
        }
      }
      $otherDecks = array_map('count', $otherDecks);
    }
    return [
      'nid' => (int) $deck['nid'],
      'title' => (string) $deck['title'],
      'currency' => $eur ? 'EUR' : 'USD',
    ] + StatsDetailCalculator::deck($slots, $owned, $cheapest, $otherDecks, $eur, $usdToEur);
  }

  /**
   * Commander, partner, main deck and sideboard slots of a deck.
   *
   * @return array<int, array<string, mixed>>
   *   Slot rows for StatsDetailCalculator::deck().
   */
  private function deckSlots(int $nid): array {
    $cardFields = "c.title, n.uuid AS cardId, s.field_set_code_value AS setCode, sn.field_set_name_value AS setName,
      cn.field_collector_number_value AS collectorNumber, r.field_rarity_value AS rarity,
      e.field_price_eur_value AS eur, ef.field_price_eur_foil_value AS eurFoil,
      u.field_price_usd_value AS usd, uf.field_price_usd_foil_value AS usdFoil";
    $cardJoins = "INNER JOIN {node} n ON n.nid = c.nid
      LEFT JOIN {node__field_set_code} s ON s.entity_id = c.nid
      LEFT JOIN {node__field_set_name} sn ON sn.entity_id = c.nid
      LEFT JOIN {node__field_collector_number} cn ON cn.entity_id = c.nid
      LEFT JOIN {node__field_rarity} r ON r.entity_id = c.nid
      LEFT JOIN {node__field_price_eur} e ON e.entity_id = c.nid
      LEFT JOIN {node__field_price_eur_foil} ef ON ef.entity_id = c.nid
      LEFT JOIN {node__field_price_usd} u ON u.entity_id = c.nid
      LEFT JOIN {node__field_price_usd_foil} uf ON uf.entity_id = c.nid";
    $commanders = $this->database->query(
      "SELECT $cardFields, 'commander' AS board, 1 AS quantity, COALESCE(cf.field_commander_foil_value, 0) AS foil, 0 AS sort
       FROM {node__field_commander} cm
       INNER JOIN {node_field_data} c ON c.nid = cm.field_commander_target_id
       $cardJoins
       LEFT JOIN {node__field_commander_foil} cf ON cf.entity_id = cm.entity_id
       WHERE cm.entity_id = :nid
       UNION ALL
       SELECT $cardFields, 'commander', 1, COALESCE(pf.field_partner_foil_value, 0), 1
       FROM {node__field_partner} p
       INNER JOIN {node_field_data} c ON c.nid = p.field_partner_target_id
       $cardJoins
       LEFT JOIN {node__field_partner_foil} pf ON pf.entity_id = p.entity_id
       WHERE p.entity_id = :nid",
      [':nid' => $nid],
    )->fetchAll(FetchAs::Associative);
    $slots = $this->database->query(
      "SELECT $cardFields, CASE WHEN COALESCE(sb.field_is_sideboard_value, 0) = 1 THEN 'side' ELSE 'main' END AS board,
         COALESCE(q.field_quantity_value, 1) AS quantity, COALESCE(fo.field_is_foil_value, 0) AS foil, dc.delta AS sort
       FROM {node__field_deck_cards} dc
       INNER JOIN {paragraph__field_card} pc ON pc.entity_id = dc.field_deck_cards_target_id
       INNER JOIN {node_field_data} c ON c.nid = pc.field_card_target_id
       $cardJoins
       LEFT JOIN {paragraph__field_quantity} q ON q.entity_id = dc.field_deck_cards_target_id
       LEFT JOIN {paragraph__field_is_sideboard} sb ON sb.entity_id = dc.field_deck_cards_target_id
       LEFT JOIN {paragraph__field_is_foil} fo ON fo.entity_id = dc.field_deck_cards_target_id
       WHERE dc.entity_id = :nid
       ORDER BY board, c.title",
      [':nid' => $nid],
    )->fetchAll(FetchAs::Associative);
    return array_map(function (array $r): array {
      $r['quantity'] = (int) $r['quantity'];
      $r['foil'] = (bool) $r['foil'];
      return $r;
    }, [...$commanders, ...$slots]);
  }

  /**
   * Statistics for one set, or NULL when no printing has that set code.
   *
   * @param string $setCode
   *   Set code, e.g. "thb".
   * @param bool $eur
   *   TRUE to value in EUR.
   * @param float $usdToEur
   *   Euros per US dollar.
   *
   * @return array<string, mixed>|null
   *   Data keyed like the SetStatsDetail GraphQL type.
   */
  public function set(string $setCode, bool $eur, float $usdToEur): ?array {
    $printings = $this->database->query(
      "SELECT c.title, n.uuid AS cardId, cn.field_collector_number_value AS collectorNumber,
         r.field_rarity_value AS rarity, sn.field_set_name_value AS setName,
         e.field_price_eur_value AS eur, ef.field_price_eur_foil_value AS eurFoil,
         u.field_price_usd_value AS usd, uf.field_price_usd_foil_value AS usdFoil,
         (SELECT SUM(COALESCE(o.field_quantity_owned_value, 0)) FROM {node__field_card} fc
            INNER JOIN {node_field_data} cc ON cc.nid = fc.entity_id AND cc.type = 'collection_card' AND cc.status = 1
            LEFT JOIN {node__field_quantity_owned} o ON o.entity_id = cc.nid
            WHERE fc.field_card_target_id = c.nid) AS regular,
         (SELECT SUM(COALESCE(f.field_quantity_foil_value, 0)) FROM {node__field_card} fc
            INNER JOIN {node_field_data} cc ON cc.nid = fc.entity_id AND cc.type = 'collection_card' AND cc.status = 1
            LEFT JOIN {node__field_quantity_foil} f ON f.entity_id = cc.nid
            WHERE fc.field_card_target_id = c.nid) AS foil
       FROM {node__field_set_code} s
       INNER JOIN {node_field_data} c ON c.nid = s.entity_id AND c.type = 'mtg_card'
       INNER JOIN {node} n ON n.nid = c.nid
       LEFT JOIN {node__field_set_name} sn ON sn.entity_id = c.nid
       LEFT JOIN {node__field_collector_number} cn ON cn.entity_id = c.nid
       LEFT JOIN {node__field_rarity} r ON r.entity_id = c.nid
       LEFT JOIN {node__field_price_eur} e ON e.entity_id = c.nid
       LEFT JOIN {node__field_price_eur_foil} ef ON ef.entity_id = c.nid
       LEFT JOIN {node__field_price_usd} u ON u.entity_id = c.nid
       LEFT JOIN {node__field_price_usd_foil} uf ON uf.entity_id = c.nid
       WHERE s.field_set_code_value = :code",
      [':code' => strtolower(trim($setCode))],
    )->fetchAll(FetchAs::Associative);
    if (!$printings) {
      return NULL;
    }
    return [
      'setCode' => strtolower(trim($setCode)),
      'setName' => (string) ($printings[0]['setName'] ?? ''),
      'currency' => $eur ? 'EUR' : 'USD',
    ] + StatsDetailCalculator::set($printings, $eur, $usdToEur);
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
