<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Service;

use Drupal\Core\Database\Connection;

/**
 * Stores which tokens, emblems and game pieces each card makes.
 *
 * Scryfall links a card to what it creates in its all_parts list: tokens
 * as "token", and emblems, dungeons and cards like The Initiative as
 * "combo_piece". Rows are kept per card name, so every printing of a card
 * shares them; each part ID is one printing of the token.
 */
final class CardParts {

  /**
   * Table holding the links.
   */
  public const TABLE = 'mtg_card_part';

  /**
   * Type lines of combo pieces that are game pieces rather than real cards.
   */
  private const GAME_PIECE_TYPES = '/^(Emblem|Dungeon|Card)\b/';

  /**
   * Reference cards that are not game pieces: reminders and checklists.
   */
  private const REFERENCE_CARDS = '/^(On an Adventure|Foretell|Plot)$|Checklist/';

  /**
   * Rows written per insert query.
   */
  private const CHUNK = 500;

  public function __construct(
    private readonly Connection $database,
  ) {}

  /**
   * Token, emblem and game-piece parts of a Scryfall card object.
   *
   * @param array<string, mixed> $card
   *   Decoded Scryfall card object.
   *
   * @return list<array{part_id: string, name: string, type_line: string, component: string}>
   *   One entry per linked printing, the card itself excluded.
   */
  public static function fromCard(array $card): array {
    $own = (string) ($card['name'] ?? '');
    $parts = [];
    foreach ($card['all_parts'] ?? [] as $part) {
      if (!is_array($part)) {
        continue;
      }
      $id = (string) ($part['id'] ?? '');
      $name = (string) ($part['name'] ?? '');
      $type = (string) ($part['type_line'] ?? '');
      $component = (string) ($part['component'] ?? '');
      if ($id === '' || $name === '' || $name === $own) {
        continue;
      }
      $isToken = $component === 'token';
      $isGamePiece = $component === 'combo_piece'
        && preg_match(self::GAME_PIECE_TYPES, $type) === 1
        && preg_match(self::REFERENCE_CARDS, $name) !== 1;
      if ($isToken || $isGamePiece) {
        $parts[$id] = [
          'part_id' => $id,
          'name' => $name,
          'type_line' => $type,
          'component' => $component,
        ];
      }
    }
    return array_values($parts);
  }

  /**
   * Adds a card's parts, keeping links from its other printings.
   *
   * @param string $cardName
   *   Card name as stored in the mtg_card title.
   * @param list<array{part_id: string, name: string, type_line: string, component: string}> $parts
   *   Parts from fromCard().
   */
  public function record(string $cardName, array $parts): void {
    foreach ($parts as $part) {
      $this->database->merge(self::TABLE)
        ->keys(['card_name' => $cardName, 'part_id' => $part['part_id']])
        ->fields([
          'name' => $part['name'],
          'type_line' => $part['type_line'],
          'component' => $part['component'],
        ])
        ->execute();
    }
  }

  /**
   * Replaces every link with the given rows.
   *
   * @param iterable<array{card_name: string, part_id: string, name: string, type_line: string, component: string}> $rows
   *   All links; duplicates of a card name and part ID are written once.
   *
   * @return int
   *   Rows written.
   */
  public function replaceAll(iterable $rows): int {
    $transaction = $this->database->startTransaction();
    $this->database->truncate(self::TABLE)->execute();
    $seen = [];
    $batch = [];
    $written = 0;
    foreach ($rows as $row) {
      $key = $row['card_name'] . "\0" . $row['part_id'];
      if (isset($seen[$key])) {
        continue;
      }
      $seen[$key] = TRUE;
      $batch[] = $row;
      if (count($batch) >= self::CHUNK) {
        $written += $this->insertBatch($batch);
        $batch = [];
      }
    }
    $written += $this->insertBatch($batch);
    unset($transaction);
    return $written;
  }

  /**
   * Links for the given card names.
   *
   * @param string[] $cardNames
   *   Card names (mtg_card titles).
   *
   * @return list<array{card_name: string, part_id: string, name: string, type_line: string, component: string}>
   *   Stored links.
   */
  public function forCards(array $cardNames): array {
    $cardNames = array_values(array_unique(array_filter($cardNames, static fn($n): bool => $n !== '')));
    $rows = [];
    foreach (array_chunk($cardNames, self::CHUNK) as $chunk) {
      $result = $this->database->select(self::TABLE, 'p')
        ->fields('p', ['card_name', 'part_id', 'name', 'type_line', 'component'])
        ->condition('card_name', $chunk, 'IN')
        ->execute();
      foreach ($result as $record) {
        $rows[] = [
          'card_name' => (string) $record->card_name,
          'part_id' => (string) $record->part_id,
          'name' => (string) $record->name,
          'type_line' => (string) $record->type_line,
          'component' => (string) $record->component,
        ];
      }
    }
    return $rows;
  }

  /**
   * Writes one batch of rows.
   *
   * @param list<array{card_name: string, part_id: string, name: string, type_line: string, component: string}> $batch
   *   Rows to insert.
   *
   * @return int
   *   Rows written.
   */
  private function insertBatch(array $batch): int {
    if ($batch === []) {
      return 0;
    }
    $insert = $this->database->insert(self::TABLE)
      ->fields(['card_name', 'part_id', 'name', 'type_line', 'component']);
    foreach ($batch as $row) {
      $insert->values([
        'card_name' => $row['card_name'],
        'part_id' => $row['part_id'],
        'name' => $row['name'],
        'type_line' => $row['type_line'],
        'component' => $row['component'],
      ]);
    }
    $insert->execute();
    return count($batch);
  }

}
