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
   * Ensures at least $minFoil foil copies.
   *
   * Moves copies from non-foil owned when possible. Never decreases
   * total owned+foil; prefers converting owned to foil over creating
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
   * Loads the collection_card node for an mtg_card, if one exists.
   *
   * @param \Drupal\node\NodeInterface $card
   *   The mtg_card printing.
   *
   * @return \Drupal\node\NodeInterface|null
   *   The collection node, or NULL if none exists.
   */
  public function loadByCard(NodeInterface $card): ?NodeInterface {
    if ($card->bundle() !== 'mtg_card') {
      return NULL;
    }
    $storage = $this->entityTypeManager->getStorage('node');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'collection_card')
      ->condition('field_card', $card->id())
      ->range(0, 1)
      ->execute();
    if ($ids === []) {
      return NULL;
    }
    $node = $storage->load(reset($ids));
    return $node instanceof NodeInterface ? $node : NULL;
  }

  /**
   * Adds copies of a printing to the collection.
   *
   * @param \Drupal\node\NodeInterface $card
   *   The mtg_card printing.
   * @param int $qty
   *   Number of copies to add.
   * @param bool $foil
   *   TRUE to add foil copies, FALSE for regular.
   */
  public function addCopies(NodeInterface $card, int $qty, bool $foil): void {
    if ($card->bundle() !== 'mtg_card' || $qty < 1) {
      return;
    }
    $node = $this->loadByCard($card);
    if ($node === NULL) {
      $storage = $this->entityTypeManager->getStorage('node');
      $node = $storage->create([
        'type' => 'collection_card',
        'title' => $card->label(),
        'status' => 1,
        'field_card' => ['target_id' => $card->id()],
        'field_quantity_owned' => $foil ? 0 : $qty,
        'field_quantity_foil' => $foil ? $qty : 0,
      ]);
      $node->save();
      return;
    }
    if ($foil) {
      $current = (int) ($node->get('field_quantity_foil')->value ?? 0);
      $node->set('field_quantity_foil', $current + $qty);
    }
    else {
      $current = (int) ($node->get('field_quantity_owned')->value ?? 0);
      $node->set('field_quantity_owned', $current + $qty);
    }
    $node->save();
  }

  /**
   * Removes up to $qty copies from the collection for a printing.
   *
   * Prefers foil when $preferFoil is TRUE, otherwise prefers non-foil.
   * Deletes the collection node when both quantities reach zero.
   *
   * @param \Drupal\node\NodeInterface $card
   *   The mtg_card printing.
   * @param int $qty
   *   Maximum copies to remove.
   * @param bool $preferFoil
   *   TRUE to take foil copies first.
   *
   * @return int
   *   Number of copies actually removed.
   */
  public function removeCopies(NodeInterface $card, int $qty, bool $preferFoil): int {
    if ($card->bundle() !== 'mtg_card' || $qty < 1) {
      return 0;
    }
    $node = $this->loadByCard($card);
    if ($node === NULL) {
      return 0;
    }

    $owned = (int) ($node->get('field_quantity_owned')->value ?? 0);
    $foil = (int) ($node->get('field_quantity_foil')->value ?? 0);
    $removed = 0;
    $remaining = $qty;

    $first = $preferFoil ? 'foil' : 'owned';
    $second = $preferFoil ? 'owned' : 'foil';
    foreach ([$first, $second] as $pool) {
      if ($remaining < 1) {
        break;
      }
      if ($pool === 'foil') {
        $take = min($foil, $remaining);
        $foil -= $take;
      }
      else {
        $take = min($owned, $remaining);
        $owned -= $take;
      }
      $removed += $take;
      $remaining -= $take;
    }

    if ($owned < 1 && $foil < 1) {
      $node->delete();
      return $removed;
    }

    $node->set('field_quantity_owned', $owned);
    $node->set('field_quantity_foil', $foil);
    $node->save();
    return $removed;
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
   * Marks every card in a deck as foil in the collection.
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
