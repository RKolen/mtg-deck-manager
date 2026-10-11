<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Database\Query\SelectInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use GraphQL\Error\UserError;

/**
 * Card pools for the land base suggester and the random deck generator.
 *
 * Returns one printing per card name together with how many copies are
 * owned, how many are in the trade binder and which other decks already use
 * the card. Free copies are worked out by the client, so the "include cards
 * used in other decks" toggle needs no extra round trip.
 */
final class DeckBuildPool {

  /**
   * Pool source: only cards in the collection.
   */
  public const SOURCE_COLLECTION = 'COLLECTION';

  /**
   * Pool source: every card in the database (lands only).
   */
  public const SOURCE_CARDBASE = 'CARDBASE';

  /**
   * Colour identity letters accepted in filters.
   */
  private const COLORS = ['W', 'U', 'B', 'R', 'G'];

  /**
   * Constructs a DeckBuildPool.
   *
   * @param \Drupal\Core\Entity\EntityTypeManagerInterface $entityTypeManager
   *   The entity type manager.
   * @param \Drupal\Core\Database\Connection $database
   *   The database connection.
   */
  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly Connection $database,
  ) {}

  /**
   * Builds the pool.
   *
   * @param array<string, mixed> $args
   *   Keys: source, lands, legalIn, colorIdentity, excludeDeckId.
   *
   * @return array<int, array{card: \Drupal\node\NodeInterface, owned: int, trade: int, usedIn: array<int, array{deckId: string, deckTitle: string, quantity: int}>}>
   *   One entry per card name, sorted by name.
   *
   * @throws \GraphQL\Error\UserError
   *   When the source is unknown, or the cardbase is asked for non-lands.
   */
  public function pool(array $args): array {
    $source = strtoupper((string) ($args['source'] ?? ''));
    if (!in_array($source, [self::SOURCE_COLLECTION, self::SOURCE_CARDBASE], TRUE)) {
      throw new UserError('source must be COLLECTION or CARDBASE.');
    }
    $lands = isset($args['lands']) ? (bool) $args['lands'] : NULL;
    if ($source === self::SOURCE_CARDBASE && $lands !== TRUE) {
      throw new UserError('The cardbase pool is limited to lands (lands: true).');
    }

    $owned = $this->ownedByTitle();
    $nids = $this->candidateNids(
      $source,
      $lands === TRUE,
      trim((string) ($args['legalIn'] ?? '')),
      isset($args['colorIdentity']) ? $this->sanitizeColors((array) $args['colorIdentity']) : NULL,
      array_keys($owned),
    );
    if ($nids === []) {
      return [];
    }

    $usage = $this->usageByTitle(isset($args['excludeDeckId']) ? (string) $args['excludeDeckId'] : NULL);
    $result = [];
    foreach ($this->entityTypeManager->getStorage('node')->loadMultiple($nids) as $card) {
      if (!$card instanceof NodeInterface) {
        continue;
      }
      // Only the front face decides: a creature with a land back face is a
      // spell for deck building purposes.
      $typeLine = explode(' // ', (string) ($card->get('field_type_line')->value ?? ''))[0];
      $isLand = preg_match('/\bland\b/i', $typeLine) === 1;
      if ($lands !== NULL && $isLand !== $lands) {
        continue;
      }
      $title = $card->getTitle();
      $result[] = [
        'card' => $card,
        'owned' => $owned[$title]['owned'] ?? 0,
        'trade' => $owned[$title]['trade'] ?? 0,
        'usedIn' => $usage[$title] ?? [],
      ];
    }
    usort($result, static fn(array $a, array $b): int => strcmp($a['card']->getTitle(), $b['card']->getTitle()));
    return $result;
  }

  /**
   * Picks one printing nid per card name matching the filters.
   *
   * Owned printings win, so the suggested printing is one already in the
   * collection whenever possible.
   *
   * @param string $source
   *   One of the SOURCE_* constants.
   * @param bool $landsOnly
   *   Whether to keep only cards whose type line mentions Land.
   * @param string $legalIn
   *   Scryfall legality key, or an empty string for no legality filter.
   * @param string[]|null $colorIdentity
   *   Allowed colour identity, or NULL for no filter.
   * @param string[] $ownedTitles
   *   Card names in the collection.
   *
   * @return int[]
   *   Card node IDs.
   */
  private function candidateNids(string $source, bool $landsOnly, string $legalIn, ?array $colorIdentity, array $ownedTitles): array {
    if ($source === self::SOURCE_COLLECTION && $ownedTitles === []) {
      return [];
    }

    $query = $this->database->select('node_field_data', 'c');
    $query->addField('c', 'title');
    $query->addExpression('MIN(c.nid)', 'nid');
    $query->condition('c.type', 'mtg_card');
    $query->condition('c.status', 1);
    $query->join('node__field_type_line', 't', 't.entity_id = c.nid');
    $query->condition('t.field_type_line_value', 'Token%', 'NOT LIKE');
    $query->condition('t.field_type_line_value', 'Emblem%', 'NOT LIKE');
    if ($landsOnly) {
      $query->condition('t.field_type_line_value', '%Land%', 'LIKE');
    }
    if ($source === self::SOURCE_COLLECTION) {
      $query->condition('c.title', $ownedTitles, 'IN');
    }
    $this->applyLegality($query, $legalIn);
    $this->applyColorIdentity($query, $colorIdentity);
    $query->groupBy('c.title');
    $byTitle = $query->execute()->fetchAllKeyed();

    // Swap in an owned printing where there is one.
    $ownedPrintings = $this->ownedPrintingByTitle(array_keys($byTitle));
    foreach ($ownedPrintings as $title => $nid) {
      $byTitle[$title] = $nid;
    }
    return array_map('intval', array_values($byTitle));
  }

  /**
   * Keeps only cards legal in the given format.
   */
  private function applyLegality(SelectInterface $query, string $legalIn): void {
    if ($legalIn === '') {
      return;
    }
    $legal = $this->database->select('node__field_legal_formats', 'lf')
      ->fields('lf', ['entity_id'])
      ->condition('lf.field_legal_formats_value', $legalIn);
    $query->condition('c.nid', $legal, 'IN');
  }

  /**
   * Keeps only cards whose colour identity fits inside the allowed colours.
   *
   * @param \Drupal\Core\Database\Query\SelectInterface $query
   *   The candidate query.
   * @param string[]|null $allowed
   *   Allowed colours, or NULL for no filter.
   */
  private function applyColorIdentity(SelectInterface $query, ?array $allowed): void {
    if ($allowed === NULL) {
      return;
    }
    $outside = $this->database->select('node__field_color_identity', 'ci')
      ->fields('ci', ['entity_id']);
    if ($allowed !== []) {
      $outside->condition('ci.field_color_identity_value', $allowed, 'NOT IN');
    }
    $query->condition('c.nid', $outside, 'NOT IN');
  }

  /**
   * Owned and trade copies per card name (all printings and finishes).
   *
   * @return array<string, array{owned: int, trade: int}>
   *   Keyed by card name; only names with at least one copy.
   */
  private function ownedByTitle(): array {
    $query = $this->database->select('node__field_card', 'fc');
    $query->join('node_field_data', 'cc', "cc.nid = fc.entity_id AND cc.type = 'collection_card'");
    $query->join('node_field_data', 'c', 'c.nid = fc.field_card_target_id');
    $query->leftJoin('node__field_quantity_owned', 'q', 'q.entity_id = cc.nid');
    $query->leftJoin('node__field_quantity_foil', 'f', 'f.entity_id = cc.nid');
    $query->leftJoin('node__field_quantity_trade', 'tr', 'tr.entity_id = cc.nid');
    $query->addField('c', 'title');
    $query->addExpression('SUM(COALESCE(q.field_quantity_owned_value, 0) + COALESCE(f.field_quantity_foil_value, 0))', 'owned');
    $query->addExpression('SUM(COALESCE(tr.field_quantity_trade_value, 0))', 'trade');
    $query->groupBy('c.title');

    $result = [];
    foreach ($query->execute() as $row) {
      $owned = (int) $row->owned;
      if ($owned > 0) {
        $result[(string) $row->title] = [
          'owned' => $owned,
          'trade' => min($owned, (int) $row->trade),
        ];
      }
    }
    return $result;
  }

  /**
   * The most-owned printing per card name.
   *
   * @param string[] $titles
   *   Card names to look up.
   *
   * @return array<string, int>
   *   Card node ID keyed by card name; names with no owned printing are
   *   left out.
   */
  private function ownedPrintingByTitle(array $titles): array {
    if ($titles === []) {
      return [];
    }
    $result = [];
    foreach (array_chunk($titles, 1000) as $chunk) {
      $query = $this->database->select('node__field_card', 'fc');
      $query->join('node_field_data', 'cc', "cc.nid = fc.entity_id AND cc.type = 'collection_card'");
      $query->join('node_field_data', 'c', 'c.nid = fc.field_card_target_id');
      $query->leftJoin('node__field_quantity_owned', 'q', 'q.entity_id = cc.nid');
      $query->leftJoin('node__field_quantity_foil', 'f', 'f.entity_id = cc.nid');
      $query->addField('c', 'title');
      $query->addField('c', 'nid');
      $query->addExpression('COALESCE(q.field_quantity_owned_value, 0) + COALESCE(f.field_quantity_foil_value, 0)', 'copies');
      $query->condition('c.title', $chunk, 'IN');
      $query->orderBy('copies', 'DESC');
      $query->orderBy('c.nid');
      foreach ($query->execute() as $row) {
        $title = (string) $row->title;
        if ((int) $row->copies > 0 && !isset($result[$title])) {
          $result[$title] = (int) $row->nid;
        }
      }
    }
    return $result;
  }

  /**
   * Copies of each card name used in decks other than the excluded one.
   *
   * Main decks, sideboards and commanders count; maybeboards do not.
   *
   * @param string|null $excludeDeckUuid
   *   UUID of the deck being built, or NULL.
   *
   * @return array<string, array<int, array{deckId: string, deckTitle: string, quantity: int}>>
   *   Uses keyed by card name.
   */
  private function usageByTitle(?string $excludeDeckUuid): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $deckIds = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'deck')
      ->execute();

    $usage = [];
    foreach ($storage->loadMultiple($deckIds) as $deck) {
      if (!$deck instanceof NodeInterface || $deck->uuid() === $excludeDeckUuid) {
        continue;
      }
      $counts = [];
      foreach ($deck->get('field_deck_cards')->referencedEntities() as $slot) {
        $card = $slot->get('field_card')->entity;
        if ($card instanceof NodeInterface) {
          $title = $card->getTitle();
          $counts[$title] = ($counts[$title] ?? 0) + max(1, (int) ($slot->get('field_quantity')->value ?? 1));
        }
      }
      $commander = $deck->hasField('field_commander') ? $deck->get('field_commander')->entity : NULL;
      if ($commander instanceof NodeInterface) {
        $title = $commander->getTitle();
        $counts[$title] = ($counts[$title] ?? 0) + 1;
      }
      foreach ($counts as $title => $quantity) {
        $usage[$title][] = [
          'deckId' => (string) $deck->uuid(),
          'deckTitle' => $deck->getTitle(),
          'quantity' => $quantity,
        ];
      }
    }
    return $usage;
  }

  /**
   * Decks with main deck or sideboard cards the collection does not cover.
   *
   * Ownership is by card name: any printing and finish counts. Copies in
   * other decks are not subtracted; this is about cards not owned at all.
   *
   * @return array<int, array{deckId: string, deckTitle: string, format: string, cards: array<int, array{card: \Drupal\node\NodeInterface, needed: int, owned: int, wished: int, priceEur: float|null, priceUsd: float|null}>}>
   *   Decks with at least one missing copy, sorted by title.
   */
  public function shortfalls(): array {
    $owned = $this->ownedByTitle();
    $wished = $this->wishedByDeckAndTitle();
    $storage = $this->entityTypeManager->getStorage('node');
    $deckIds = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'deck')
      ->sort('title')
      ->execute();

    $result = [];
    foreach ($storage->loadMultiple($deckIds) as $deck) {
      if (!$deck instanceof NodeInterface) {
        continue;
      }
      $needed = [];
      $cards = [];
      foreach ($deck->get('field_deck_cards')->referencedEntities() as $slot) {
        $card = $slot->get('field_card')->entity;
        if (!$card instanceof NodeInterface) {
          continue;
        }
        $title = $card->getTitle();
        $needed[$title] = ($needed[$title] ?? 0) + max(1, (int) ($slot->get('field_quantity')->value ?? 1));
        $cards[$title] ??= $card;
      }
      $missing = [];
      foreach ($needed as $title => $quantity) {
        $have = $owned[$title]['owned'] ?? 0;
        if ($have < $quantity) {
          $missing[] = [
            'card' => $cards[$title],
            'needed' => $quantity,
            'owned' => $have,
            'wished' => $wished[(int) $deck->id()][$title] ?? 0,
          ];
        }
      }
      if ($missing !== []) {
        $cheapest = $this->cheapestByTitle(array_map(static fn(array $m): string => $m['card']->getTitle(), $missing));
        foreach ($missing as &$m) {
          $m += $cheapest[$m['card']->getTitle()] ?? ['priceEur' => NULL, 'priceUsd' => NULL];
        }
        unset($m);
        usort($missing, static fn(array $a, array $b): int => strcmp($a['card']->getTitle(), $b['card']->getTitle()));
        $result[] = [
          'deckId' => (string) $deck->uuid(),
          'deckTitle' => $deck->getTitle(),
          'format' => (string) ($deck->get('field_format')->value ?? ''),
          'cards' => $missing,
        ];
      }
    }
    return $result;
  }

  /**
   * Cheapest regular price of any printing, per card name.
   *
   * Deck needs are wished as any printing, so this matches the wishlist.
   *
   * @param string[] $titles
   *   Card names.
   *
   * @return array<string, array{priceEur: float|null, priceUsd: float|null}>
   *   Prices keyed by card name.
   */
  private function cheapestByTitle(array $titles): array {
    if ($titles === []) {
      return [];
    }
    $query = $this->database->select('node_field_data', 'c');
    $query->leftJoin('node__field_price_eur', 'e', 'e.entity_id = c.nid AND e.field_price_eur_value > 0');
    $query->leftJoin('node__field_price_usd', 'u', 'u.entity_id = c.nid AND u.field_price_usd_value > 0');
    $query->addField('c', 'title');
    $query->addExpression('MIN(e.field_price_eur_value)', 'eur');
    $query->addExpression('MIN(u.field_price_usd_value)', 'usd');
    $query->condition('c.type', 'mtg_card');
    $query->condition('c.title', array_values(array_unique($titles)), 'IN');
    $query->groupBy('c.title');

    $result = [];
    foreach ($query->execute() as $row) {
      $result[(string) $row->title] = [
        'priceEur' => $row->eur !== NULL ? (float) $row->eur : NULL,
        'priceUsd' => $row->usd !== NULL ? (float) $row->usd : NULL,
      ];
    }
    return $result;
  }

  /**
   * Largest wished quantity per deck and card name.
   *
   * @return array<int, array<string, int>>
   *   Quantities keyed by deck node ID, then card name.
   */
  private function wishedByDeckAndTitle(): array {
    $query = $this->database->select('node__field_wish_deck', 'wd');
    $query->join('node__field_card', 'fc', 'fc.entity_id = wd.entity_id');
    $query->join('node_field_data', 'c', 'c.nid = fc.field_card_target_id');
    $query->leftJoin('node__field_wish_quantity', 'q', 'q.entity_id = wd.entity_id');
    $query->addField('wd', 'field_wish_deck_target_id', 'deck');
    $query->addField('c', 'title');
    $query->addExpression('MAX(COALESCE(q.field_wish_quantity_value, 1))', 'quantity');
    $query->condition('wd.bundle', 'wishlist_item');
    $query->groupBy('wd.field_wish_deck_target_id');
    $query->groupBy('c.title');

    $result = [];
    foreach ($query->execute() as $row) {
      $result[(int) $row->deck][(string) $row->title] = (int) $row->quantity;
    }
    return $result;
  }

  /**
   * Keeps only valid, unique colour letters.
   *
   * @param array<int, mixed> $colors
   *   Raw colour letters.
   *
   * @return string[]
   *   Upper-case colour letters.
   */
  private function sanitizeColors(array $colors): array {
    $clean = array_map(static fn($c): string => strtoupper(trim((string) $c)), $colors);
    return array_values(array_unique(array_intersect($clean, self::COLORS)));
  }

}
