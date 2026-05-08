<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Plugin\rest\resource;

use Drupal\Core\Cache\CacheableMetadata;
use Drupal\mtg_card_suggestions\Service\MatchupAdvisor;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;

/**
 * REST resource for LLM-powered matchup advice.
 *
 * POST /api/matchup-advice
 *
 * Request body:
 *   playerDeckId  (int)    - Drupal node ID of the player's deck
 *   opponentArchetype (string) - Archetype name matching a meta_deck title
 *   confidence    (float)  - Classifier P(archetype), 0–1
 *   format        (string) - MTG format, e.g. "Modern"
 *
 * Response:
 *   { dynamic, threats[], sideboard: { in[], out[] }, keyPlay }
 *
 * @RestResource(
 *   id = "matchup_advice",
 *   label = @Translation("MTG Matchup Advice"),
 *   uri_paths = {
 *     "create" = "/api/matchup-advice"
 *   }
 * )
 */
final class MatchupAdviceResource extends ResourceBase {

  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    array $serializer_formats,
    LoggerInterface $logger,
    private readonly MatchupAdvisor $advisor,
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
      $container->get('logger.factory')->get('mtg_card_suggestions'),
      $container->get('mtg_card_suggestions.matchup_advisor'),
    );
  }

  /**
   * Handles POST /api/matchup-advice.
   *
   * @param mixed $data
   *   Deserialized request body.
   */
  public function post(mixed $data): ResourceResponse {
    if (
      !is_array($data)
      || !isset($data['playerDeckId'])
      || empty($data['opponentArchetype'])
      || empty($data['format'])
    ) {
      throw new BadRequestHttpException(
        'Request body must include playerDeckId (int), opponentArchetype (string), and format (string).',
      );
    }

    $advice = $this->advisor->advise(
      (int) $data['playerDeckId'],
      (string) $data['opponentArchetype'],
      (float) ($data['confidence'] ?? 1.0),
      (string) $data['format'],
    );

    $response = new ResourceResponse($advice);
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);
    return $response;
  }

}
