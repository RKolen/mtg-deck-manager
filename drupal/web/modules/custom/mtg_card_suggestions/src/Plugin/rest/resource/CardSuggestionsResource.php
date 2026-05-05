<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Plugin\rest\resource;

use Drupal\Core\Cache\CacheableMetadata;
use Drupal\Core\Entity\EntityStorageInterface;
use Drupal\mtg_card_suggestions\Service\CardSuggester;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * REST resource exposing AI-powered deck card suggestions.
 *
 * GET /api/card-suggestions?deck_id=<nid>&limit=<n>
 *
 * Returns a ranked list of cards that synergise with the given deck,
 * derived from Milvus semantic search + Ollama reasoning.
 *
 * @RestResource(
 *   id = "mtg_card_suggestions",
 *   label = @Translation("MTG Card Suggestions"),
 *   uri_paths = {
 *     "canonical" = "/api/card-suggestions"
 *   }
 * )
 */
class CardSuggestionsResource extends ResourceBase {

  /**
   * The card suggester service.
   *
   * @var \Drupal\mtg_card_suggestions\Service\CardSuggester
   */
  private CardSuggester $suggester;

  /**
   * The node entity storage.
   *
   * @var \Drupal\Core\Entity\EntityStorageInterface
   */
  private EntityStorageInterface $nodeStorage;

  /**
   * {@inheritdoc}
   *
   * @throws \Drupal\Component\Plugin\Exception\InvalidPluginDefinitionException
   * @throws \Drupal\Component\Plugin\Exception\PluginNotFoundException
   */
  public static function create(
    ContainerInterface $container,
    array $configuration,
    $plugin_id,
    $plugin_definition,
  ): static {
    $instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
    $instance->suggester = $container->get('mtg_card_suggestions.suggester');
    /** @var \Drupal\Core\Entity\EntityTypeManagerInterface $etm */
    $etm = $container->get('entity_type.manager');
    $instance->nodeStorage = $etm->getStorage('node');
    return $instance;
  }

  /**
   * Responds to GET /api/card-suggestions.
   *
   * Query parameters:
   *   - deck_id (required): The deck node ID.
   *   - limit (optional, 1–50, default 10): Max suggestions to return.
   *
   * @param \Symfony\Component\HttpFoundation\Request $request
   *   The incoming request.
   *
   * @return \Drupal\rest\ResourceResponse
   *   JSON response with suggestions array and meta count.
   *
   * @throws \Symfony\Component\HttpKernel\Exception\BadRequestHttpException
   * @throws \Symfony\Component\HttpKernel\Exception\NotFoundHttpException
   */
  public function get(Request $request): ResourceResponse {
    $deckIdRaw = $request->query->get('deck_id', '');
    if ($deckIdRaw === '' || !ctype_digit((string) $deckIdRaw)) {
      throw new BadRequestHttpException('deck_id must be a positive integer.');
    }

    $deckNid = (int) $deckIdRaw;
    $deck = $this->nodeStorage->load($deckNid);
    if ($deck === NULL || $deck->bundle() !== 'deck') {
      throw new NotFoundHttpException('Deck not found.');
    }

    $limit = max(1, min(50, (int) $request->query->get('limit', 10)));
    $suggestions = $this->suggester->suggest($deckNid, $limit);

    $response = new ResourceResponse([
      'data' => $suggestions,
      'meta' => ['count' => count($suggestions)],
    ]);
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);
    return $response;
  }

}
