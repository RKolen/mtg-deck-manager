<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Entity\EntityRepositoryInterface;
use Drupal\Core\Entity\FieldableEntityInterface;
use Drupal\node\NodeInterface;
use Drupal\paragraphs\Entity\Paragraph;
use Drupal\paragraphs\ParagraphInterface;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * Creates, updates, and removes deck_card paragraphs on deck nodes.
 *
 * Main deck and sideboard slots live in field_deck_cards. Maybeboard slots
 * live in field_maybe_cards, so everything that reads field_deck_cards
 * (legality, value, simulation, collection syncing) ignores them.
 */
final class DeckCardMutator {

  /**
   * Deck field holding main deck and sideboard slots.
   */
  public const DECK_FIELD = 'field_deck_cards';

  /**
   * Deck field holding maybeboard slots.
   */
  public const MAYBE_FIELD = 'field_maybe_cards';

  /**
   * Valid board names.
   */
  public const BOARDS = ['main', 'side', 'maybe'];

  public function __construct(
    private readonly EntityRepositoryInterface $entityRepository,
    private readonly CollectionEnsurer $collectionEnsurer,
  ) {}

  /**
   * Adds a card to a deck.
   *
   * Does not change collection quantities. NULL $foil uses the deck default.
   * A $board of 'maybe' puts the card on the maybeboard; otherwise
   * $isSideboard decides between main deck and sideboard.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   The new deck slot data.
   */
  public function add(
    string $deckUuid,
    string $cardUuid,
    int $quantity,
    bool $isSideboard,
    ?bool $foil = NULL,
    ?string $board = NULL,
  ): array {
    $deck = $this->loadDeck($deckUuid);
    $card = $this->loadCard($cardUuid);
    $isFoil = $foil ?? $this->deckDefaultFoil($deck);
    $board = $this->normalizeBoard($board ?? ($isSideboard ? 'side' : 'main'));
    $isSideboard = $board === 'side';

    $para = Paragraph::create([
      'type' => 'deck_card',
      'field_card' => ['target_id' => $card->id()],
      'field_quantity' => $quantity,
      'field_is_sideboard' => $isSideboard,
      'field_is_foil' => $isFoil,
    ]);
    $para->setNewRevision(FALSE);
    $para->save();

    $deck->get($this->boardField($board))->appendItem([
      'target_id' => $para->id(),
      'target_revision_id' => $para->getRevisionId(),
    ]);
    $deck->setNewRevision(FALSE);
    $deck->save();

    return $this->slotPayload($para, $quantity, $isSideboard, $isFoil, $board);
  }

  /**
   * Moves a slot to another board (main, side or maybe).
   *
   * When the target board already has this printing, the quantities are
   * merged into that slot. Does not change collection quantities.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   The resulting deck slot data.
   */
  public function move(string $deckUuid, string $slotUuid, string $board): array {
    $board = $this->normalizeBoard($board);
    $deck = $this->loadDeck($deckUuid);
    [$para, $fromField] = $this->findSlot($deck, $slotUuid);
    $toField = $this->boardField($board);
    $isSideboard = $board === 'side';
    $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
    $cardId = (int) ($para->get('field_card')->target_id ?? 0);

    $target = $this->findSlotWithCard($deck, $toField, $cardId, $isSideboard, (int) $para->id());
    if ($target instanceof Paragraph) {
      $mergedQty = max(1, (int) ($target->get('field_quantity')->value ?? 1)) + $qty;
      $target->set('field_quantity', $mergedQty);
      $target->setNewRevision(FALSE);
      $target->save();
      $this->pointDeckAtParagraphRevision($deck, $target, $toField);
      $this->remove($deckUuid, $slotUuid);
      return $this->slotPayload($target, $mergedQty, $isSideboard, $this->slotIsFoil($target), $board);
    }

    $para->set('field_is_sideboard', $isSideboard);
    $para->setNewRevision(FALSE);
    $para->save();

    if ($fromField !== $toField) {
      $this->detachFromField($deck, $fromField, (int) $para->id());
      $deck->get($toField)->appendItem([
        'target_id' => $para->id(),
        'target_revision_id' => $para->getRevisionId(),
      ]);
      $deck->setNewRevision(FALSE);
      $deck->save();
    }
    else {
      $this->pointDeckAtParagraphRevision($deck, $para, $toField);
    }

    return $this->slotPayload($para, $qty, $isSideboard, $this->slotIsFoil($para), $board);
  }

