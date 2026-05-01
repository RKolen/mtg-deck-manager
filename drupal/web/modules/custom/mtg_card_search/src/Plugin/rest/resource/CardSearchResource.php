<?php

declare(strict_types=1);

namespace Drupal\mtg_card_search\Plugin\rest\resource;

use Drupal\node\NodeInterface;
use Drupal\search_api\Query\QueryInterface;
use Drupal\Core\Cache\CacheableMetadata;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use Drupal\search_api\IndexInterface;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\Request;

/**
 * REST resource exposing full-text card search over Search API + Solr.
 *
 * GET /api/card-search.
 *
 * Query parameters:
 *   q            - Fulltext search across card name and oracle text.
 *   type         - Partial match against type_line (e.g. "Creature").
 *   legal_in     - Format legality filter (e.g. "modern").
 *   cmc_min      - Minimum converted mana cost (inclusive).
 *   cmc_max      - Maximum converted mana cost (inclusive).
 *   colors[]     - Colors the card must contain (W/U/B/R/G, repeatable).
 *   color_identity[] - Color identity filter (W/U/B/R/G, repeatable).
 *   mana_producer - Filter to mana-producing creatures (1/0).
 *   page         - Zero-based page number (default 0).
 *   limit        - Results per page, max 100 (default 20).
 *
 * Response shape mirrors JSON:API for frontend type reuse:
 *   { data: [{id, type, attributes}], meta: { count, pages } }
 *
 * @RestResource(
 *   id = "card_search",
 *   label = @Translation("MTG Card Search"),
 *   uri_paths = {
 *     "canonical" = "/api/card-search"
 *   }
 * )
 */
final class CardSearchResource extends ResourceBase {

  /**
   * The Search API index ID used for card search.
   */
  private const INDEX_ID = 'mtg_card_search';

  /**
   * Maximum allowed results per page.
   */
  private const MAX_LIMIT = 100;

  /**
   * Default results per page.
   */
  private const DEFAULT_LIMIT = 20;

