<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Commands;

use Drupal\mtg_scryfall_sync\ScryfallImporter;
use Drush\Commands\DrushCommands;

/**
 * Drush commands for the MTG Scryfall Sync module.
 */
class ScryfallCommands extends DrushCommands {

  public function __construct(
    private readonly ScryfallImporter $importer,
  ) {
    parent::__construct();
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

}
