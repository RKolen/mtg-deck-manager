<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Commands;

use Drupal\mtg_scryfall_sync\ScryfallImporter;
use Drupal\mtg_scryfall_sync\Service\CardParts;
use Drupal\mtg_scryfall_sync\Service\SetTaxonomy;
use Drush\Commands\DrushCommands;

/**
 * Drush commands for the MTG Scryfall Sync module.
 */
class ScryfallCommands extends DrushCommands {

  public function __construct(
    private readonly ScryfallImporter $importer,
    private readonly SetTaxonomy $setTaxonomy,
    private readonly CardParts $cardParts,
  ) {
    parent::__construct();
  }

  /**
   * Rebuilds which tokens, emblems and game pieces each card makes.
   *
   * Without --file it reads the local bulk file. With --file it loads a
   * tab-separated list (card name, part ID, part name, part type line,
   * component), e.g. one made on the host by scripts/card-parts.mjs, so the
   * container does not have to read the whole bulk file.
   *
   * @param array $options
   *   Command options.
   *
   * @command mtg:card-parts
   * @option file Tab-separated card parts file to load instead of the bulk file.
   * @usage ddev drush mtg:card-parts
   * @usage ddev drush mtg:card-parts --file=/var/www/html/card_parts.tsv
   */
  public function cardParts(array $options = ['file' => NULL]): void {
    $file = $options['file'] ?? NULL;
    try {
      if (is_string($file) && $file !== '') {
        $written = $this->cardParts->replaceAll($this->readPartsFile($file));
      }
      else {
        if (!$this->importer->dataFileExists()) {
          $this->logger()->error('No data file found. Run mtg:scryfall-download first, or pass --file.');
          return;
        }
        $written = $this->importer->importCardParts();
      }
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Card parts import failed: ' . $e->getMessage());
      return;
    }
    $this->output()->writeln(sprintf('Card parts import complete: %d links written.', $written));
  }

  /**
   * Yields rows from a tab-separated card parts file.
   *
   * @return \Generator<int, array{card_name: string, part_id: string, name: string, type_line: string, component: string}>
   *   One link per valid line.
   *
   * @throws \RuntimeException
   *   When the file cannot be opened.
   */
  private function readPartsFile(string $file): \Generator {
    $fh = @fopen($file, 'rb');
    if ($fh === FALSE) {
      throw new \RuntimeException('Cannot open ' . $file);
    }
    try {
      while (($line = fgets($fh)) !== FALSE) {
        $cols = explode("\t", rtrim($line, "\r\n"));
        if (count($cols) !== 5 || $cols[0] === '' || $cols[1] === '') {
          continue;
        }
        yield [
          'card_name' => $cols[0],
          'part_id' => $cols[1],
          'name' => $cols[2],
          'type_line' => $cols[3],
          'component' => $cols[4],
        ];
      }
    }
    finally {
      fclose($fh);
    }
  }

  /**
   * Downloads the Scryfall default_cards bulk JSON file.
   *
   * @command mtg:scryfall-download
   * @aliases mtg-dl
   * @usage ddev drush mtg:scryfall-download
   */
  public function download(): void {
    $this->output()->writeln('Downloading Scryfall bulk data...');
    $this->importer->downloadBulkData();
    $this->output()->writeln('Download complete.');
  }

  /**
   * Runs a full Scryfall import (download + all batches until complete).
   *
   * This command blocks until the entire import finishes, which can take
   * several minutes. For controlled step-by-step execution, use
   * mtg:scryfall-batch instead.
   *
   * @command mtg:scryfall-sync
   * @aliases mtg-sync
   * @usage ddev drush mtg:scryfall-sync
   * @usage ddev drush mtg:scryfall-sync --skip-download
   *
   * @option skip-download Skip the download step and use the existing data file.
   */
  public function sync(array $options = ['skip-download' => FALSE]): void {
    if (!$options['skip-download']) {
      $this->output()->writeln('Downloading Scryfall bulk data...');
      $this->importer->downloadBulkData();
    }

    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run without --skip-download first.');
      return;
    }

    $this->output()->writeln('Starting card import (this may take several minutes)...');
    do {
      $progress = $this->importer->getProgress();
      $this->output()->writeln(sprintf(
        '  Processing batch from offset %d / %d (%s%%)',
        $progress['offset'],
        $progress['total'],
        $progress['percent'],
      ));
      $more = $this->importer->importNextBatch();
    } while ($more);

