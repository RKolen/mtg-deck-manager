<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\Core\State\StateInterface;
use GuzzleHttp\ClientInterface;

/**
 * Imports Scryfall bulk card data into mtg_card nodes.
 *
 * Design goals
 * ------------
 * - Memory-efficient: streams the file line by line; never loads the full
 *   300 MB JSON array into PHP memory.
 * - Resumable: the current file-line offset is stored in Drupal State so an
 *   interrupted import can continue from where it left off.
 * - Safe to re-run: upserts by scryfall_id, so duplicate runs are idempotent.
 *
 * Usage flow
 * ----------
 *   1. downloadBulkData()         - fetches the bulk JSON once.
 *   2. resetProgress()            - (optional) restart from the beginning.
 *   3. importNextBatch()          - call repeatedly (or via cron) until it
 *                                   returns FALSE, indicating completion.
 *   4. finalise()                 - records the last-sync timestamp.
 *
 * The Scryfall bulk endpoint is documented at:
 * https://scryfall.com/docs/api/bulk-data
 *
 * File format assumption
 * ----------------------
 * The Scryfall default_cards JSON is a top-level array with one card object
 * per line, e.g.:
 *   [
 *   {"id":"...","name":"..."},
 *   {"id":"...","name":"..."}
 *   ]
 * Lines starting with "[" or "]" are skipped; every other line is a card.
 */
class ScryfallImporter {

  /**
   * Scryfall bulk-data API endpoint.
   */
  private const BULK_DATA_URL = 'https://api.scryfall.com/bulk-data';

  /**
   * Bulk data type to use.
   */
  private const BULK_TYPE = 'default_cards';

  /**
   * Local path for the downloaded JSON file.
   */
  private const DATA_FILE = __DIR__ . '/../data/default_cards.json';

  /**
   * Number of card lines to process per importNextBatch() call.
   */
  private const BATCH_SIZE = 200;

  /**
   * State key tracking how many card lines have been processed so far.
   */
  private const STATE_OFFSET = 'mtg_scryfall_sync.import_offset';

  /**
   * State key for the total number of card lines in the current data file.
   */
  private const STATE_TOTAL = 'mtg_scryfall_sync.import_total';

  /**
   * State key storing the file byte position after the last processed batch.
   *
   * Enables O(1) seeking via fseek() instead of re-reading from line 1 each
   * batch, which would otherwise be O(n) per batch and O(n^2) overall for a
   * full 114k-card import.
   */
  private const STATE_BYTE_OFFSET = 'mtg_scryfall_sync.import_byte_offset';

  /**
   * Layouts that should be skipped during import.
   *
   * @var string[]
   */
  private const SKIP_LAYOUTS = [
    'token',
    'emblem',
    'art_series',
    'double_faced_token',
  ];

