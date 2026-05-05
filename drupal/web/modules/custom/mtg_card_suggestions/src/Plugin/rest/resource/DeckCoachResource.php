<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Plugin\rest\resource;

use Drupal\ai\AiProviderPluginManager;
use Drupal\ai\OperationType\Chat\ChatInput;
use Drupal\ai\OperationType\Chat\ChatMessage;
use Drupal\Core\Cache\CacheableMetadata;
use Drupal\rest\Plugin\ResourceBase;
use Drupal\rest\ResourceResponse;
use Psr\Log\LoggerInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * REST resource for AI-powered deck coaching.
 *
 * POST /api/deck-coach
 *
 * Accepts pre-computed analysis metrics from the Gatsby frontend and asks
 * Ollama to interpret them in the context of the deck's format. The numbers
 * are computed client-side so this endpoint never needs to load deck cards.
 *
 * Request body:
 *   format       - e.g. "Modern"
 *   deckTitle    - deck name for context
 *   metrics      - output of deckAnalysis.ts (avgCmc, colorSourcePct, etc.)
 *
 * Response:
 *   { coaching: "<four paragraphs of plain-language coaching>" }
 *
 * @RestResource(
 *   id = "deck_coach",
 *   label = @Translation("MTG Deck Coach"),
 *   uri_paths = {
 *     "create" = "/api/deck-coach"
 *   }
 * )
 */
