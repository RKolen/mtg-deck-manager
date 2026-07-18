<?php

declare(strict_types=1);

namespace Drupal\mtg_card_images\Commands;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Queue\QueueFactory;
use Drupal\mtg_card_images\CardImageFetcher;
use Drupal\node\NodeInterface;
use Drush\Commands\DrushCommands;

/**
 * Drush commands to enqueue and process local Scryfall card art.
 */
final class CardImageCommands extends DrushCommands {

  public function __construct(
    private readonly CardImageFetcher $fetcher,
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly QueueFactory $queueFactory,
  ) {
    parent::__construct();
  }

  /**
   * Enqueues cards that still need a local Scryfall image cache.
   *
   * @command mtg:card-images-enqueue
   * @aliases mtg-img-enq
   * @option deck Deck node ID — enqueue every card referenced by that deck.
   * @option all Enqueue all mtg_card nodes missing local art (use with --limit).
   * @option limit Max cards to enqueue when using --all (default 500).
   * @option nids Comma-separated mtg_card nids.
   * @usage ddev drush mtg:card-images-enqueue --deck=123
   * @usage ddev drush mtg:card-images-enqueue --all --limit=200
   */
  public function enqueue(
    array $options = [
      'deck' => NULL,
      'all' => FALSE,
      'limit' => 500,
      'nids' => NULL,
    ],
  ): void {
    $nids = [];

    if (!empty($options['nids'])) {
      foreach (explode(',', (string) $options['nids']) as $raw) {
        $nid = (int) trim($raw);
        if ($nid > 0) {
          $nids[] = $nid;
        }
      }
    }

    if (!empty($options['deck'])) {
      $deck = $this->entityTypeManager->getStorage('node')->load((int) $options['deck']);
      if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
        $this->logger()->error('Deck @id not found.', ['@id' => $options['deck']]);
        return;
      }
      if ($deck->hasField('field_deck_cards')) {
        foreach ($deck->get('field_deck_cards') as $item) {
          $paragraph = $item->entity;
          if ($paragraph && $paragraph->hasField('field_card') && !$paragraph->get('field_card')->isEmpty()) {
            $card = $paragraph->get('field_card')->entity;
            if ($card instanceof NodeInterface) {
              $nids[] = (int) $card->id();
            }
          }
        }
      }
    }

    if (!empty($options['all'])) {
      $limit = max(1, (int) $options['limit']);
      $query = $this->entityTypeManager->getStorage('node')->getQuery()
        ->accessCheck(FALSE)
        ->condition('type', 'mtg_card')
        ->condition('status', 1)
        ->notExists(CardImageFetcher::FIELD_LOCAL)
        ->condition('field_image_uri', 'https://cards.scryfall.io/', 'STARTS_WITH')
        ->range(0, $limit)
        ->sort('nid', 'DESC');
      $nids = array_merge($nids, array_map('intval', $query->execute()));
    }

    $nids = array_values(array_unique($nids));
    if ($nids === []) {
      $this->output()->writeln('No cards to enqueue. Pass --deck, --nids, or --all.');
      return;
    }

    $queued = $this->fetcher->enqueueNids($nids);
    $depth = $this->queueFactory->get(CardImageFetcher::QUEUE_ID)->numberOfItems();
    $this->output()->writeln(sprintf(
      'Enqueued %d card(s). Queue depth: %d. Run: ddev drush mtg:card-images-process',
      $queued,
      $depth,
    ));
  }

  /**
   * Processes pending card image downloads from the queue.
   *
   * @command mtg:card-images-process
   * @aliases mtg-img-run
   * @option limit Max items to process this run (default 100).
   * @usage ddev drush mtg:card-images-process --limit=50
   */
  public function process(array $options = ['limit' => 100]): void {
    $limit = max(1, (int) $options['limit']);
    $queue = $this->queueFactory->get(CardImageFetcher::QUEUE_ID);
    $ok = 0;
    $fail = 0;
    for ($i = 0; $i < $limit; $i++) {
      $item = $queue->claimItem(120);
      if (!$item) {
        break;
      }
      $nid = (int) ($item->data['nid'] ?? 0);
      try {
        if ($nid > 0 && $this->fetcher->fetchNode($nid)) {
          $ok++;
        }
        else {
          $fail++;
        }
        $queue->deleteItem($item);
      }
      catch (\Throwable $e) {
        $fail++;
        $queue->releaseItem($item);
        $this->logger()->error('Fetch failed for nid @nid: @m', [
          '@nid' => $nid,
          '@m' => $e->getMessage(),
        ]);
      }
    }
    $this->output()->writeln(sprintf(
      'Processed images: %d ok, %d failed/skipped. Remaining in queue: %d',
      $ok,
      $fail,
      $queue->numberOfItems(),
    ));
  }

}
