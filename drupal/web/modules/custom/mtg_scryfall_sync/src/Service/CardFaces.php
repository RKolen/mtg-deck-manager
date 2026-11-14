<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Service;

use Drupal\Core\Cache\CacheTagsInvalidatorInterface;
use Drupal\Core\Database\Connection;

/**
 * Stores every face of multi-faced cards.
 *
 * The mtg_card node keeps only the first face's mana cost and oracle text,
 * so back faces of transform, modal double-faced, adventure, split and flip
 * cards were lost. Faces are kept per card name here, because every
 * printing of a card shares its rules text.
 */
final class CardFaces {

  /**
   * Table holding the faces.
   */
  public const TABLE = 'mtg_card_face';

  /**
   * Cache tag invalidated whenever faces change.
   */
  public const CACHE_TAG = 'mtg_card_face_list';

  /**
   * Layouts whose faces are not separate rules faces.
   *
   * Tokens are skipped like in CardParts. Art series cards are not playable,
   * and reversible cards print the same face twice.
   */
  private const SKIP_LAYOUTS = [
    'token',
    'emblem',
    'double_faced_token',
    'art_series',
    'reversible_card',
  ];

  /**
   * Rows written per insert query.
   */
  private const CHUNK = 500;

  /**
   * Columns of a face row, apart from the card name.
   */
  private const FACE_COLUMNS = [
    'face_index',
    'name',
    'mana_cost',
    'type_line',
    'oracle_text',
    'power',
    'toughness',
    'loyalty',
    'layout',
  ];

  public function __construct(
    private readonly Connection $database,
    private readonly CacheTagsInvalidatorInterface $cacheTagsInvalidator,
  ) {}

  /**
   * Faces of a Scryfall card object.
   *
   * @param array<string, mixed> $card
   *   Decoded Scryfall card object.
   *
   * @return list<array{face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}>
   *   One entry per face, or an empty list for single-faced cards.
   */
  public static function fromCard(array $card): array {
    if (in_array($card['layout'] ?? '', self::SKIP_LAYOUTS, TRUE)) {
      return [];
    }
    $faces = $card['card_faces'] ?? NULL;
    if (!is_array($faces) || count($faces) < 2) {
      return [];
    }
    $layout = is_string($card['layout'] ?? NULL) ? $card['layout'] : '';
    $rows = [];
    foreach (array_values($faces) as $index => $face) {
      if (!is_array($face)) {
        continue;
      }
      $text = static fn(string $key): string => is_scalar($face[$key] ?? NULL) ? (string) $face[$key] : '';
      $rows[] = [
        'face_index' => $index,
        'name' => $text('name'),
        'mana_cost' => $text('mana_cost'),
        'type_line' => $text('type_line'),
        'oracle_text' => $text('oracle_text'),
        'power' => $text('power'),
        'toughness' => $text('toughness'),
        'loyalty' => $text('loyalty'),
        'layout' => $layout,
      ];
    }
    return count($rows) >= 2 ? $rows : [];
  }

  /**
   * Writes a card's faces, replacing what was stored for that name.
   *
   * @param string $cardName
   *   Card name as stored in the mtg_card title.
   * @param list<array{face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}> $faces
   *   Faces from fromCard().
   */
  public function record(string $cardName, array $faces): void {
    if ($cardName === '' || $faces === []) {
      return;
    }
    foreach ($faces as $face) {
      $fields = $face;
      unset($fields['face_index']);
      $this->database->merge(self::TABLE)
        ->keys(['card_name' => $cardName, 'face_index' => $face['face_index']])
        ->fields($fields)
        ->execute();
    }
    $this->cacheTagsInvalidator->invalidateTags([self::CACHE_TAG]);
  }

  /**
   * Replaces every stored face with the given rows.
   *
   * @param iterable<array{card_name: string, face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}> $rows
   *   All faces; the first row for a card name and face index wins.
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
      $key = $row['card_name'] . "\0" . $row['face_index'];
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
    $this->cacheTagsInvalidator->invalidateTags([self::CACHE_TAG]);
    return $written;
  }

  /**
   * Faces of one card, in printed order.
   *
   * @param string $cardName
   *   Card name (mtg_card title).
   *
   * @return list<array{face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}>
   *   Stored faces, or an empty list for single-faced cards.
   */
  public function forCard(string $cardName): array {
    return $this->forCards([$cardName])[$cardName] ?? [];
  }

  /**
   * Faces of several cards, keyed by card name.
   *
   * @param string[] $cardNames
   *   Card names (mtg_card titles).
   *
   * @return array<string, list<array{face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}>>
   *   Faces in printed order per card name; single-faced cards are absent.
   */
  public function forCards(array $cardNames): array {
    $cardNames = array_values(array_unique(array_filter($cardNames, static fn($n): bool => $n !== '')));
    $faces = [];
    foreach (array_chunk($cardNames, self::CHUNK) as $chunk) {
      $result = $this->database->select(self::TABLE, 'f')
        ->fields('f', ['card_name', ...self::FACE_COLUMNS])
        ->condition('card_name', $chunk, 'IN')
        ->orderBy('card_name')
        ->orderBy('face_index')
        ->execute();
      foreach ($result as $record) {
        $faces[(string) $record->card_name][] = [
          'face_index' => (int) $record->face_index,
          'name' => (string) $record->name,
          'mana_cost' => (string) $record->mana_cost,
          'type_line' => (string) $record->type_line,
          'oracle_text' => (string) $record->oracle_text,
          'power' => (string) $record->power,
          'toughness' => (string) $record->toughness,
          'loyalty' => (string) $record->loyalty,
          'layout' => (string) $record->layout,
        ];
      }
    }
    return $faces;
  }

  /**
   * Writes one batch of rows.
   *
   * @param list<array{card_name: string, face_index: int, name: string, mana_cost: string, type_line: string, oracle_text: string, power: string, toughness: string, loyalty: string, layout: string}> $batch
   *   Rows to insert.
   *
   * @return int
   *   Rows written.
   */
  private function insertBatch(array $batch): int {
    if ($batch === []) {
      return 0;
    }
    $columns = ['card_name', ...self::FACE_COLUMNS];
    $insert = $this->database->insert(self::TABLE)->fields($columns);
    foreach ($batch as $row) {
      $insert->values(array_map(static fn(string $column) => $row[$column], $columns));
    }
    $insert->execute();
    return count($batch);
  }

}
