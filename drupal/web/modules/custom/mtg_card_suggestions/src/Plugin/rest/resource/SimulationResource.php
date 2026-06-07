<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Plugin\rest\resource;

use Drupal\Core\Cache\CacheableMetadata;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\ServiceUnavailableHttpException;

/**
 * Proxies simulation requests to the Python mtg-sim service.
 *
 * POST /api/simulate.
 *
 * Request body:
 *   playerDeckId    (int)     - Drupal node ID of the player's deck
 *   opponentArchetype (string) - Archetype name matching a meta_deck title
 *   format          (string)  - MTG format, e.g. "Modern"
 *   games           (int)     - Number of games, 1–200 (default 50)
 *   useLlm          (bool)    - Use Ollama for MCTS board evaluation (slower)
 *
 * Response: the full simulation statistics JSON from the Python service,
 * also persisted as a simulation_result node for historical comparison.
 *
 * Requires MTG_SIM_SERVICE_URL in DDEV web_environment (config.local.yaml).
 *
 * @RestResource(
 *   id = "simulation",
 *   label = @Translation("MTG Simulation"),
 *   uri_paths = {
 *     "create" = "/api/simulate"
 *   }
 * )
 */
final class SimulationResource extends ResourceBase {

  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    array $serializer_formats,
    LoggerInterface $logger,
    private readonly ClientInterface $httpClient,
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
      $container->get('logger.factory')->get('mtg_card_suggestions'),
      $container->get('http_client'),
      $container->get('entity_type.manager'),
    );
  }

  /**
   * Handles POST /api/simulate.
   *
   * @param mixed $data
   *   Deserialized request body.
   */
  public function post(mixed $data): ResourceResponse {
    if (
      !is_array($data)
      || !isset($data['playerDeckId'])
      || empty($data['opponentArchetype'])
    ) {
      throw new BadRequestHttpException(
        'Request body must include playerDeckId (int) and opponentArchetype (string).',
      );
    }

    $payload = [
      'playerDeckId'      => (int) $data['playerDeckId'],
      'opponentArchetype' => (string) $data['opponentArchetype'],
      'format'            => (string) ($data['format'] ?? 'Modern'),
      'games'             => min(200, max(1, (int) ($data['games'] ?? 50))),
      'useLlm'            => (bool) ($data['useLlm'] ?? FALSE),
      'pilotSide'         => (string) ($data['pilotSide'] ?? 'auto'),
    ];

    $simServiceUrl = (string) getenv('MTG_SIM_SERVICE_URL');
    if ($simServiceUrl === '') {
      throw new ServiceUnavailableHttpException(
        NULL,
        'MTG_SIM_SERVICE_URL env var is not set. Set it to the sim service base URL and restart DDEV.',
      );
    }

    $simBase = rtrim($simServiceUrl, '/');
    try {
      $this->httpClient->get($simBase . '/health', ['timeout' => 5, 'connect_timeout' => 3]);
    }
    catch (GuzzleException $e) {
      $this->logger->error('Simulation service health check failed: @msg', ['@msg' => $e->getMessage()]);
      throw new ServiceUnavailableHttpException(
        NULL,
        'Simulation service is not reachable at ' . $simBase
        . '. Start it with ./start.sh from the repo root.',
      );
    }

    try {
      $httpResponse = $this->httpClient->post(
        $simBase . '/simulate',
        [
          'json'             => $payload,
          'timeout'          => 3600,
          'connect_timeout'  => 10,
        ],
      );
      $result = json_decode((string) $httpResponse->getBody(), TRUE, 512, JSON_THROW_ON_ERROR);
    }
    catch (GuzzleException $e) {
      $this->logger->error('Simulation service unavailable: @msg', ['@msg' => $e->getMessage()]);
      throw new ServiceUnavailableHttpException(
        NULL,
        'Simulation request failed: ' . $e->getMessage()
        . '. Long runs (50+ games with LLM pilots) can take several minutes.',
      );
    }

    // Persist the result as a simulation_result node.
    $this->persistResult($payload, $result);

    $response = new ResourceResponse($result);
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);
    return $response;
  }

  /**
   * Saves the simulation result as a simulation_result node.
   *
   * @param array<string, mixed> $request
   *   The request payload sent to the Python service.
   * @param array<string, mixed> $result
   *   The result returned by the Python service.
   */
  private function persistResult(array $request, array $result): void {
    try {
      $storage = $this->entityTypeManager->getStorage('node');
      $node = $storage->create([
        'type'   => 'simulation_result',
        'title'  => sprintf(
          '%s vs %s (%s, %d games)',
          $result['playerDeck'] ?? 'Unknown',
          $request['opponentArchetype'],
          $request['format'],
          $result['games'] ?? 0,
        ),
        'status' => 1,
        'field_sim_player_deck_nid' => $request['playerDeckId'],
        'field_sim_opponent'        => $request['opponentArchetype'],
        'field_sim_format'          => $request['format'],
        'field_sim_games'           => $result['games'] ?? 0,
        'field_sim_wins'            => $result['wins'] ?? 0,
        'field_sim_win_rate'        => $result['winRate'] ?? 0.0,
        'field_sim_result_json'     => json_encode($result),
      ]);
      $node->save();
    }
    catch (\Throwable $e) {
      // Non-fatal — result already returned to the client.
      $this->logger->warning('Could not persist simulation result: @msg', ['@msg' => $e->getMessage()]);
    }
  }

}
