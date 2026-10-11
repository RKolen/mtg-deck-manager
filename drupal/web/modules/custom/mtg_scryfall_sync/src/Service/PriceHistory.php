<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Service;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Database\Connection;
use Drupal\Core\State\StateInterface;

/**
 * Keeps the prices from before the latest import, to show price movers.
 *
 * Price imports overwrite the price fields in place. Just before an import,
 * snapshot() copies the current prices into mtg_price_previous, so movers()
 * can compare them with the new prices.
 */
final class PriceHistory {

  /**
   * State key: when the snapshot was taken (start of the latest import).
   */
  public const STATE_SNAPSHOT = 'mtg_scryfall_sync.price_snapshot';

  /**
   * Snapshot table.
   */
  private const TABLE = 'mtg_price_previous';

  /**
   * Price field per snapshot column.
   */
  private const COLUMNS = [
    'eur' => 'field_price_eur',
    'eur_foil' => 'field_price_eur_foil',
    'usd' => 'field_price_usd',
    'usd_foil' => 'field_price_usd_foil',
  ];

  /**
   * Constructs a PriceHistory service.
   *
   * @param \Drupal\Core\Database\Connection $database
   *   The database connection.
   * @param \Drupal\Core\State\StateInterface $state
   *   The state store.
   * @param \Drupal\Component\Datetime\TimeInterface $time
   *   The time service.
   */
  public function __construct(
    private readonly Connection $database,
    private readonly StateInterface $state,
    private readonly TimeInterface $time,
  ) {}

  /**
   * Copies every card's current prices into the snapshot table.
   *
   * Call right before overwriting prices. Does nothing when the table does
   * not exist yet (update hook not run).
   */
  public function snapshot(): void {
    if (!$this->database->schema()->tableExists(self::TABLE)) {
      return;
    }
    $select = $this->database->select('node_field_data', 'n');
    $select->addField('n', 'nid');
    foreach (self::COLUMNS as $column => $field) {
      $select->leftJoin('node__' . $field, $column, "$column.entity_id = n.nid AND $column.deleted = 0");
      $select->addField($column, $field . '_value', $column);
    }
    $select->condition('n.type', 'mtg_card');
    $select->condition('n.default_langcode', 1);

    $transaction = $this->database->startTransaction();
    try {
      // DELETE, not TRUNCATE: TRUNCATE commits implicitly on MySQL.
      $this->database->delete(self::TABLE)->execute();
      $this->database->insert(self::TABLE)
        ->fields(array_merge(['nid'], array_keys(self::COLUMNS)))
        ->from($select)
        ->execute();
    }
    catch (\Throwable $e) {
      $transaction->rollBack();
      throw $e;
    }
    $this->state->set(self::STATE_SNAPSHOT, $this->time->getRequestTime());
  }

  /**
   * Cards whose regular price changed most, in percent, since the snapshot.
   *
   * @param string $currency
   *   EUR or USD.
   * @param int $limit
   *   Number of cards to return.
   * @param float $minPrice
   *   Cards must cost at least this both before and after. Thin markets
   *   for cheap cards make jumps like 0.02 to 3.27 meaningless.
   *
   * @return array<int, array{nid: int, previous: float, current: float, changePct: float}>
   *   Biggest movers first, one printing per card name.
   */
  public function movers(string $currency, int $limit, float $minPrice): array {
    if (!$this->database->schema()->tableExists(self::TABLE)) {
      return [];
    }
    $column = strtoupper($currency) === 'USD' ? 'usd' : 'eur';
    $field = self::COLUMNS[$column];

    $query = $this->database->select(self::TABLE, 'p');
    $query->join('node__' . $field, 'c', 'c.entity_id = p.nid AND c.deleted = 0');
    $query->join('node_field_data', 'n', 'n.nid = p.nid');
    $query->join('node__field_type_line', 't', 't.entity_id = p.nid');
    $query->addField('p', 'nid');
    $query->addField('n', 'title');
    $query->addField('p', $column, 'previous');
    $query->addField('c', $field . '_value', 'current');
    $pct = "(c.{$field}_value - p.$column) / p.$column";
    $query->addExpression($pct, 'change_pct');
    $query->condition("p.$column", 0, '>');
    $query->where("p.$column <> c.{$field}_value");
    $query->where("(p.$column >= :min AND c.{$field}_value >= :min)", [":min" => $minPrice]);
    $query->condition('t.field_type_line_value', 'Token%', 'NOT LIKE');
    $query->orderBy('abs_change', 'DESC');
    $query->addExpression("ABS($pct)", 'abs_change');
    // Fetch extra rows: several printings of one card often move together.
    $query->range(0, max(1, $limit) * 20);

    $result = [];
    $seen = [];
    foreach ($query->execute() as $row) {
      if (isset($seen[$row->title])) {
        continue;
      }
      $seen[$row->title] = TRUE;
      $result[] = [
        'nid' => (int) $row->nid,
        'previous' => (float) $row->previous,
        'current' => (float) $row->current,
        'changePct' => round((float) $row->change_pct * 100, 1),
      ];
      if (count($result) >= $limit) {
        break;
      }
    }
    return $result;
  }

  /**
   * When the snapshot was taken, or NULL when there is none yet.
   */
  public function snapshotTime(): ?int {
    $time = $this->state->get(self::STATE_SNAPSHOT);
    return $time !== NULL ? (int) $time : NULL;
  }

}