  /**
   * Constructs a CardSearchResource instance.
   *
   * @param array<string, mixed> $configuration
   *   Plugin configuration.
   * @param string $plugin_id
   *   The plugin ID.
   * @param mixed $plugin_definition
   *   The plugin definition.
   * @param string[] $serializer_formats
   *   The available serializer formats.
   * @param \Psr\Log\LoggerInterface $logger
   *   The logger.
   * @param \Drupal\Core\Entity\EntityTypeManagerInterface $entityTypeManager
   *   The entity type manager.
   */
  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    array $serializer_formats,
    LoggerInterface $logger,
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition, $serializer_formats, $logger);
  }

  /**
   * {@inheritdoc}
   */
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
      $container->get('logger.factory')->get('mtg_card_search'),
      $container->get('entity_type.manager'),
    );
  }

  /**
   * Handles GET requests.
   *
   * @param \Symfony\Component\HttpFoundation\Request $request
   *   The current request.
   *
   * @return \Drupal\rest\ResourceResponse
   *   The response containing matching card data.
   */
  public function get(Request $request): ResourceResponse {
    $index = $this->loadIndex();
    if ($index === NULL) {
      return $this->errorResponse('Search index not available.', 503);
    }

    [$page, $limit] = $this->parsePagination($request);
    $query = $index->query();
    $query->range($page * $limit, $limit);

    $this->applyFulltextSearch($query, $request);
    $this->applyConditions($query, $request);

    /** @var \Drupal\search_api\Query\ResultSetInterface $results */
    $results = $query->execute();
    $count = $results->getResultCount();

    $data = [];
    foreach ($results->getResultItems() as $item) {
      $object = $item->getOriginalObject();
      if ($object === NULL) {
        continue;
      }
      /** @var \Drupal\node\NodeInterface $node */
      $node = $object->getValue();
      $data[] = $this->serializeCard($node);
    }

    $response = new ResourceResponse([
      'data' => $data,
      'meta' => [
        'count' => $count,
        'pages' => (int) ceil($count / $limit),
      ],
    ]);

    // Each unique query combination is cached under its own cache context.
    // Set max-age to 0 to let the upstream HTTP cache handle invalidation
    // rather than Drupal's internal page cache, which does not vary on
    // query string by default.
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);

    return $response;
  }

  /**
   * Loads the Search API index.
   *
   * @return \Drupal\search_api\IndexInterface|null
   *   The loaded index, or NULL if not found.
   */
  private function loadIndex(): ?IndexInterface {
    $storage = $this->entityTypeManager->getStorage('search_api_index');
    $index = $storage->load(self::INDEX_ID);
    if (!$index instanceof IndexInterface) {
      $this->logger->error('Search API index "@id" not found.', ['@id' => self::INDEX_ID]);
      return NULL;
    }
    return $index;
  }

  /**
   * Applies fulltext search keys to the query.
   *
   * @param \Drupal\search_api\Query\QueryInterface $query
   *   The search query.
   * @param \Symfony\Component\HttpFoundation\Request $request
   *   The request.
   */
  private function applyFulltextSearch(
    QueryInterface $query,
    Request $request,
  ): void {
    $q = trim($request->query->getString('q', ''));
    if ($q !== '') {
      $query->keys($q);
      $query->setFulltextFields(['title', 'field_oracle_text']);
    }
  }

  /**
   * Applies filter conditions to the query.
   *
   * @param \Drupal\search_api\Query\QueryInterface $query
   *   The search query.
   * @param \Symfony\Component\HttpFoundation\Request $request
   *   The request.
   */
  private function applyConditions(
    QueryInterface $query,
    Request $request,
  ): void {
    $conditions = $query->createConditionGroup('AND');
    $hasCondition = FALSE;

    $type = trim($request->query->getString('type', ''));
    if ($type !== '') {
      $conditions->addCondition('field_type_line_string', $type, 'CONTAINS');
      $hasCondition = TRUE;
    }

    $legalIn = trim($request->query->getString('legal_in', ''));
    if ($legalIn !== '') {
      $conditions->addCondition('field_legal_formats', $legalIn);
      $hasCondition = TRUE;
    }

    $cmcMin = $request->query->get('cmc_min');
    if ($cmcMin !== NULL && is_numeric($cmcMin)) {
      $conditions->addCondition('field_cmc', (float) $cmcMin, '>=');
      $hasCondition = TRUE;
    }

    $cmcMax = $request->query->get('cmc_max');
    if ($cmcMax !== NULL && is_numeric($cmcMax)) {
      $conditions->addCondition('field_cmc', (float) $cmcMax, '<=');
      $hasCondition = TRUE;
    }

    // Each selected color must be present on the card.
    $colors = $request->query->all('colors');
    foreach ($this->sanitizeColors($colors) as $color) {
      $conditions->addCondition('field_colors', $color);
      $hasCondition = TRUE;
    }

    $colorIdentity = $request->query->all('color_identity');
    foreach ($this->sanitizeColors($colorIdentity) as $color) {
      $conditions->addCondition('field_color_identity', $color);
      $hasCondition = TRUE;
    }

    $manaProducer = $request->query->get('mana_producer');
    if ($manaProducer !== NULL) {
      $conditions->addCondition('field_is_mana_producer', (bool) (int) $manaProducer);
      $hasCondition = TRUE;
    }

    if ($hasCondition) {
      $query->addConditionGroup($conditions);
    }
  }

  /**
   * Sanitizes a raw color array, keeping only valid WUBRG values.
   *
   * @param mixed[] $colors
   *   Raw input array from the request.
   *
   * @return string[]
   *   Deduplicated, uppercase WUBRG color strings.
   */
  private function sanitizeColors(array $colors): array {
    $valid = [];
    foreach ($colors as $c) {
      $upper = strtoupper((string) $c);
      if (preg_match('/^[WUBRG]$/', $upper) && !in_array($upper, $valid, TRUE)) {
        $valid[] = $upper;
      }
    }
    return $valid;
  }

  /**
   * Parses and clamps pagination parameters from the request.
   *
   * @param \Symfony\Component\HttpFoundation\Request $request
   *   The request.
   *
   * @return array{int, int}
   *   Tuple of [page, limit].
   */
  private function parsePagination(Request $request): array {
    $page = max(0, (int) $request->query->get('page', 0));
    $limit = min(self::MAX_LIMIT, max(1, (int) $request->query->get('limit', self::DEFAULT_LIMIT)));
    return [$page, $limit];
  }

  /**
   * Serializes a node into the JSON:API-compatible response shape.
   *
   * @param \Drupal\node\NodeInterface $node
   *   The card node to serialize.
   *
   * @return array<string, mixed>
   *   The serialized card data.
   */
  private function serializeCard(NodeInterface $node): array {
    $oracleText = NULL;
    if (!$node->get('field_oracle_text')->isEmpty()) {
      $oracleText = [
        'value' => (string) ($node->get('field_oracle_text')->value ?? ''),
        'format' => $node->get('field_oracle_text')->format,
        'processed' => (string) ($node->get('field_oracle_text')->processed ?? ''),
      ];
    }

    return [
      'id' => $node->uuid(),
      'type' => 'node--mtg_card',
      'attributes' => [
        'title' => (string) $node->label(),
        'field_mana_cost' => (string) ($node->get('field_mana_cost')->value ?? ''),
        'field_cmc' => (float) ($node->get('field_cmc')->value ?? 0),
        'field_type_line' => (string) ($node->get('field_type_line')->value ?? ''),
        'field_colors' => array_column($node->get('field_colors')->getValue(), 'value'),
        'field_color_identity' => array_column($node->get('field_color_identity')->getValue(), 'value'),
        'field_oracle_text' => $oracleText,
        'field_scryfall_id' => (string) ($node->get('field_scryfall_id')->value ?? ''),
        'field_image_uri' => (string) ($node->get('field_image_uri')->value ?? ''),
        'field_is_mana_producer' => (bool) ($node->get('field_is_mana_producer')->value ?? FALSE),
        'field_produced_mana' => array_column($node->get('field_produced_mana')->getValue(), 'value'),
        'field_legal_formats' => array_column($node->get('field_legal_formats')->getValue(), 'value'),
        'field_power' => $node->get('field_power')->value,
        'field_toughness' => $node->get('field_toughness')->value,
        'field_loyalty' => $node->get('field_loyalty')->value,
      ],
    ];
  }

  /**
   * Builds a generic error ResourceResponse.
   *
   * @param string $detail
   *   Human-readable error message.
   * @param int $status
   *   HTTP status code.
   *
   * @return \Drupal\rest\ResourceResponse
   *   The error response.
   */
  private function errorResponse(string $detail, int $status): ResourceResponse {
    return new ResourceResponse(['errors' => [['detail' => $detail]]], $status);
  }

}