  /**
   * Board a slot paragraph belongs to: main, side or maybe.
   */
  public static function boardOf(ParagraphInterface $para): string {
    if ($para->get('parent_field_name')->value === self::MAYBE_FIELD) {
      return 'maybe';
    }
    return self::fieldIsOn($para, 'field_is_sideboard') ? 'side' : 'main';
  }

  /**
   * Validates a board name.
   *
   * @throws \Symfony\Component\HttpKernel\Exception\BadRequestHttpException
   *   When the board is not main, side or maybe.
   */
  private function normalizeBoard(string $board): string {
    $board = strtolower(trim($board));
    if (!in_array($board, self::BOARDS, TRUE)) {
      throw new BadRequestHttpException('board must be main, side, or maybe');
    }
    return $board;
  }

  /**
   * Deck field that stores slots for a board.
   */
  private function boardField(string $board): string {
    return $board === 'maybe' ? self::MAYBE_FIELD : self::DECK_FIELD;
  }

  /**
   * Updates the quantity of a deck slot.
   *
   * Does not change collection quantities.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   The updated deck slot data.
   */
  public function update(string $deckUuid, string $slotUuid, int $quantity): array {
    if ($quantity < 1) {
      throw new BadRequestHttpException('quantity must be at least 1');
    }
    $deck = $this->loadDeck($deckUuid);
    [$para, $field] = $this->findSlot($deck, $slotUuid);
    $para->set('field_quantity', $quantity);
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para, $field);

