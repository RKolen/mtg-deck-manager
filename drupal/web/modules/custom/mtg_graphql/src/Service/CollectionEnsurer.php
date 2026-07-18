<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\paragraphs\ParagraphInterface;

/**
 * Ensures mtg_card nodes referenced by decks also exist in the collection.
 */
final class CollectionEnsurer {

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {}

  /**
   * Ensures a collection entry with at least $minTotal owned+foil copies.
   *
   * Bumps field_quantity_owned when needed; never decreases quantities.
   */
  public function ensureMinOwned(NodeInterface $card, int $minTotal): void {
    if ($card->bundle() !== 'mtg_card' || $minTotal < 1) {
      return;
    }

    $storage = $this->entityTypeManager->getStorage('node');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'collection_card')
      ->condition('field_card', $card->id())
      ->range(0, 1)
      ->execute();

    if ($ids === []) {
      $node = $storage->create([
        'type' => 'collection_card',
        'title' => $card->label(),
        'status' => 1,
        'field_card' => ['target_id' => $card->id()],
        'field_quantity_owned' => $minTotal,
        'field_quantity_foil' => 0,
      ]);
      $node->save();
      return;
    }

    /** @var \Drupal\node\NodeInterface $node */
    $node = $storage->load(reset($ids));
    if (!$node instanceof NodeInterface) {
      return;
    }

    $owned = (int) ($node->get('field_quantity_owned')->value ?? 0);
    $foil = (int) ($node->get('field_quantity_foil')->value ?? 0);
    $total = $owned + $foil;
    if ($total >= $minTotal) {
      return;
    }

    $node->set('field_quantity_owned', $owned + ($minTotal - $total));
    $node->save();
  }

  /**
   * Ensures at least $minFoil foil copies, moving from non-foil owned when possible.
   *
   * Never decreases total owned+foil; prefers converting owned → foil over creating
   * extra copies.
   */
  public function ensureMinFoil(NodeInterface $card, int $minFoil): void {
    if ($card->bundle() !== 'mtg_card' || $minFoil < 1) {
      return;
    }

    $storage = $this->entityTypeManager->getStorage('node');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'collection_card')
      ->condition('field_card', $card->id())
      ->range(0, 1)
      ->execute();

    if ($ids === []) {
      $node = $storage->create([
        'type' => 'collection_card',
        'title' => $card->label(),
        'status' => 1,
        'field_card' => ['target_id' => $card->id()],
        'field_quantity_owned' => 0,
        'field_quantity_foil' => $minFoil,
      ]);
      $node->save();
      return;
    }

    /** @var \Drupal\node\NodeInterface $node */
    $node = $storage->load(reset($ids));
    if (!$node instanceof NodeInterface) {
      return;
    }

    $owned = (int) ($node->get('field_quantity_owned')->value ?? 0);
    $foil = (int) ($node->get('field_quantity_foil')->value ?? 0);
    if ($foil >= $minFoil) {
      return;
    }

    $need = $minFoil - $foil;
    $fromOwned = min($owned, $need);
    $owned -= $fromOwned;
    $foil += $fromOwned;
    $stillNeed = $need - $fromOwned;
    if ($stillNeed > 0) {
      $foil += $stillNeed;
    }

    $node->set('field_quantity_owned', $owned);
    $node->set('field_quantity_foil', $foil);
    $node->save();
  }

  /**
   * Ensures every unique card in a deck is in the collection.
   *
   * Quantity required per card = sum of that card's copies in the deck
   * (main + sideboard).
   *
   * @return int
   *   Number of distinct cards ensured.
   */
  public function ensureDeckCards(NodeInterface $deck): int {
    if ($deck->bundle() !== 'deck' || !$deck->hasField('field_deck_cards')) {
      return 0;
    }

    $totals = [];
    $cards = [];
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $para) {
      if (!$para instanceof ParagraphInterface || !$para->hasField('field_card')) {
        continue;
      }
      if ($para->get('field_card')->isEmpty()) {
        continue;
      }
      $card = $para->get('field_card')->entity;
      if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
        continue;
      }
      $nid = (int) $card->id();
      $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
      $totals[$nid] = ($totals[$nid] ?? 0) + $qty;
      $cards[$nid] = $card;
    }

    foreach ($totals as $nid => $qty) {
      $this->ensureMinOwned($cards[$nid], $qty);
    }

    return count($totals);
  }

  /**
   * Marks every card in a deck as foil in the collection (min foil qty = deck copies).
   *
   * @return int
   *   Number of distinct cards updated/ensured as foil.
   */
  public function ensureDeckCardsAsFoil(NodeInterface $deck): int {
    if ($deck->bundle() !== 'deck' || !$deck->hasField('field_deck_cards')) {
      return 0;
    }

    $totals = [];
    $cards = [];
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $para) {
      if (!$para instanceof ParagraphInterface || !$para->hasField('field_card')) {
        continue;
      }
      if ($para->get('field_card')->isEmpty()) {
        continue;
      }
      $card = $para->get('field_card')->entity;
      if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
        continue;
      }
      $nid = (int) $card->id();
      $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
      $totals[$nid] = ($totals[$nid] ?? 0) + $qty;
      $cards[$nid] = $card;
    }

    foreach ($totals as $nid => $qty) {
      $this->ensureMinFoil($cards[$nid], $qty);
    }

    return count($totals);
  }

  /**
   * Backfills collection from every deck: required qty = max per-deck total.
   *
   * @return array{decks: int, cards: int, ensured: int}
   *   Counts for logging.
   */
  public function backfillFromAllDecks(): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $deckIds = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'deck')
      ->execute();

    $maxByCard = [];
    $cardEntities = [];
    $decks = 0;

    foreach ($storage->loadMultiple($deckIds) as $deck) {
      if (!$deck instanceof NodeInterface) {
        continue;
      }
      $decks++;
      $perDeck = [];
      foreach ($deck->get('field_deck_cards')->referencedEntities() as $para) {
        if (!$para instanceof ParagraphInterface || !$para->hasField('field_card')) {
          continue;
        }
        if ($para->get('field_card')->isEmpty()) {
          continue;
        }
        $card = $para->get('field_card')->entity;
        if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
          continue;
        }
        $nid = (int) $card->id();
        $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
        $perDeck[$nid] = ($perDeck[$nid] ?? 0) + $qty;
        $cardEntities[$nid] = $card;
      }
      foreach ($perDeck as $nid => $qty) {
        $maxByCard[$nid] = max($maxByCard[$nid] ?? 0, $qty);
      }
    }

    foreach ($maxByCard as $nid => $qty) {
      $this->ensureMinOwned($cardEntities[$nid], $qty);
    }

    return [
      'decks' => $decks,
      'cards' => count($maxByCard),
      'ensured' => count($maxByCard),
    ];
  }

}