final class DeckCoachResource extends ResourceBase {

  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    array $serializer_formats,
    LoggerInterface $logger,
    private readonly AiProviderPluginManager $aiProvider,
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
      $container->get('ai.provider'),
    );
  }

  /**
   * Handles POST /api/deck-coach.
   *
   * @param mixed $data
   *   Deserialized request body.
   *
   * @return \Drupal\rest\ResourceResponse
   *   JSON response with a 'coaching' key containing the LLM output.
   */
  public function post(mixed $data): ResourceResponse {
    if (
      !is_array($data)
      || empty($data['format'])
      || empty($data['deckTitle'])
      || !isset($data['metrics'])
      || !is_array($data['metrics'])
    ) {
      return $this->errorResponse(
        'Request body must include format (string), deckTitle (string), and metrics (object).',
        400,
      );
    }

    $coaching = $this->runOllama(
      $this->buildPrompt(
        (string) $data['format'],
        (string) $data['deckTitle'],
        $data['metrics'],
      ),
    );

    $response = new ResourceResponse(['coaching' => $coaching]);
    $cache = new CacheableMetadata();
    $cache->setCacheMaxAge(0);
    $response->addCacheableDependency($cache);
    return $response;
  }

  /**
   * Builds the structured coaching prompt from the analysis metrics.
   *
   * @param string $format
   *   MTG format name.
   * @param string $deckTitle
   *   Deck title for context.
   * @param array<string, mixed> $metrics
   *   Analysis metrics from deckAnalysis.ts.
   *
   * @return string
   *   The prompt string for Ollama.
   */
  private function buildPrompt(string $format, string $deckTitle, array $metrics): string {
    $avgCmc = number_format((float) ($metrics['avgCmc'] ?? 0), 1);
    $landCount = (int) ($metrics['landCount'] ?? 0);
    $totalSources = number_format((float) ($metrics['totalManaSources'] ?? 0), 1);

    // Colour source / pip lines — only include colours with any presence.
    $colorSourcePct = is_array($metrics['colorSourcePct'] ?? NULL) ? $metrics['colorSourcePct'] : [];
    $colorPipPct = is_array($metrics['colorPipPct'] ?? NULL) ? $metrics['colorPipPct'] : [];
    $colors = array_unique(array_merge(array_keys($colorSourcePct), array_keys($colorPipPct)));

    $colorLines = [];
    foreach ($colors as $c) {
      $src = round((float) ($colorSourcePct[$c] ?? 0), 1);
      $pip = round((float) ($colorPipPct[$c] ?? 0), 1);
      $colorLines[] = "  {$c}: {$src}% sources, {$pip}% pip demand";
    }
    $colorBlock = $colorLines !== [] ? implode("\n", $colorLines) : '  (no coloured sources)';

    // Mana hand probabilities.
    $manaHandProb = is_array($metrics['manaHandProb'] ?? NULL) ? $metrics['manaHandProb'] : [];
    $handLines = [];
    foreach ($manaHandProb as $c => $turns) {
      if (!is_array($turns)) {
        continue;
      }
      $t2 = isset($turns['turn2']) ? round((float) $turns['turn2'] * 100, 1) . '%' : 'n/a';
      $t3 = isset($turns['turn3']) ? round((float) $turns['turn3'] * 100, 1) . '%' : 'n/a';
      $handLines[] = "  {$c}: {$t2} by turn 2, {$t3} by turn 3";
    }
    $handBlock = $handLines !== [] ? implode("\n", $handLines) : '  (no data)';

    // CMC curve summary.
    $histogram = is_array($metrics['cmcHistogram'] ?? NULL) ? $metrics['cmcHistogram'] : [];
    $curveParts = [];
    for ($i = 0; $i <= 6; $i++) {
      $count = (int) ($histogram[(string) $i] ?? $histogram[$i] ?? 0);
      if ($count > 0) {
        $curveParts[] = "{$count} at CMC {$i}";
      }
    }
    $high = (int) ($histogram['7+'] ?? 0);
    if ($high > 0) {
      $curveParts[] = "{$high} at CMC 7+";
    }
    $curveStr = $curveParts !== [] ? implode(', ', $curveParts) : 'no data';

    // Non-land producer context.
    $manaSources = is_array($metrics['manaSources'] ?? NULL) ? $metrics['manaSources'] : [];
    $nonLand = (int) ($manaSources['nonLandProducers'] ?? 0);
    $producerTypes = implode(', ', (array) ($manaSources['producerTypes'] ?? []));
    $sourceNote = $nonLand > 0
      ? "{$landCount} lands + {$nonLand} non-land producers ({$producerTypes}) = {$totalSources} effective sources"
      : "{$landCount} lands = {$totalSources} effective sources";

    return <<<PROMPT
You are a Magic: The Gathering deck-building coach.

Format: {$format}. Deck: "{$deckTitle}".

Mana analysis:
- Average CMC: {$avgCmc}
- {$sourceNote}
- Colour source % vs pip demand %:
{$colorBlock}
- Probability of drawing at least one source of each colour:
{$handBlock}
- Curve: {$curveStr}

Interpret these numbers for a {$format} player. Be specific:
1. Is the manabase well-calibrated for the pip demand?
2. Are any colour splashes reliable enough to cast spells on curve?
3. Is the CMC curve appropriate for the format?
4. What is the single biggest mana risk in this deck?

Keep the response to four short paragraphs. Use plain language, no bullet points.
PROMPT;
  }

  /**
   * Sends the prompt to the default Ollama chat provider.
   *
   * Falls back to a user-readable error string rather than throwing, so the
   * frontend always receives a 200 response it can display.
   *
   * @param string $prompt
   *   The coaching prompt.
   *
   * @return string
   *   The LLM response text, or an error message.
   */
  private function runOllama(string $prompt): string {
    $default = $this->aiProvider->getDefaultProviderForOperationType('chat');
    if (!is_array($default) || empty($default['provider_id'])) {
      return 'AI provider not configured. Make sure Ollama is running and the ai_provider_ollama module is enabled.';
    }

    try {
      $provider = $this->aiProvider->createInstance($default['provider_id']);
      $input = new ChatInput([new ChatMessage('user', $prompt)]);
      $output = $provider->chat($input, (string) $default['model_id']);
      return (string) $output->getNormalized()->getText();
    }
    catch (\Throwable $e) {
      $this->logger->warning('Deck coach Ollama call failed: @msg', ['@msg' => $e->getMessage()]);
      return 'Could not reach the AI model. Make sure Ollama is running with a chat model loaded.';
    }
  }

  /**
   * Builds a generic error ResourceResponse.
   */
  private function errorResponse(string $detail, int $status): ResourceResponse {
    return new ResourceResponse(['errors' => [['detail' => $detail]]], $status);
  }

}
