<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Entity\EntityRepositoryInterface;
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
   * @return array{id: string, quantity: int, isSideboard: bool}
   *   The new deck slot data.
   */
  public function add(string $deckUuid, string $cardUuid, int $quantity, bool $isSideboard): array {
    $deck = $this->loadDeck($deckUuid);
    $card = $this->loadCard($cardUuid);

    $para = Paragraph::create([
      'type' => 'deck_card',
      'field_card' => ['target_id' => $card->id()],
      'field_quantity' => $quantity,
      'field_is_sideboard' => $isSideboard,
    ]);
    $para->setNewRevision(FALSE);
    $para->save();

    $deck->get('field_deck_cards')->appendItem([
      'target_id' => $para->id(),
      'target_revision_id' => $para->getRevisionId(),
    ]);
    $deck->setNewRevision(FALSE);
    $deck->save();

    $this->syncCollectionForDeckCard(
      $deck,
      $card,
      $this->quantityOfCardInDeck($deck, (int) $card->id()),
    );

    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => $isSideboard,
    ];
  }

  /**
   * Updates the quantity of a deck slot.
   *
   * @return array{id: string, quantity: int, isSideboard: bool}
   *   The updated deck slot data.
   */
  public function update(string $deckUuid, string $slotUuid, int $quantity): array {
    if ($quantity < 1) {
      throw new BadRequestHttpException('quantity must be at least 1');
    }
    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    $para->set('field_quantity', $quantity);
    $para->save();

    // Reload so quantity sums see the updated paragraph values.
    $deck = $this->loadDeck($deckUuid);
    $card = $para->get('field_card')->entity;
    if ($card instanceof NodeInterface) {
      $this->syncCollectionForDeckCard(
        $deck,
        $card,
        $this->quantityOfCardInDeck($deck, (int) $card->id()),
      );
    }

    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => (bool) ($para->get('field_is_sideboard')->value ?? FALSE),
    ];
  }

  /**
   * Syncs collection owned/foil qty for a card based on the deck's foil flag.
   */
  private function syncCollectionForDeckCard(NodeInterface $deck, NodeInterface $card, int $qty): void {
    $isFoil = $deck->hasField('field_is_foil') && (bool) $deck->get('field_is_foil')->value;
    if ($isFoil) {
      $this->collectionEnsurer->ensureMinFoil($card, $qty);
      return;
    }
    $this->collectionEnsurer->ensureMinOwned($card, $qty);
  }

  /**
   * Replaces the printing on a deck slot and updates the collection.
   *
   * @param string $deckUuid
   *   Deck node UUID.
   * @param string $slotUuid
   *   Deck card paragraph UUID.
   * @param string $cardUuid
   *   New mtg_card printing UUID.
   * @param string $collectionMode
   *   Replace moves collection copies from the old printing to the new
   *   one. Add keeps the old collection row and ensures the new printing.
   * @param bool $foil
   *   TRUE to treat the copies as foil in the collection.
   *
   * @return array{id: string, quantity: int, isSideboard: bool}
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
    if (!in_array($mode, ['replace', 'add'], TRUE)) {
      throw new BadRequestHttpException('collectionMode must be replace or add');
    }

    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    $newCard = $this->loadCard($cardUuid);
    $oldRef = $para->get('field_card')->entity;
    $oldCard = $oldRef instanceof NodeInterface ? $oldRef : NULL;
    $qty = max(1, (int) ($para->get('field_quantity')->value ?? 1));
    $isSideboard = (bool) ($para->get('field_is_sideboard')->value ?? FALSE);

    if ($oldCard instanceof NodeInterface && $oldCard->uuid() === $newCard->uuid()) {
      throw new BadRequestHttpException('That printing is already in this slot');
    }

    $merged = $this->findMergeTarget($deck, $para, $newCard, $isSideboard);
    if ($merged instanceof Paragraph) {
      $mergedQty = max(1, (int) ($merged->get('field_quantity')->value ?? 1)) + $qty;
      $merged->set('field_quantity', $mergedQty);
      $merged->setNewRevision(FALSE);
      $merged->save();
      $this->remove($deckUuid, $slotUuid);
      $this->applyCollectionChange($oldCard, $newCard, $qty, $mode, $foil);
      return [
        'id' => $merged->uuid(),
        'quantity' => $mergedQty,
        'isSideboard' => $isSideboard,
      ];
    }

    $para->set('field_card', ['target_id' => $newCard->id()]);
    $para->setNewRevision(FALSE);
    $para->save();
    $this->pointDeckAtParagraphRevision($deck, $para);

    $this->applyCollectionChange($oldCard, $newCard, $qty, $mode, $foil);

    return [
      'id' => $para->uuid(),
      'quantity' => $qty,
      'isSideboard' => $isSideboard,
    ];
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
   * Sums quantity of a card across all slots in a deck.
   */
  private function quantityOfCardInDeck(NodeInterface $deck, int $cardNid): int {
    $total = 0;
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $entity) {
      if (!$entity instanceof ParagraphInterface || !$entity->hasField('field_card')) {
        continue;
      }
      if ($entity->get('field_card')->isEmpty()) {
        continue;
      }
      if ((int) $entity->get('field_card')->target_id !== $cardNid) {
        continue;
      }
      $total += max(1, (int) ($entity->get('field_quantity')->value ?? 1));
    }
    return max(1, $total);
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

}
