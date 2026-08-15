<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Commands;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\mtg_graphql\Service\CollectionEnsurer;
use Drupal\node\NodeInterface;
use Drush\Commands\DrushCommands;

/**
 * Drush commands for keeping the collection in sync with decks.
 */
final class CollectionCommands extends DrushCommands {

  public function __construct(
    private readonly CollectionEnsurer $ensurer,
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {
    parent::__construct();
  }

  /**
   * Ensures every card used in any deck exists in the collection.
   *
   * Owned quantity is set to at least the max copies of that card in any
   * single deck (main + sideboard combined). Existing higher quantities
   * are left unchanged.
   *
   * @command mtg:collection-from-decks
   * @aliases mtg-col-decks
   * @usage ddev drush mtg:collection-from-decks
   */
  public function fromDecks(): void {
    $this->output()->writeln('Syncing collection from all decks...');
    $result = $this->ensurer->backfillFromAllDecks();
    $this->output()->writeln(sprintf(
      'Done. Decks scanned: %d. Distinct cards ensured: %d.',
      $result['decks'],
      $result['ensured'],
    ));
  }

  /**
   * Marks a deck as foil and moves its collection copies to foil qty.
   *
   * @param int $nid
   *   Deck node ID.
   *
   * @command mtg:collection-deck-foil
   * @usage ddev drush mtg:collection-deck-foil 108404
   */
  public function deckFoil(int $nid): void {
    $storage = $this->entityTypeManager->getStorage('node');
    $deck = $storage->load($nid);
    if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
      throw new \InvalidArgumentException("Node $nid is not a deck.");
    }
    if ($deck->hasField('field_is_foil')) {
      $deck->set('field_is_foil', TRUE);
      $deck->setNewRevision(FALSE);
      $deck->save();
      $this->output()->writeln(sprintf('Marked deck "%s" as foil.', $deck->label()));
    }
    $count = $this->ensurer->ensureDeckCardsAsFoil($deck);
    $this->output()->writeln(sprintf('Ensured foil collection qty for %d distinct cards.', $count));
  }

}
