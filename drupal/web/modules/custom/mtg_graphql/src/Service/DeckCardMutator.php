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
 */
final class DeckCardMutator {

  public function __construct(
    private readonly EntityRepositoryInterface $entityRepository,
    private readonly CollectionEnsurer $collectionEnsurer,
  ) {}

  /**
   * Adds a card to a deck.
   *
   * Does not change collection quantities. NULL $foil uses the deck default.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool}
   *   The new deck slot data.
   */
  public function add(
    string $deckUuid,
    string $cardUuid,
    int $quantity,
    bool $isSideboard,
    ?bool $foil = NULL,
  ): array {
    $deck = $this->loadDeck($deckUuid);
    $card = $this->loadCard($cardUuid);
    $isFoil = $foil ?? $this->deckDefaultFoil($deck);

    $para = Paragraph::create([
      'type' => 'deck_card',
      'field_card' => ['target_id' => $card->id()],
      'field_quantity' => $quantity,
      'field_is_sideboard' => $isSideboard,
      'field_is_foil' => $isFoil,
    ]);
    $para->setNewRevision(FALSE);
    $para->save();

    $deck->get('field_deck_cards')->appendItem([
      'target_id' => $para->id(),
      'target_revision_id' => $para->getRevisionId(),
    ]);
    $deck->setNewRevision(FALSE);
    $deck->save();

    return $this->slotPayload($para, $quantity, $isSideboard, $isFoil);
  }

  /**
   * Updates the quantity of a deck slot.
   *
   * Does not change collection quantities.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool}
   *   The updated deck slot data.
   */
  public function update(string $deckUuid, string $slotUuid, int $quantity): array {
    if ($quantity < 1) {
      throw new BadRequestHttpException('quantity must be at least 1');
    }
    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    $para->set('field_quantity', $quantity);
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para);

    return $this->slotPayload(
      $para,
      $quantity,
      (bool) ($para->get('field_is_sideboard')->value ?? FALSE),
      $this->slotIsFoil($para),
    );
  }

  /**
   * Sets the foil flag on a deck slot without touching the collection.
   *
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool}
   *   The updated deck slot data.
   */
  public function setFoil(string $deckUuid, string $slotUuid, bool $foil): array {
    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    if ($para->hasField('field_is_foil')) {
      $para->set('field_is_foil', $foil);
    }
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para);

    return $this->slotPayload(
      $para,
      max(1, (int) ($para->get('field_quantity')->value ?? 1)),
      (bool) ($para->get('field_is_sideboard')->value ?? FALSE),
      $foil,
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
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool}
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
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    $newCard = $this->loadCard($cardUuid);
    $oldRef = $para->get('field_card')->entity;
    $oldCard = $oldRef instanceof NodeInterface ? $oldRef : NULL;
    $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
    $isSideboard = (bool) ($para->get('field_is_sideboard')->value ?? FALSE);

    if ($oldCard instanceof NodeInterface && $oldCard->uuid() === $newCard->uuid()) {
      if ($this->slotIsFoil($para) === $foil && $mode === 'none') {
        throw new BadRequestHttpException('That printing is already in this slot');
      }
      if ($para->hasField('field_is_foil')) {
        $para->set('field_is_foil', $foil);
      }
      $para->setNewRevision(FALSE);
      $para->save();
      $this->pointDeckAtParagraphRevision($deck, $para);
      if ($mode !== 'none') {
        $this->applyCollectionChange($oldCard, $newCard, $qty, $mode, $foil);
      }
      return $this->slotPayload($para, $qty, $isSideboard, $foil);
    }

    $merged = $this->findMergeTarget($deck, $para, $newCard, $isSideboard);
    if ($merged instanceof Paragraph) {
      $mergedQty = max(1, (int) ($merged->get('field_quantity')->value ?? 1)) + $qty;
      $merged->set('field_quantity', $mergedQty);
      if ($merged->hasField('field_is_foil')) {
        $merged->set('field_is_foil', $foil);
      }
      $merged->setNewRevision(FALSE);
      $merged->save();
      $this->remove($deckUuid, $slotUuid);
      if ($mode !== 'none') {
        $this->applyCollectionChange($oldCard, $newCard, $qty, $mode, $foil);
      }
      return $this->slotPayload($merged, $mergedQty, $isSideboard, $foil);
    }

    $para->set('field_card', ['target_id' => $newCard->id()]);
    if ($para->hasField('field_is_foil')) {
      $para->set('field_is_foil', $foil);
    }
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para);

    if ($mode !== 'none') {
      $this->applyCollectionChange($oldCard, $newCard, $qty, $mode, $foil);
    }

    return $this->slotPayload($para, $qty, $isSideboard, $foil);
  }

  /**
   * Applies replace or add collection updates for a printing swap.
   */
  private function applyCollectionChange(
    ?NodeInterface $oldCard,
    NodeInterface $newCard,
    int $qty,
    string $mode,
    bool $foil,
  ): void {
    if ($mode === 'replace' && $oldCard instanceof NodeInterface) {
      $this->collectionEnsurer->removeCopies($oldCard, $qty, $foil);
    }
    if ($this->collectionEnsurer->loadByCard($newCard) === NULL) {
      $this->collectionEnsurer->addCopies($newCard, $qty, $foil);
      return;
    }
    if ($foil) {
      $this->collectionEnsurer->ensureMinFoil($newCard, $qty);
      return;
    }
    $this->collectionEnsurer->ensureMinOwned($newCard, $qty);
  }

  /**
   * Finds another slot on the deck that already uses this printing.
   */
  private function findMergeTarget(
    NodeInterface $deck,
    Paragraph $current,
    NodeInterface $newCard,
    bool $isSideboard,
  ): ?Paragraph {
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $entity) {
      if (!$entity instanceof Paragraph || $entity->id() === $current->id()) {
        continue;
      }
      if ((bool) ($entity->get('field_is_sideboard')->value ?? FALSE) !== $isSideboard) {
        continue;
      }
      if ((int) ($entity->get('field_card')->target_id ?? 0) !== (int) $newCard->id()) {
        continue;
      }
      return $entity;
    }
    return NULL;
  }

  /**
   * Updates the deck paragraph reference to the latest revision.
   */
  private function pointDeckAtParagraphRevision(NodeInterface $deck, Paragraph $para): void {
    $items = $deck->get('field_deck_cards');
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
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);

    $items = $deck->get('field_deck_cards');
    foreach ($items as $delta => $item) {
      if ((int) $item->getValue()['target_id'] === (int) $para->id()) {
        $items->removeItem($delta);
        break;
      }
    }
    $deck->setNewRevision(FALSE);
    $deck->save();
    $para->delete();
    return TRUE;
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
   * Finds a specific deck_card paragraph on the deck, throwing if not found.
   */
  private function loadParagraphOnDeck(NodeInterface $deck, string $slotUuid): Paragraph {
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $entity) {
      if ($entity instanceof Paragraph && $entity->uuid() === $slotUuid) {
        return $entity;
      }
    }
    throw new NotFoundHttpException('Deck slot not found: ' . $slotUuid);
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
   * @return array{id: string, quantity: int, isSideboard: bool, isFoil: bool}
   *   Slot fields for mutation responses.
   */
  private function slotPayload(
    ParagraphInterface $para,
    int $quantity,
    bool $isSideboard,
    bool $isFoil,
  ): array {
    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => $isSideboard,
      'isFoil' => $isFoil,
    ];
  }

}