  /**
   * User-Agent sent with all Scryfall API requests.
   *
   * Scryfall requires a descriptive User-Agent including contact information.
   * See https://scryfall.com/docs/api.
   */
  private const USER_AGENT = 'MTGDeckManager/1.0 (drupal-module; contact@example.com)';

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly LoggerChannelFactoryInterface $loggerFactory,
    private readonly StateInterface $state,
    private readonly TimeInterface $time,
    private readonly ClientInterface $httpClient,
  ) {}

  /**
   * Downloads the Scryfall default_cards bulk JSON to the data directory.
   *
   * Only makes two HTTP requests: one to the index endpoint to resolve the
   * current download URI, then one streaming download of the bulk file.
   * Scryfall API rate limits do not apply to the bulk file CDN download.
   *
   * @throws \RuntimeException
   *   When the download or file write fails.
   */
  public function downloadBulkData(): void {
    $logger = $this->loggerFactory->get('mtg_scryfall_sync');

    $response = $this->httpClient->get(self::BULK_DATA_URL, [
      'headers' => [
        'User-Agent' => self::USER_AGENT,
        'Accept' => 'application/json',
      ],
    ]);
    $index = json_decode((string) $response->getBody(), TRUE, 512, JSON_THROW_ON_ERROR);

    $download_uri = NULL;
    foreach ($index['data'] as $item) {
      if ($item['type'] === self::BULK_TYPE) {
        $download_uri = $item['download_uri'];
        break;
      }
    }
    if ($download_uri === NULL) {
      throw new \RuntimeException('Could not locate default_cards entry in Scryfall bulk-data index.');
    }

    $logger->info('Downloading Scryfall bulk data from @uri.', ['@uri' => $download_uri]);

    $data_dir = dirname(self::DATA_FILE);
    if (!is_dir($data_dir)) {
      mkdir($data_dir, 0755, TRUE);
    }

    $this->httpClient->get($download_uri, [
      'headers' => [
        'User-Agent' => self::USER_AGENT,
        'Accept' => '*/*',
      ],
      'sink' => self::DATA_FILE,
    ]);

    $logger->info('Scryfall bulk data downloaded to @path.', ['@path' => self::DATA_FILE]);

    // Pre-count card lines and reset progress for a fresh import.
    $this->state->set(self::STATE_TOTAL, $this->countCardLines());
    $this->resetProgress();
  }

  /**
   * Returns TRUE if the local bulk data file exists.
   */
  public function dataFileExists(): bool {
    return file_exists(self::DATA_FILE);
  }

  /**
   * Returns the current import progress as an associative array.
   *
   * @return array{offset: int, total: int, percent: float}
   *   Import progress details.
   */
  public function getProgress(): array {
    $offset = (int) $this->state->get(self::STATE_OFFSET, 0);
    $total = (int) $this->state->get(self::STATE_TOTAL, 0);
    $percent = $total > 0 ? round(($offset / $total) * 100, 1) : 0.0;
    return [
      'offset' => $offset,
      'total' => $total,
      'percent' => $percent,
    ];
  }

  /**
   * Resets the import offset to zero so the next batch starts from the top.
   *
   * Does not delete the downloaded data file.
   */
  public function resetProgress(): void {
    $this->state->set(self::STATE_OFFSET, 0);
    $this->state->set(self::STATE_BYTE_OFFSET, 0);
    $this->loggerFactory->get('mtg_scryfall_sync')->info('Scryfall import progress reset.');
  }

  /**
   * Processes the next batch of BATCH_SIZE card lines from the data file.
   *
   * Reads only the lines required for this batch - no full-file load into
   * memory. Stores the new offset in state so the next call resumes correctly.
   *
   * @return bool
   *   TRUE if more cards remain after this batch, FALSE when complete.
   *
   * @throws \RuntimeException
   *   When the data file is missing.
   */
  public function importNextBatch(): bool {
    if (!$this->dataFileExists()) {
      throw new \RuntimeException('Scryfall data file not found. Run downloadBulkData() first.');
    }

    $logger = $this->loggerFactory->get('mtg_scryfall_sync');
    $storage = $this->entityTypeManager->getStorage('node');

    $offset = (int) $this->state->get(self::STATE_OFFSET, 0);
    $total = (int) $this->state->get(self::STATE_TOTAL, 0);
    $byte_offset = (int) $this->state->get(self::STATE_BYTE_OFFSET, 0);

    // Re-count if total was never stored (e.g. file downloaded outside this
    // class or state was cleared).
    if ($total === 0) {
      $total = $this->countCardLines();
      $this->state->set(self::STATE_TOTAL, $total);
    }

    $fh = fopen(self::DATA_FILE, 'rb');
    if ($fh === FALSE) {
      throw new \RuntimeException('Failed to open data file: ' . self::DATA_FILE);
    }

    // Seek directly to the stored byte position, avoiding an O(n) line scan
    // on every batch. Falls back to reading from the start when byte_offset
    // is 0 (first batch or after a reset).
    if ($byte_offset > 0) {
      fseek($fh, $byte_offset);
    }

    $processed = 0;

    while (!feof($fh)) {
      $raw = fgets($fh);
      if ($raw === FALSE) {
        break;
      }
      $line = ltrim($raw);
      if (!str_starts_with($line, '{')) {
        continue;
      }

      // Strip trailing comma added by JSON array formatting before decoding.
      $json = rtrim($line, " \t\n\r\0\x0B,");
      $card = json_decode($json, TRUE);
      if (is_array($card)) {
        $this->upsertCard($card, $storage);
      }

      $processed++;

      if ($processed >= self::BATCH_SIZE) {
        break;
      }
    }

    $new_byte_offset = ftell($fh);
    fclose($fh);

    $new_offset = $offset + $processed;
    $this->state->set(self::STATE_OFFSET, $new_offset);
    $this->state->set(self::STATE_BYTE_OFFSET, $new_byte_offset !== FALSE ? $new_byte_offset : 0);

    $logger->info('Scryfall batch: processed lines @from-@to of @total.', [
      '@from' => $offset + 1,
      '@to' => $new_offset,
      '@total' => $total,
    ]);

    return $new_offset < $total;
  }

  /**
   * Marks the sync as complete by recording the current timestamp.
   */
  public function finalise(): void {
    $this->state->set('mtg_scryfall_sync.last_sync', $this->time->getRequestTime());
    $this->state->set('mtg_scryfall_sync.sync_requested', FALSE);
    $this->loggerFactory->get('mtg_scryfall_sync')->info('Scryfall sync finalised.');
  }

  /**
   * Queues a full sync for execution via cron.
   */
  public function queueFullSync(): void {
    $this->state->set('mtg_scryfall_sync.sync_requested', TRUE);
    $this->loggerFactory->get('mtg_scryfall_sync')->info('Full Scryfall sync requested.');
  }

  /**
   * Counts card lines in the data file without loading the full file.
   *
   * A card line is any line whose first non-whitespace character is "{".
   * The opening "[" and closing "]" lines are not counted.
   *
   * @return int
   *   Number of card lines found.
   */
  private function countCardLines(): int {
    if (!$this->dataFileExists()) {
      return 0;
    }
    $count = 0;
    $fh = fopen(self::DATA_FILE, 'rb');
    if ($fh === FALSE) {
      return 0;
    }
    while (($line = fgets($fh)) !== FALSE) {
      if (str_starts_with(ltrim($line), '{')) {
        $count++;
      }
    }
    fclose($fh);
    return $count;
  }

  /**
   * Creates or updates a single mtg_card node from a Scryfall card object.
   *
   * Uses scryfall_id for deduplication: if a node with the same scryfall_id
   * already exists it is updated in place, otherwise a new node is created.
   *
   * @param array<string, mixed> $card
   *   Decoded Scryfall card object.
   * @param \Drupal\Core\Entity\EntityStorageInterface $storage
   *   Node storage.
   */
  private function upsertCard(array $card, $storage): void {
    if (isset($card['layout']) && in_array($card['layout'], self::SKIP_LAYOUTS, TRUE)) {
      return;
    }

    $scryfall_id = $card['id'] ?? NULL;
    if ($scryfall_id === NULL) {
      return;
    }

    $existing = $storage->loadByProperties(['field_scryfall_id' => $scryfall_id]);
    $node = $existing ? reset($existing) : NULL;

    if ($node === NULL) {
      $node = $storage->create([
        'type' => 'mtg_card',
        'status' => 1,
      ]);
    }

    // Double-faced cards (transform, modal_dfc, etc.) store mana_cost,
    // oracle_text, and colors on card_faces[0] rather than at the top level.
    $face = $card['card_faces'][0] ?? [];
    $oracle_text = $card['oracle_text'] ?? $face['oracle_text'] ?? '';
    $mana_cost = $card['mana_cost'] ?? $face['mana_cost'] ?? '';
    $colors = $card['colors'] ?? $face['colors'] ?? [];

    // Scryfall provides a pre-computed produced_mana array covering all card
    // types (creatures, artifacts, lands). Use it directly rather than
    // attempting to parse oracle text with regexes, which would miss non-tap
    // abilities and cards with unusual wording.
    // Filter out colourless (C) - not a colour for manabase analysis.
    $produced_mana = array_values(array_filter(
      $card['produced_mana'] ?? [],
      fn(string $c) => $c !== 'C',
    ));
    $is_mana_producer = $produced_mana !== [];

    // Image URI - prefer normal size, fall back through available options.
    $image_uri = $card['image_uris']['normal']
      ?? $card['image_uris']['small']
      ?? ($face['image_uris']['normal'] ?? '');

    $node->set('title', $card['name'] ?? 'Unknown');
    $node->set('field_mana_cost', $mana_cost);
    // Cap CMC at 9999.9 (the field_cmc decimal(5,1) maximum). Outlier cards
    // such as B.F.M. (Big Furry Monster) use cmc: 1000000 as a joke value.
    $node->set('field_cmc', min((float) ($card['cmc'] ?? 0), 9999.9));
    $node->set('field_type_line', $card['type_line'] ?? '');
    $node->set('field_colors', $colors);
    $node->set('field_color_identity', $card['color_identity'] ?? []);
    $node->set('field_oracle_text', $oracle_text);
    $node->set('field_scryfall_id', $scryfall_id);
    $node->set('field_image_uri', $image_uri);
    $node->set('field_is_mana_producer', $is_mana_producer);
    $node->set('field_produced_mana', $produced_mana);
    // Power and toughness are strings to handle values like "*" or "1+*".
    // Loyalty covers planeswalkers; these fields are NULL for non-creatures
    // and non-planeswalkers respectively.
    $node->set('field_power', $card['power'] ?? $face['power'] ?? NULL);
    $node->set('field_toughness', $card['toughness'] ?? $face['toughness'] ?? NULL);
    $node->set('field_loyalty', $card['loyalty'] ?? NULL);

    // Legalities: store only the format keys where the card is "legal".
    // Formats with "not_legal", "banned", or "restricted" are omitted so the
    // field can be queried as an inclusion list (e.g. "is 'modern' in the
    // field?" means the card is legal in Modern).
    $legal_formats = [];
    foreach ($card['legalities'] ?? [] as $format => $status) {
      if ($status === 'legal') {
        $legal_formats[] = $format;
      }
    }
    $node->set('field_legal_formats', $legal_formats);

    $node->save();
  }

}