    $this->importer->finalise();
    $this->output()->writeln('Scryfall sync complete.');
  }

  /**
   * Processes a single import batch and exits.
   *
   * Ideal for cron-driven incremental import or manual step-through. Call
   * repeatedly until it reports "Import complete." Each call processes
   * up to 200 cards and persists the offset in Drupal State so the next
   * call resumes from where this one left off.
   *
   * @command mtg:scryfall-batch
   * @aliases mtg-batch
   * @usage ddev drush mtg:scryfall-batch
   */
  public function batch(): void {
    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run mtg:scryfall-download first.');
      return;
    }

    $more = $this->importer->importNextBatch();
    $progress = $this->importer->getProgress();

    $this->output()->writeln(sprintf(
      'Batch complete. Progress: %d / %d cards processed (%s%%).',
      $progress['offset'],
      $progress['total'],
      $progress['percent'],
    ));

    if (!$more) {
      $this->importer->finalise();
      $this->output()->writeln('Import complete. All cards have been processed.');
    }
    else {
      $this->output()->writeln('Run again to process the next batch.');
    }
  }

  /**
   * Shows the current Scryfall import progress.
   *
   * @command mtg:scryfall-status
   * @aliases mtg-status
   * @usage ddev drush mtg:scryfall-status
   */
  public function status(): void {
    if (!$this->importer->dataFileExists()) {
      $this->output()->writeln('No data file found. Run mtg:scryfall-download first.');
      return;
    }

    $progress = $this->importer->getProgress();
    $this->output()->writeln(sprintf(
      'Import progress: %d / %d cards processed (%s%%).',
      $progress['offset'],
      $progress['total'],
      $progress['percent'],
    ));

    if ($progress['total'] > 0 && $progress['offset'] >= $progress['total']) {
      $this->output()->writeln('Status: complete.');
    }
    elseif ($progress['offset'] === 0) {
      $this->output()->writeln('Status: not started.');
    }
    else {
      $this->output()->writeln('Status: in progress.');
    }
  }

  /**
   * Resets the import progress so the next batch starts from the beginning.
   *
   * Does not delete the downloaded data file.
   *
   * @command mtg:scryfall-reset
   * @aliases mtg-reset
   * @usage ddev drush mtg:scryfall-reset
   */
  public function reset(): void {
    $this->importer->resetProgress();
    $this->output()->writeln('Import progress reset. The next batch will start from the beginning.');
  }

  /**
   * Imports all cards from a single Scryfall set and refreshes legalities.
   *
   * Fetches ~200-300 cards for the given set via the Scryfall search API
   * (no bulk file download) then runs a legality refresh pass over all
   * printings of every card name added or updated.
   *
   * @param string $setCode
   *   Scryfall set code, e.g. "mh3" or "dsk".
   * @param array<string, mixed> $options
   *   Drush option bag. Supported key: skip-legality.
   *
   * @command mtg:import-set
   * @aliases mtg-set
   * @usage ddev drush mtg:import-set mh3
   * @usage ddev drush mtg:import-set dsk --skip-legality
   *
   * @option skip-legality Skip the legality refresh pass.
   */
  public function importSet(string $setCode, array $options = ['skip-legality' => FALSE]): void {
    $setCode = strtolower(trim($setCode));
    if ($setCode === '') {
      $this->logger()->error('Set code is required.');
      return;
    }

    $this->output()->writeln(sprintf('Importing set "%s" from Scryfall...', $setCode));

    try {
      $result = $this->importer->importSet($setCode);
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Import failed: @msg', ['@msg' => $e->getMessage()]);
      return;
    }

    $this->output()->writeln(sprintf(
      'Set import complete: %d cards added, %d updated.',
      $result['added'],
      $result['updated'],
    ));

    if (!$options['skip-legality'] && $result['names'] !== []) {
      $this->output()->writeln(sprintf(
        'Running legality refresh for %d unique card names...',
        count($result['names']),
      ));
      $refreshed = $this->importer->refreshLegalitiesByName($result['names']);
      $this->output()->writeln(sprintf('Legality refresh complete: %d nodes updated.', $refreshed));
    }
  }

  /**
   * Syncs mtg_set taxonomy terms from card set codes/names.
   *
   * @command mtg:sync-sets
   * @option backfill Also attach field_set on cards missing the term reference.
   * @usage ddev drush mtg:sync-sets
   * @usage ddev drush mtg:sync-sets --backfill
   */
  public function syncSets(array $options = ['backfill' => FALSE]): void {
    $this->output()->writeln('Syncing MTG set taxonomy from cards...');
    $result = $this->setTaxonomy->syncFromCards();
    $this->output()->writeln(sprintf(
      'Sets: %d distinct codes, %d terms created, %d renamed.',
      $result['total'],
      $result['created'],
      $result['updated'],
    ));

    if (!empty($options['backfill'])) {
      $total = 0;
      do {
        $n = $this->setTaxonomy->backfillCardReferences(500);
        $total += $n;
        if ($n > 0) {
          $this->output()->writeln(sprintf('  Linked %d cards (running total %d)...', $n, $total));
        }
      } while ($n > 0);
      $this->output()->writeln(sprintf('Backfill complete: %d cards linked.', $total));
    }
  }

  /**
   * Backfills full-art and border-color fields from the local bulk file.
   *
   * Needed once after those fields were added; the Full art printing filter
   * stays empty until cards have these values.
   *
   * @command mtg:backfill-art
   * @aliases mtg-art
   * @usage ddev drush mtg:backfill-art
   */
  public function backfillArt(): void {
    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run mtg:scryfall-download first.');
      return;
    }

    $this->output()->writeln('Backfilling full-art and border-color from the local Scryfall file...');
    try {
      $result = $this->importer->backfillArtFields();
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Backfill failed: @msg', ['@msg' => $e->getMessage()]);
      return;
    }

    $this->output()->writeln(sprintf(
      'Art backfill complete: %d cards written, %d bulk rows unmatched.',
      $result['updated'],
      $result['skipped'],
    ));
  }

  /**
   * Backfills legal and restricted formats from the local bulk file.
   *
   * Restricted cards become playable in field_legal_formats and listed in
   * field_restricted_formats so Vintage-style one-copy rules can be enforced.
   *
   * @command mtg:backfill-legalities
   * @aliases mtg-legal
   * @usage ddev drush mtg:backfill-legalities
   */
  public function backfillLegalities(): void {
    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run mtg:scryfall-download first.');
      return;
    }

    $this->output()->writeln('Backfilling legal and restricted formats from the local Scryfall file...');
    try {
      $result = $this->importer->backfillLegalities();
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Backfill failed: @msg', ['@msg' => $e->getMessage()]);
      return;
    }

    $this->output()->writeln(sprintf(
      'Legality backfill complete: %d cards written, %d bulk rows unmatched.',
      $result['updated'],
      $result['skipped'],
    ));
  }

  /**
   * Imports tokens and emblems from the local bulk file.
   *
   * Earlier syncs skipped tokens. This imports only token layouts, so it runs
   * in minutes; later full syncs keep them up to date.
   *
   * @command mtg:import-tokens
   * @aliases mtg-tokens
   * @usage ddev drush mtg:import-tokens
   */
  public function importTokens(): void {
    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run mtg:scryfall-download first.');
      return;
    }
    $this->output()->writeln('Importing tokens and emblems from the local Scryfall file...');
    try {
      $result = $this->importer->importTokens();
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Token import failed: @msg', ['@msg' => $e->getMessage()]);
      return;
    }
    $this->output()->writeln(sprintf(
      'Token import complete: %d added, %d updated.',
      $result['added'],
      $result['updated'],
    ));
  }

  /**
   * Refreshes card prices from the Scryfall bulk file.
   *
   * Writes prices directly instead of saving every card, so it takes minutes
   * instead of the hours a full sync needs. New cards still need a full sync.
   *
   * @param array $options
   *   Command options.
   *
   * @command mtg:refresh-prices
   * @aliases mtg-prices
   * @option download Download a fresh bulk file first.
   * @usage ddev drush mtg:refresh-prices --download
   */
  public function refreshPrices(array $options = ['download' => FALSE]): void {
    if ($options['download']) {
      $this->output()->writeln('Downloading Scryfall bulk data...');
      $this->importer->downloadBulkData();
    }
    if (!$this->importer->dataFileExists()) {
      $this->logger()->error('No data file found. Run with --download or mtg:scryfall-download first.');
      return;
    }
    $this->output()->writeln('Refreshing prices from the local Scryfall file...');
    try {
      $result = $this->importer->refreshPrices();
    }
    catch (\RuntimeException $e) {
      $this->logger()->error('Price refresh failed: @msg', ['@msg' => $e->getMessage()]);
      return;
    }
    $this->output()->writeln(sprintf(
      'Price refresh complete: %d cards written, %d bulk rows unmatched.',
      $result['updated'],
      $result['skipped'],
    ));
  }

}