    return $this->slotPayload(
      $para,
      $quantity,
      self::fieldIsOn($para, 'field_is_sideboard'),
      $this->slotIsFoil($para),
      $this->boardForField($para, $field),
    );
  }

  /**
   * Sets the foil flag on a deck slot without touching the collection.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   The updated deck slot data.
   */
  public function setFoil(string $deckUuid, string $slotUuid, bool $foil): array {
    $deck = $this->loadDeck($deckUuid);
    [$para, $field] = $this->findSlot($deck, $slotUuid);
    if ($para->hasField('field_is_foil')) {
      $para->set('field_is_foil', $foil);
    }
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para, $field);

    return $this->slotPayload(
      $para,
      max(1, (int) ($para->get('field_quantity')->value ?? 1)),
      self::fieldIsOn($para, 'field_is_sideboard'),
      $foil,
      $this->boardForField($para, $field),
    );
  }

  /**
   * Replaces the printing on a deck slot.
   *
   * Collection updates run only for replace or add. none changes the list
   * entry only. The foil argument is written onto the slot either way.
   *
   * @param string $deckUuid
   *   Deck node UUID.
   * @param string $slotUuid
   *   Deck card paragraph UUID.
   * @param string $cardUuid
   *   New mtg_card printing UUID.
   * @param string $collectionMode
   *   None leaves collection unchanged. Replace moves copies from the old
   *   printing. Add keeps the old row and ensures the new printing.
   * @param bool $foil
   *   Foil flag stored on the slot (and used for collection replace/add).
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   The resulting deck slot data.
   */
  public function replacePrinting(
    string $deckUuid,
    string $slotUuid,
    string $cardUuid,
    string $collectionMode,
    bool $foil,
  ): array {
    $mode = strtolower(trim($collectionMode));
    if (!in_array($mode, ['none', 'replace', 'add'], TRUE)) {
      throw new BadRequestHttpException('collectionMode must be none, replace, or add');
    }

    $deck = $this->loadDeck($deckUuid);
    [$para, $field] = $this->findSlot($deck, $slotUuid);
    $board = $this->boardForField($para, $field);
    // Maybeboard cards are not owned, so a printing swap never touches the
    // collection there.
    if ($board === 'maybe') {
      $mode = 'none';
    }
    $newCard = $this->loadCard($cardUuid);
    $oldRef = $para->get('field_card')->entity;
    $oldCard = $oldRef instanceof NodeInterface ? $oldRef : NULL;
    $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
    $isSideboard = self::fieldIsOn($para, 'field_is_sideboard');

    if ($oldCard instanceof NodeInterface && $oldCard->uuid() === $newCard->uuid()) {
      if ($this->slotIsFoil($para) === $foil && $mode === 'none') {
        throw new BadRequestHttpException('That printing is already in this slot');
      }
      if ($para->hasField('field_is_foil')) {
        $para->set('field_is_foil', $foil);
      }
      $para->setNewRevision(FALSE);
      $para->save();
      $this->pointDeckAtParagraphRevision($deck, $para, $field);
      if ($mode !== 'none') {
        $this->applyCollectionChange($deck, $oldCard, $newCard, $qty, $mode, $foil);
      }
      return $this->slotPayload($para, $qty, $isSideboard, $foil, $board);
    }

    $merged = $this->findSlotWithCard($deck, $field, (int) $newCard->id(), $isSideboard, (int) $para->id());
    if ($merged instanceof Paragraph) {
      $mergedQty = max(1, (int) ($merged->get('field_quantity')->value ?? 1)) + $qty;
      $merged->set('field_quantity', $mergedQty);
      if ($merged->hasField('field_is_foil')) {
        $merged->set('field_is_foil', $foil);
      }
      $merged->setNewRevision(FALSE);
      $merged->save();
      $this->pointDeckAtParagraphRevision($deck, $merged, $field);
      $this->remove($deckUuid, $slotUuid);
      if ($mode !== 'none') {
        $this->applyCollectionChange($deck, $oldCard, $newCard, $qty, $mode, $foil);
      }
      return $this->slotPayload($merged, $mergedQty, $isSideboard, $foil, $board);
    }

    $para->set('field_card', ['target_id' => $newCard->id()]);
    if ($para->hasField('field_is_foil')) {
      $para->set('field_is_foil', $foil);
    }
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para, $field);

    if ($mode !== 'none') {
      $this->applyCollectionChange($deck, $oldCard, $newCard, $qty, $mode, $foil);
    }

    return $this->slotPayload($para, $qty, $isSideboard, $foil, $board);
  }

  /**
   * Applies replace or add collection updates for a printing swap.
   *
   * The new printing is ensured for every copy the deck runs of it (main and
   * sideboard together), not only the swapped slot, so a sideboard slot of a
   * printing that is also in the main deck is counted on top.
   */
  private function applyCollectionChange(
    NodeInterface $deck,
    ?NodeInterface $oldCard,
    NodeInterface $newCard,
    int $qty,
    string $mode,
    bool $foil,
  ): void {
    if ($mode === 'replace' && $oldCard instanceof NodeInterface) {
      $this->collectionEnsurer->removeCopies($oldCard, $qty, $foil);
    }
    $needed = max($qty, $this->deckCopiesOf($deck, $newCard, $foil));
    if ($this->collectionEnsurer->loadByCard($newCard) === NULL) {
      $this->collectionEnsurer->addCopies($newCard, $needed, $foil);
      return;
    }
    if ($foil) {
      $this->collectionEnsurer->ensureMinFoil($newCard, $needed);
      return;
    }
    $this->collectionEnsurer->ensureMinOwned($newCard, $needed);
  }

  /**
   * Copies of a printing in a deck's main deck and sideboard, by finish.
   */
  private function deckCopiesOf(NodeInterface $deck, NodeInterface $card, bool $foil): int {
    $total = 0;
    foreach ($deck->get(self::DECK_FIELD)->referencedEntities() as $slot) {
      if (!$slot instanceof ParagraphInterface
        || (int) ($slot->get('field_card')->target_id ?? 0) !== (int) $card->id()
        || $this->slotIsFoil($slot) !== $foil) {
        continue;
      }
      $total += max(1, (int) ($slot->get('field_quantity')->value ?? 1));
    }
    return $total;
  }

  /**
   * Finds another slot in a deck field that already uses this printing.
   *
   * On the maybeboard the sideboard flag is ignored.
   */
  private function findSlotWithCard(
    NodeInterface $deck,
    string $field,
    int $cardId,
    bool $isSideboard,
    int $excludeId,
  ): ?Paragraph {
    if (!$deck->hasField($field)) {
      return NULL;
    }
    foreach ($deck->get($field)->referencedEntities() as $entity) {
      if (!$entity instanceof Paragraph || (int) $entity->id() === $excludeId) {
        continue;
      }
      if ($field === self::DECK_FIELD && self::fieldIsOn($entity, 'field_is_sideboard') !== $isSideboard) {
        continue;
      }
      if ((int) ($entity->get('field_card')->target_id ?? 0) !== $cardId) {
        continue;
      }
      return $entity;
    }
    return NULL;
  }

  /**
   * Updates the deck paragraph reference to the latest revision.
   */
  private function pointDeckAtParagraphRevision(NodeInterface $deck, Paragraph $para, string $field = self::DECK_FIELD): void {
    $items = $deck->get($field);
    foreach ($items as $item) {
      $value = $item->getValue();
      if ((int) ($value['target_id'] ?? 0) !== (int) $para->id()) {
        continue;
      }
      $item->setValue([
        'target_id' => $para->id(),
        'target_revision_id' => $para->getRevisionId(),
      ]);
      break;
    }
    $deck->setNewRevision(FALSE);
    $deck->save();
  }

  /**
   * Removes a deck slot from a deck and deletes the paragraph.
   *
   * @return bool
   *   TRUE on success.
   */
  public function remove(string $deckUuid, string $slotUuid): bool {
    $deck = $this->loadDeck($deckUuid);
    [$para, $field] = $this->findSlot($deck, $slotUuid);
    $this->detachFromField($deck, $field, (int) $para->id());
    $deck->setNewRevision(FALSE);
    $deck->save();
    $para->delete();
    return TRUE;
  }

  /**
   * Removes a paragraph reference from a deck field without saving.
   */
  private function detachFromField(NodeInterface $deck, string $field, int $paraId): void {
    $items = $deck->get($field);
    foreach ($items as $delta => $item) {
      if ((int) ($item->getValue()['target_id'] ?? 0) === $paraId) {
        $items->removeItem($delta);
        return;
      }
    }
  }

  /**
   * Loads a deck node by UUID, throwing if not found.
   */
  private function loadDeck(string $deckUuid): NodeInterface {
    $deck = $this->entityRepository->loadEntityByUuid('node', $deckUuid);
    if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
      throw new NotFoundHttpException('Deck not found: ' . $deckUuid);
    }
    return $deck;
  }

  /**
   * Loads a card node by UUID, throwing if not found.
   */
  private function loadCard(string $cardUuid): NodeInterface {
    $card = $this->entityRepository->loadEntityByUuid('node', $cardUuid);
    if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
      throw new NotFoundHttpException('Card not found: ' . $cardUuid);
    }
    return $card;
  }

  /**
   * Finds a deck_card paragraph on any board, throwing if not found.
   *
   * @return array{0: \Drupal\paragraphs\Entity\Paragraph, 1: string}
   *   The paragraph and the deck field holding it.
   */
  private function findSlot(NodeInterface $deck, string $slotUuid): array {
    foreach ([self::DECK_FIELD, self::MAYBE_FIELD] as $field) {
      if (!$deck->hasField($field)) {
        continue;
      }
      foreach ($deck->get($field)->referencedEntities() as $entity) {
        if ($entity instanceof Paragraph && $entity->uuid() === $slotUuid) {
          return [$entity, $field];
        }
      }
    }
    throw new NotFoundHttpException('Deck slot not found: ' . $slotUuid);
  }

  /**
   * Board of a slot, given the deck field it was found in.
   */
  private function boardForField(ParagraphInterface $para, string $field): string {
    if ($field === self::MAYBE_FIELD) {
      return 'maybe';
    }
    return self::fieldIsOn($para, 'field_is_sideboard') ? 'side' : 'main';
  }

  /**
   * Reads a Drupal boolean field as true only when the stored value is 1.
   *
   * Drupal stores off as the string 0, which (bool) casts to TRUE.
   */
  public static function fieldIsOn(FieldableEntityInterface $entity, string $field): bool {
    if (!$entity->hasField($field)) {
      return FALSE;
    }
    $item = $entity->get($field);
    if ($item->isEmpty()) {
      return FALSE;
    }
    return (int) $item->value === 1;
  }

  /**
   * Default foil flag for newly added slots.
   */
  private function deckDefaultFoil(NodeInterface $deck): bool {
    return self::fieldIsOn($deck, 'field_is_foil');
  }

  /**
   * Reads the foil flag on a deck_card paragraph.
   */
  private function slotIsFoil(ParagraphInterface $para): bool {
    return self::fieldIsOn($para, 'field_is_foil');
  }

  /**
   * Builds the GraphQL DeckCardSlot payload.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool, board: string}
   *   Slot fields for mutation responses.
   */
  private function slotPayload(
    ParagraphInterface $para,
    int $quantity,
    bool $isSideboard,
    bool $isFoil,
    string $board,
  ): array {
    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => $isSideboard,
      'isFoil' => $isFoil,
      'board' => $board,
    ];
  }

}
