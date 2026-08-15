<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Service;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;

/**
 * Ensures MTG set taxonomy terms exist and stay linked to card nodes.
 */
final class SetTaxonomy {

  public const VOCABULARY = 'mtg_set';

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {}

  /**
   * Loads or creates a set term for a Scryfall set code.
   */
  public function ensureTerm(string $code, string $name = ''): ?TermInterface {
    $code = strtolower(trim($code));
    if ($code === '') {
      return NULL;
    }
    $name = trim($name);
    if ($name === '') {
      $name = strtoupper($code);
    }

    $storage = $this->entityTypeManager->getStorage('taxonomy_term');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('vid', self::VOCABULARY)
      ->condition('field_set_code', $code)
      ->range(0, 1)
      ->execute();

    if ($ids !== []) {
      /** @var \Drupal\taxonomy\TermInterface $term */
      $term = $storage->load(reset($ids));
      if ($term instanceof TermInterface && $term->label() !== $name && $name !== strtoupper($code)) {
        $term->setName($name);
        $term->save();
      }
      return $term;
    }

    /** @var \Drupal\taxonomy\TermInterface $term */
    $term = $storage->create([
      'vid' => self::VOCABULARY,
      'name' => $name,
      'field_set_code' => $code,
    ]);
    $term->save();
    return $term;
  }

  /**
   * Applies set string fields + taxonomy reference on a card node.
   */
  public function applyToCard(NodeInterface $card, string $code, string $name = ''): void {
    if ($card->bundle() !== 'mtg_card') {
      return;
    }
    $code = strtolower(trim($code));
    $name = trim($name);
    if ($card->hasField('field_set_code')) {
      $card->set('field_set_code', $code);
    }
    if ($card->hasField('field_set_name')) {
      $card->set('field_set_name', $name !== '' ? $name : strtoupper($code));
    }
    if (!$card->hasField('field_set')) {
      return;
    }
    $term = $this->ensureTerm($code, $name);
    if ($term instanceof TermInterface) {
      $card->set('field_set', ['target_id' => $term->id()]);
    }
  }

  /**
   * Creates missing set terms from distinct card set code/name values.
   *
   * @return array{created: int, updated: int, total: int}
   *   Counts for logging.
   */
  public function syncFromCards(): array {
    $database = \Drupal::database();
    $query = $database->select('node__field_set_code', 'c');
    $query->leftJoin('node__field_set_name', 'n', 'n.entity_id = c.entity_id AND n.deleted = 0');
    $query->addField('c', 'field_set_code_value', 'code');
    $query->addExpression('MAX(n.field_set_name_value)', 'name');
    $query->condition('c.deleted', 0);
    $query->condition('c.field_set_code_value', '', '<>');
    $query->groupBy('c.field_set_code_value');

    $created = 0;
    $updated = 0;
    $total = 0;
    foreach ($query->execute() as $row) {
      $total++;
      $code = strtolower((string) $row->code);
      $name = trim((string) ($row->name ?? ''));
      $before = $this->loadByCode($code);
      $term = $this->ensureTerm($code, $name);
      if ($before === NULL && $term !== NULL) {
        $created++;
      }
      elseif ($before !== NULL && $term !== NULL && $before->label() !== $term->label()) {
        $updated++;
      }
    }

    return [
      'created' => $created,
      'updated' => $updated,
      'total' => $total,
    ];
  }

  /**
   * Backfills field_set on card nodes that have a set code but no term ref.
   *
   * @return int
   *   Number of cards updated.
   */
  public function backfillCardReferences(int $limit = 500): int {
    $nids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'mtg_card')
      ->condition('field_set_code', '', '<>')
      ->notExists('field_set')
      ->range(0, $limit)
      ->execute();

    if ($nids === []) {
      return 0;
    }

    $updated = 0;
    foreach ($this->entityTypeManager->getStorage('node')->loadMultiple($nids) as $card) {
      if (!$card instanceof NodeInterface) {
        continue;
      }
      $code = (string) ($card->get('field_set_code')->value ?? '');
      $name = (string) ($card->get('field_set_name')->value ?? '');
      $term = $this->ensureTerm($code, $name);
      if ($term === NULL) {
        continue;
      }
      $card->set('field_set', ['target_id' => $term->id()]);
      $card->setNewRevision(FALSE);
      $card->save();
      $updated++;
    }
    return $updated;
  }

  /**
   * Searches set terms by name or code.
   *
   * @param string $q
   *   Optional name or set-code fragment.
   * @param int $limit
   *   Maximum terms to return.
   *
   * @return list<array{code: string, name: string, count: int, tid: int}>
   *   Set options for autocomplete UIs.
   */
  public function search(string $q = '', int $limit = 40): array {
    $storage = $this->entityTypeManager->getStorage('taxonomy_term');
    $limit = max(1, min(2000, $limit));
    $query = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('vid', self::VOCABULARY)
      ->sort('name', 'ASC')
      ->range(0, $limit);

    $q = trim($q);
    if ($q !== '') {
      $group = $query->orConditionGroup()
        ->condition('name', $q, 'CONTAINS')
        ->condition('field_set_code', strtolower($q), 'CONTAINS');
      $query->condition($group);
    }

    $ids = $query->execute();
    if ($ids === []) {
      return [];
    }

    $rows = [];
    foreach ($storage->loadMultiple($ids) as $term) {
      if (!$term instanceof TermInterface) {
        continue;
      }
      $code = strtolower((string) ($term->get('field_set_code')->value ?? ''));
      $rows[] = [
        'code' => $code,
        'name' => (string) $term->label(),
        'count' => 0,
        'tid' => (int) $term->id(),
      ];
    }

    // Keep alphabetical order for select lists (name ASC from query).
    if ($rows !== []) {
      $codes = array_column($rows, 'code');
      $counts = $this->countsByCode($codes);
      foreach ($rows as &$row) {
        $row['count'] = $counts[$row['code']] ?? 0;
      }
      unset($row);
    }

    return $rows;
  }

  /**
   * Loads a set term by Scryfall set code.
   */
  private function loadByCode(string $code): ?TermInterface {
    $ids = $this->entityTypeManager->getStorage('taxonomy_term')->getQuery()
      ->accessCheck(FALSE)
      ->condition('vid', self::VOCABULARY)
      ->condition('field_set_code', $code)
      ->range(0, 1)
      ->execute();
    if ($ids === []) {
      return NULL;
    }
    $term = $this->entityTypeManager->getStorage('taxonomy_term')->load(reset($ids));
    return $term instanceof TermInterface ? $term : NULL;
  }

  /**
   * Counts published cards per set code.
   *
   * @param string[] $codes
   *   Lowercase Scryfall set codes.
   *
   * @return array<string, int>
   *   Map of set code to card count.
   */
  private function countsByCode(array $codes): array {
    if ($codes === []) {
      return [];
    }
    $query = \Drupal::database()->select('node__field_set_code', 'c');
    $query->addField('c', 'field_set_code_value', 'code');
    $query->addExpression('COUNT(*)', 'card_count');
    $query->condition('c.deleted', 0);
    $query->condition('c.field_set_code_value', $codes, 'IN');
    $query->groupBy('c.field_set_code_value');
    $out = [];
    foreach ($query->execute() as $row) {
      $out[strtolower((string) $row->code)] = (int) $row->card_count;
    }
    return $out;
  }

}
