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
   * State key: when the prices in the snapshot were imported.
   */
  public const STATE_SNAPSHOT = 'mtg_scryfall_sync.price_snapshot';

  /**
   * State key: when the current prices were imported.
   */
  public const STATE_PRICES_UPDATED = 'mtg_scryfall_sync.prices_updated';

  /**
   * State key of the full sync's completion time (older installs).
   */
  private const STATE_LAST_SYNC = 'mtg_scryfall_sync.last_sync';

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
    // The snapshot holds the prices of the previous import, so date it by
    // that import, not by now.
    $previous = $this->state->get(self::STATE_PRICES_UPDATED) ?? $this->state->get(self::STATE_LAST_SYNC);
    $this->state->set(self::STATE_SNAPSHOT, $previous);
  }

  /**
   * Cards whose regular price rose and fell most, in percent.
   *
   * Half the list is risers and half fallers, alternating. Ranking all
   * changes together would show only risers: a price can rise by hundreds
   * of percent but never fall by more than 100.
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
   *   Risers and fallers alternating, biggest first, one printing per card
   *   name.
   */
  public function movers(string $currency, int $limit, float $minPrice): array {
    if (!$this->database->schema()->tableExists(self::TABLE)) {
      return [];
    }
    $limit = max(1, $limit);
    $risers = $this->topMovers($currency, $minPrice, (int) ceil($limit / 2), TRUE);
    $fallers = $this->topMovers($currency, $minPrice, intdiv($limit, 2), FALSE);

    $result = [];
    for ($i = 0; $i < max(count($risers), count($fallers)); $i++) {
      if (isset($risers[$i])) {
        $result[] = $risers[$i];
      }
      if (isset($fallers[$i])) {
        $result[] = $fallers[$i];
      }
    }
    return $result;
  }

  /**
   * The biggest risers or fallers.
   *
   * @param string $currency
   *   EUR or USD.
   * @param float $minPrice
   *   Minimum price before and after.
   * @param int $count
   *   Number of cards to return.
   * @param bool $rising
   *   TRUE for risers, FALSE for fallers.
   *
   * @return array<int, array{nid: int, previous: float, current: float, changePct: float}>
   *   Biggest change first, one printing per card name.
   */
  private function topMovers(string $currency, float $minPrice, int $count, bool $rising): array {
    if ($count <= 0) {
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
    $query->addExpression("(c.{$field}_value - p.$column) / p.$column", 'change_pct');
    $query->condition("p.$column", 0, '>');
    $query->where($rising ? "c.{$field}_value > p.$column" : "c.{$field}_value < p.$column");
    $query->where("(p.$column >= :min AND c.{$field}_value >= :min)", [':min' => $minPrice]);
    $query->condition('t.field_type_line_value', 'Token%', 'NOT LIKE');
    $query->orderBy('change_pct', $rising ? 'DESC' : 'ASC');
    // Fetch extra rows: several printings of one card often move together.
    $query->range(0, $count * 20);

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
      if (count($result) >= $count) {
        break;
      }
    }
    return $result;
  }

  /**
   * Records that prices were just imported. Call when an import finishes.
   */
  public function markUpdated(): void {
    $this->state->set(self::STATE_PRICES_UPDATED, $this->time->getRequestTime());
  }

  /**
   * When the snapshot's prices were imported, or NULL when unknown.
   */
  public function snapshotTime(): ?int {
    $time = $this->state->get(self::STATE_SNAPSHOT);
    return $time !== NULL ? (int) $time : NULL;
  }

}
