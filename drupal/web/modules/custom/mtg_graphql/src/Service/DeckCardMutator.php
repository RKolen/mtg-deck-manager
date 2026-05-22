<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Entity\EntityRepositoryInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\paragraphs\Entity\Paragraph;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * Creates, updates, and removes deck_card paragraphs on deck nodes.
 */
final class DeckCardMutator {

  public function __construct(
    private readonly EntityRepositoryInterface $entityRepository,
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {}

  /**
   * @return array{id: string, quantity: int, isSideboard: bool}
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

    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => $isSideboard,
    ];
  }

  /**
   * @return array{id: string, quantity: int, isSideboard: bool}
   */
  public function update(string $deckUuid, string $slotUuid, int $quantity): array {
    if ($quantity < 1) {
      throw new BadRequestHttpException('quantity must be at least 1');
    }
    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);
    $para->set('field_quantity', $quantity);
    $para->save();

    return [
      'id' => $para->uuid(),
      'quantity' => $quantity,
      'isSideboard' => (bool) ($para->get('field_is_sideboard')->value ?? FALSE),
    ];
  }

  public function remove(string $deckUuid, string $slotUuid): bool {
    $deck = $this->loadDeck($deckUuid);
    $para = $this->loadParagraphOnDeck($deck, $slotUuid);

    $items = $deck->get('field_deck_cards');
    foreach ($items as $delta => $item) {
      if ((int) $item->target_id === (int) $para->id()) {
        $items->removeItem($delta);
        break;
      }
    }
    $deck->setNewRevision(FALSE);
    $deck->save();
    $para->delete();
    return TRUE;
  }

  private function loadDeck(string $deckUuid): NodeInterface {
    $deck = $this->entityRepository->loadEntityByUuid('node', $deckUuid);
    if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
      throw new NotFoundHttpException('Deck not found: ' . $deckUuid);
    }
    return $deck;
  }

  private function loadCard(string $cardUuid): NodeInterface {
    $card = $this->entityRepository->loadEntityByUuid('node', $cardUuid);
    if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
      throw new NotFoundHttpException('Card not found: ' . $cardUuid);
    }
    return $card;
  }

  private function loadParagraphOnDeck(NodeInterface $deck, string $slotUuid): Paragraph {
    foreach ($deck->get('field_deck_cards') as $item) {
      if ($item->entity instanceof Paragraph && $item->entity->uuid() === $slotUuid) {
        return $item->entity;
      }
    }
    throw new NotFoundHttpException('Deck slot not found: ' . $slotUuid);
  }

}
