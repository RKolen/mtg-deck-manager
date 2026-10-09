<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityRepositoryInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;
use GraphQL\Error\UserError;

/**
 * Reads and writes wishlist_item nodes.
 *
 * A wish is for a card, either any printing of it or one exact printing,
 * optionally tied to a deck and an intent (deck need, brew, upgrade, price
 * watch). It counts as done once the collection holds enough copies. The
 * deck is set on creation only; a new deck wish also puts the card on that
 * deck's maybeboard when the deck does not run it yet.
 */
final class WishlistService {

  /**
   * Allowed minimum conditions (Cardmarket grades).
   */
  public const CONDITIONS = ['M', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'];

  /**
   * Owned counts per card title or nid, cached for the request.
   *
   * @var array<string, int>
   */
  private array $ownedCache = [];

  /**
   * Lowest regular and foil price per title or nid and currency.
   *
   * @var array<string, array{regular: float|null, foil: float|null}>
   */
  private array $priceCache = [];

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly EntityRepositoryInterface $entityRepository,
    private readonly Connection $database,
    private readonly DeckCardMutator $deckCardMutator,
  ) {}

  /**
   * Lists wishes, optionally filtered by deck and intent.
   *
   * @param string|null $deckUuid
   *   Only wishes for this deck.
   * @param string|null $intentId
   *   Only wishes with this intent term ID.
   * @param bool $includeDone
   *   Include wishes the collection already covers.
   *
   * @return \Drupal\node\NodeInterface[]
   *   Wishlist items sorted by card name.
   */
  public function items(?string $deckUuid, ?string $intentId, bool $includeDone): array {
    $query = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'wishlist_item')
      ->sort('title');
    if ($deckUuid !== NULL && $deckUuid !== '') {
      $deck = $this->entityRepository->loadEntityByUuid('node', $deckUuid);
      $query->condition('field_wish_deck', $deck instanceof NodeInterface ? $deck->id() : -1);
    }
    if ($intentId !== NULL && $intentId !== '') {
      $query->condition('field_wish_intent', (int) $intentId);
    }
    $items = $this->entityTypeManager->getStorage('node')->loadMultiple($query->execute());
    $items = array_values(array_filter($items, fn($n) => $n instanceof NodeInterface));
    if (!$includeDone) {
      $items = array_values(array_filter($items, fn(NodeInterface $n) => !$this->isDone($n)));
    }
    return $items;
  }

  /**
   * Wishes that a printing would fill (same card for any-printing wishes).
   *
   * @return \Drupal\node\NodeInterface[]
   *   Matching wishlist items.
   */
  public function itemsForCard(NodeInterface $card): array {
    $titleNids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'mtg_card')
      ->condition('title', $card->getTitle())
      ->execute();
    if ($titleNids === []) {
      return [];
    }
    $ids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'wishlist_item')
      ->condition('field_card', array_values($titleNids), 'IN')
      ->execute();
    $out = [];
    foreach ($this->entityTypeManager->getStorage('node')->loadMultiple($ids) as $item) {
      if (!$item instanceof NodeInterface) {
        continue;
      }
      $exact = (int) ($item->get('field_card')->target_id ?? 0) === (int) $card->id();
      if ($exact || $this->anyPrinting($item)) {
        $out[] = $item;
      }
    }
    return $out;
  }

  /**
   * Creates or updates a wish.
   *
   * @param array<string, mixed> $args
   *   GraphQL arguments: id, cardId, quantity, anyPrinting, foil, deckId,
   *   intentId, minCondition, notes.
   *
   * @throws \GraphQL\Error\UserError
   *   When the card, deck, intent or condition is invalid.
   */
  public function save(array $args): NodeInterface {
    $storage = $this->entityTypeManager->getStorage('node');
    $item = NULL;
    if (!empty($args['id'])) {
      $item = $this->entityRepository->loadEntityByUuid('node', (string) $args['id']);
      if (!$item instanceof NodeInterface || $item->bundle() !== 'wishlist_item') {
        throw new UserError('Wishlist item not found.');
      }
    }
    $card = $this->entityRepository->loadEntityByUuid('node', (string) $args['cardId']);
    if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
      throw new UserError('Card not found.');
    }
    $isNew = !$item instanceof NodeInterface;
    if ($isNew) {
      $item = $storage->create(['type' => 'wishlist_item', 'status' => 1]);
    }

    $item->setTitle($card->getTitle());
    $item->set('field_card', ['target_id' => $card->id()]);
    $item->set('field_wish_quantity', max(1, (int) ($args['quantity'] ?? 1)));
    if (array_key_exists('anyPrinting', $args) && $args['anyPrinting'] !== NULL) {
      $item->set('field_any_printing', (bool) $args['anyPrinting']);
    }
    if (array_key_exists('foil', $args) && $args['foil'] !== NULL) {
      $item->set('field_is_foil', (bool) $args['foil']);
    }
    // The deck is fixed when the wish is created, so the list always shows
    // the deck the card was wished for.
    $deck = NULL;
    if ($isNew && array_key_exists('deckId', $args)) {
      $deckRef = $this->deckReference($args['deckId']);
      $item->set('field_wish_deck', $deckRef);
      $deck = $deckRef === NULL ? NULL : $storage->load($deckRef['target_id']);
    }
    if (array_key_exists('intentId', $args)) {
      $item->set('field_wish_intent', $this->intentReference($args['intentId']));
    }
    if (array_key_exists('minCondition', $args)) {
      $condition = strtoupper(trim((string) ($args['minCondition'] ?? '')));
      if ($condition !== '' && !in_array($condition, self::CONDITIONS, TRUE)) {
        throw new UserError('Unknown condition "' . $condition . '".');
      }
      $item->set('field_min_condition', $condition === '' ? NULL : $condition);
    }
    if (array_key_exists('notes', $args)) {
      $notes = trim((string) ($args['notes'] ?? ''));
      $item->set('field_notes', $notes === '' ? NULL : ['value' => $notes, 'format' => 'plain_text']);
    }
    $item->save();

    if ($deck instanceof NodeInterface && !$this->deckHasCard($deck, $card->getTitle())) {
      $this->deckCardMutator->add(
        $deck->uuid(),
        $card->uuid(),
        max(1, (int) ($args['quantity'] ?? 1)),
        FALSE,
        (bool) ($args['foil'] ?? FALSE),
        'maybe',
      );
    }
    return $item;
  }

  /**
   * Whether a deck runs a card by name on any board.
   */
  private function deckHasCard(NodeInterface $deck, string $title): bool {
    foreach ([DeckCardMutator::DECK_FIELD, DeckCardMutator::MAYBE_FIELD] as $field) {
      if (!$deck->hasField($field)) {
        continue;
      }
      foreach ($deck->get($field)->referencedEntities() as $slot) {
        $card = $slot->get('field_card')->entity;
        if ($card instanceof NodeInterface && $card->getTitle() === $title) {
          return TRUE;
        }
      }
    }
    $commander = $deck->hasField('field_commander') ? $deck->get('field_commander')->entity : NULL;
    return $commander instanceof NodeInterface && $commander->getTitle() === $title;
  }

  /**
   * Deletes a wish.
   */
  public function delete(string $uuid): bool {
    $item = $this->entityRepository->loadEntityByUuid('node', $uuid);
    if (!$item instanceof NodeInterface || $item->bundle() !== 'wishlist_item') {
      return FALSE;
    }
    $item->delete();
    return TRUE;
  }

  /**
   * All wish intent terms, in weight order.
   *
   * @return \Drupal\taxonomy\TermInterface[]
   *   Intent terms.
   */
  public function intents(): array {
    $storage = $this->entityTypeManager->getStorage('taxonomy_term');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('vid', 'wish_intent')
      ->sort('weight')
      ->sort('name')
      ->execute();
    return array_values(array_filter(
      $storage->loadMultiple($ids),
      fn($t) => $t instanceof TermInterface,
    ));
  }

  /**
   * Copies in the collection that count toward a wish.
   *
   * Any-printing wishes count every printing of the card; exact wishes only
   * that printing. Foil wishes count foil copies only.
   */
  public function owned(NodeInterface $item): int {
    $card = $item->get('field_card')->entity;
    if (!$card instanceof NodeInterface) {
      return 0;
    }
    $foil = (int) ($item->get('field_is_foil')->value ?? 0) === 1;
    $any = $this->anyPrinting($item);
    $key = ($any ? 't:' . $card->getTitle() : 'n:' . $card->id()) . ($foil ? ':f' : '');
    if (isset($this->ownedCache[$key])) {
      return $this->ownedCache[$key];
    }
    $query = $this->database->select('node__field_card', 'fc');
    $query->join('node_field_data', 'cc', "cc.nid = fc.entity_id AND cc.type = 'collection_card'");
    $query->join('node_field_data', 'c', 'c.nid = fc.field_card_target_id');
    $query->leftJoin('node__field_quantity_foil', 'f', 'f.entity_id = cc.nid');
    $query->addExpression('SUM(COALESCE(f.field_quantity_foil_value, 0))', 'foil');
    if (!$foil) {
      $query->leftJoin('node__field_quantity_owned', 'q', 'q.entity_id = cc.nid');
      $query->addExpression('SUM(COALESCE(q.field_quantity_owned_value, 0))', 'owned');
    }
    if ($any) {
      $query->condition('c.title', $card->getTitle());
    }
    else {
      $query->condition('c.nid', $card->id());
    }
    $row = $query->execute()->fetchAssoc() ?: [];
    $count = (int) ($row['foil'] ?? 0) + (int) ($row['owned'] ?? 0);
    return $this->ownedCache[$key] = $count;
  }

  /**
   * Price of one wanted copy.
   *
   * Any-printing wishes take the cheapest priced printing of the card, exact
   * wishes that printing. Each finish falls back to the other when it has
   * no price (foil-only or regular-only printings).
   *
   * @param \Drupal\node\NodeInterface $item
   *   The wishlist item.
   * @param string $currency
   *   Either 'eur' or 'usd'.
   *
   * @return float|null
   *   The price, or NULL when no printing has one.
   */
  public function price(NodeInterface $item, string $currency): ?float {
    $card = $item->get('field_card')->entity;
    if (!$card instanceof NodeInterface || !in_array($currency, ['eur', 'usd'], TRUE)) {
      return NULL;
    }
    $foil = (int) ($item->get('field_is_foil')->value ?? 0) === 1;
    $any = $this->anyPrinting($item);
    $key = ($any ? 't:' . $card->getTitle() : 'n:' . $card->id()) . ':' . $currency;
    if (!isset($this->priceCache[$key])) {
      $query = $this->database->select('node_field_data', 'c');
      $query->leftJoin("node__field_price_$currency", 'r', 'r.entity_id = c.nid');
      $query->leftJoin("node__field_price_{$currency}_foil", 'f', 'f.entity_id = c.nid');
      $query->addExpression("MIN(NULLIF(r.field_price_{$currency}_value, 0))", 'regular');
      $query->addExpression("MIN(NULLIF(f.field_price_{$currency}_foil_value, 0))", 'foil');
      $query->condition('c.type', 'mtg_card');
      if ($any) {
        $query->condition('c.title', $card->getTitle());
      }
      else {
        $query->condition('c.nid', $card->id());
      }
      $row = $query->execute()->fetchAssoc() ?: [];
      $this->priceCache[$key] = [
        'regular' => isset($row['regular']) ? (float) $row['regular'] : NULL,
        'foil' => isset($row['foil']) ? (float) $row['foil'] : NULL,
      ];
    }
    $prices = $this->priceCache[$key];
    return $foil ? ($prices['foil'] ?? $prices['regular']) : ($prices['regular'] ?? $prices['foil']);
  }

  /**
   * Whether the collection covers the wish.
   */
  public function isDone(NodeInterface $item): bool {
    return $this->owned($item) >= max(1, (int) ($item->get('field_wish_quantity')->value ?? 1));
  }

  /**
   * Whether any printing of the card fills the wish.
   */
  public function anyPrinting(NodeInterface $item): bool {
    if ($item->get('field_any_printing')->isEmpty()) {
      return TRUE;
    }
    return (int) $item->get('field_any_printing')->value === 1;
  }

  /**
   * Builds a deck reference from a deck UUID; empty clears it.
   *
   * @return array<string, int>|null
   *   Field value.
   *
   * @throws \GraphQL\Error\UserError
   *   When the deck does not exist.
   */
  private function deckReference(mixed $deckUuid): ?array {
    $deckUuid = trim((string) ($deckUuid ?? ''));
    if ($deckUuid === '') {
      return NULL;
    }
    $deck = $this->entityRepository->loadEntityByUuid('node', $deckUuid);
    if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
      throw new UserError('Deck not found.');
    }
    return ['target_id' => (int) $deck->id()];
  }

  /**
   * Builds an intent reference from a term ID; empty clears it.
   *
   * @return array<string, int>|null
   *   Field value.
   *
   * @throws \GraphQL\Error\UserError
   *   When the term is not a wish intent.
   */
  private function intentReference(mixed $termId): ?array {
    $termId = trim((string) ($termId ?? ''));
    if ($termId === '') {
      return NULL;
    }
    $term = $this->entityTypeManager->getStorage('taxonomy_term')->load((int) $termId);
    if (!$term instanceof TermInterface || $term->bundle() !== 'wish_intent') {
      throw new UserError('Unknown wish intent.');
    }
    return ['target_id' => (int) $term->id()];
  }

}
