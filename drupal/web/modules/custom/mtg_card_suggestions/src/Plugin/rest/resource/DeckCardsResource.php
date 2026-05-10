<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Plugin\rest\resource;

use Drupal\Core\Cache\CacheableMetadata;
use Drupal\Core\Entity\EntityRepositoryInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\paragraphs\Entity\Paragraph;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * REST resource for deck card slot mutations.
 *
 * POST /api/deck-cards
 *
 * All mutations go through a single POST with an 'action' field so Drupal
 * routing stays trivial and CSRF is bypassed via Basic Auth.
 *
 * Actions:
 *   add    {deckUuid, cardUuid, quantity, isSideboard}
 *          → creates a paragraph--deck_card, appends to deck
 *          → returns {paraUuid, quantity, isSideboard}
 *
 *   update {deckUuid, paraUuid, quantity}
 *          → updates field_quantity on the paragraph
 *          → returns {paraUuid, quantity}
 *
 *   remove {deckUuid, paraUuid}
 *          → removes paragraph from deck and deletes it
 *          → returns {}
 *
 * @RestResource(
 *   id = "deck_cards",
 *   label = @Translation("MTG Deck Cards"),
 *   uri_paths = {
 *     "create" = "/api/deck-cards"
 *   }
 * )
 */
final class DeckCardsResource extends ResourceBase {

  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    array $serializer_formats,
    LoggerInterface $logger,
    private readonly EntityRepositoryInterface $entityRepository,
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition, $serializer_formats, $logger);
  }

  public static function create(
    ContainerInterface $container,
    array $configuration,
    $plugin_id,
    $plugin_definition,
  ): static {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->getParameter('serializer.formats'),
      $container->get('logger.factory')->get('mtg_card_suggestions'),
      $container->get('entity.repository'),
      $container->get('entity_type.manager'),
    );
  }

  public function post(mixed $data): ResourceResponse {
    if (!is_array($data) || empty($data['action']) || empty($data['deckUuid'])) {
      throw new BadRequestHttpException('Body must include action and deckUuid.');
    }

    $deck = $this->loadDeck((string) $data['deckUuid']);

    return match ((string) $data['action']) {
      'add'    => $this->actionAdd($deck, $data),
      'update' => $this->actionUpdate($deck, $data),
      'remove' => $this->actionRemove($deck, $data),
      default  => throw new BadRequestHttpException('Unknown action: ' . $data['action']),
    };
  }

  private function actionAdd(NodeInterface $deck, array $data): ResourceResponse {
    if (empty($data['cardUuid']) || !isset($data['quantity']) || !isset($data['isSideboard'])) {
      throw new BadRequestHttpException('add requires cardUuid, quantity, and isSideboard.');
    }

    $card = $this->entityRepository->loadEntityByUuid('node', (string) $data['cardUuid']);
    if (!$card instanceof NodeInterface || $card->bundle() !== 'mtg_card') {
      throw new NotFoundHttpException('Card not found: ' . $data['cardUuid']);
    }

    $para = Paragraph::create([
      'type' => 'deck_card',
      'field_card' => ['target_id' => $card->id()],
      'field_quantity' => (int) $data['quantity'],
      'field_is_sideboard' => (bool) $data['isSideboard'],
    ]);
    $para->setNewRevision(FALSE);
    $para->save();

    $deck->get('field_deck_cards')->appendItem([
      'target_id' => $para->id(),
      'target_revision_id' => $para->getRevisionId(),
    ]);
    $deck->setNewRevision(FALSE);
    $deck->save();

    return $this->ok([
      'paraUuid'    => $para->uuid(),
      'quantity'    => (int) $para->get('field_quantity')->value,
      'isSideboard' => (bool) $para->get('field_is_sideboard')->value,
    ]);
  }

  private function actionUpdate(NodeInterface $deck, array $data): ResourceResponse {
    if (empty($data['paraUuid']) || !isset($data['quantity'])) {
      throw new BadRequestHttpException('update requires paraUuid and quantity.');
    }

    $para = $this->entityRepository->loadEntityByUuid('paragraph', (string) $data['paraUuid']);
    if ($para === NULL) {
      throw new NotFoundHttpException('Card slot not found: ' . $data['paraUuid']);
    }

    $para->set('field_quantity', (int) $data['quantity']);
    $para->setNewRevision(FALSE);
    $para->save();

    // Re-save the deck so entity_reference_revisions tracks the updated vid.
    $deck->setNewRevision(FALSE);
    $deck->save();

    return $this->ok([
      'paraUuid' => $para->uuid(),
      'quantity' => (int) $para->get('field_quantity')->value,
    ]);
  }

  private function actionRemove(NodeInterface $deck, array $data): ResourceResponse {
    if (empty($data['paraUuid'])) {
      throw new BadRequestHttpException('remove requires paraUuid.');
    }

    $para = $this->entityRepository->loadEntityByUuid('paragraph', (string) $data['paraUuid']);
    if ($para === NULL) {
      throw new NotFoundHttpException('Card slot not found: ' . $data['paraUuid']);
    }

    // Remove the item from the field before deleting the paragraph.
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

    return $this->ok([]);
  }

  private function loadDeck(string $uuid): NodeInterface {
    $deck = $this->entityRepository->loadEntityByUuid('node', $uuid);
    if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
      throw new NotFoundHttpException('Deck not found: ' . $uuid);
    }
    return $deck;
  }

  private function ok(array $payload): ResourceResponse {
    $response = new ResourceResponse($payload, 200);
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);
    return $response;
  }

}
