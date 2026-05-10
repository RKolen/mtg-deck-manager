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

    $cards = is_array($data['cards'] ?? NULL) ? $data['cards'] : [];
    $archetype = $this->detectArchetype($data['metrics'], $cards);

    $coaching = $this->runOllama(
      $this->buildPrompt(
        (string) $data['format'],
        (string) $data['deckTitle'],
        $data['metrics'],
        $archetype,
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
  /**
   * Classifies the deck's archetype from metrics and card list.
   *
   * @param array<string, mixed> $metrics
   *   Analysis metrics from the frontend.
   * @param list<array<string, mixed>> $cards
   *   Card list sent from the frontend (name, type, cmc).
   *
   * @return array<string, string>
   *   Archetype descriptor: speed, label, landNorm, caveats.
   */
  private function detectArchetype(array $metrics, array $cards): array {
    $avgCmc = (float) ($metrics['avgCmc'] ?? 2.5);
    $landCount = (int) ($metrics['landCount'] ?? 24);

    // Detect keywords from card list
    $keywords = [];
    foreach ($cards as $card) {
      $oracle = strtolower((string) ($card['oracle'] ?? $card['oracle_text'] ?? ''));
      $type = strtolower((string) ($card['type'] ?? $card['type_line'] ?? ''));
      foreach (['heroic', 'prowess', 'trample', 'haste', 'infect', 'storm'] as $kw) {
        if (str_contains($oracle, $kw) || str_contains($type, $kw)) {
          $keywords[$kw] = ($keywords[$kw] ?? 0) + 1;
        }
      }
    }
    arsort($keywords);
    $topKeyword = array_key_first($keywords) ?? '';

    if ($avgCmc < 1.6) {
      return [
        'speed' => 'ultra-fast aggro',
        'label' => "ultra-fast aggro ({$topKeyword})",
        'landNorm' => '14–18 lands is CORRECT for this archetype — the deck is designed to empty its hand by turn 3.',
        'cmcNorm' => "An average CMC of {$avgCmc} is intentional — this deck wins BECAUSE of its low curve, not despite it.",
        'coachingFocus' => 'Identify mana screw/flood risks on the specific early turns this deck needs. Do NOT recommend more lands, higher CMC cards, or a different game plan.',
        'winCon' => 'attack for lethal by turn 3–4, typically by pumping a creature with heroic or prowess triggers',
      ];
    }
    if ($avgCmc < 2.2) {
      return [
        'speed' => 'aggressive',
        'label' => 'aggressive',
        'landNorm' => '18–22 lands is normal for this archetype.',
        'cmcNorm' => "An average CMC of {$avgCmc} is appropriate for an aggressive deck.",
        'coachingFocus' => 'Focus on consistency of early plays and reliability of the colour sources for key spells.',
        'winCon' => 'apply consistent early pressure and close out by turns 4–6',
      ];
    }
    if ($avgCmc > 3.5) {
      return [
        'speed' => 'midrange or control',
        'label' => 'midrange/control',
        'landNorm' => '24–26 lands is standard.',
        'cmcNorm' => "An average CMC of {$avgCmc} requires reliable mana development.",
        'coachingFocus' => 'Evaluate whether colour sources match spell requirements across all stages of the game.',
        'winCon' => 'grind resources and win in the mid-to-late game',
      ];
    }
    return [
      'speed' => 'midrange',
      'label' => 'midrange',
      'landNorm' => '22–24 lands is typical.',
      'cmcNorm' => "An average CMC of {$avgCmc} is standard for midrange.",
      'coachingFocus' => 'Check that colour sources match pip demands at each point on the curve.',
      'winCon' => 'balance early plays with late-game threats',
    ];
  }

  private function buildPrompt(string $format, string $deckTitle, array $metrics, array $archetype): string {
    $avgCmc = number_format((float) ($metrics['avgCmc'] ?? 0), 1);
    $landCount = (int) ($metrics['landCount'] ?? 0);
    $totalSources = number_format((float) ($metrics['totalManaSources'] ?? 0), 1);

    // Only show colours that are actually significant (>5% pip demand).
    $colorSourcePct = is_array($metrics['colorSourcePct'] ?? NULL) ? $metrics['colorSourcePct'] : [];
    $colorPipPct = is_array($metrics['colorPipPct'] ?? NULL) ? $metrics['colorPipPct'] : [];
    $mainColors = array_filter($colorPipPct, static fn($v) => (float) $v >= 5.0);
    $colorLines = [];
    foreach ($mainColors as $c => $pip) {
      $src = round((float) ($colorSourcePct[$c] ?? 0), 1);
      $pip = round((float) $pip, 1);
      $colorLines[] = "  {$c}: {$src}% sources vs {$pip}% pip demand";
    }
    $colorBlock = $colorLines !== [] ? implode("\n", $colorLines) : '  (no significant coloured sources)';

    // Mana hand probabilities — only for main colours.
    $manaHandProb = is_array($metrics['manaHandProb'] ?? NULL) ? $metrics['manaHandProb'] : [];
    $handLines = [];
    foreach ($manaHandProb as $c => $turns) {
      if (!is_array($turns) || !isset($mainColors[$c])) {
        continue;
      }
      $t2 = isset($turns['turn2']) ? round((float) $turns['turn2'] * 100, 1) . '%' : 'n/a';
      $t3 = isset($turns['turn3']) ? round((float) $turns['turn3'] * 100, 1) . '%' : 'n/a';
      $handLines[] = "  {$c}: {$t2} by turn 2, {$t3} by turn 3";
    }
    $handBlock = $handLines !== [] ? implode("\n", $handLines) : '  (no data)';

    // Curve.
    $histogram = is_array($metrics['cmcHistogram'] ?? NULL) ? $metrics['cmcHistogram'] : [];
    $curveParts = [];
    for ($i = 0; $i <= 5; $i++) {
      $count = (int) ($histogram[(string) $i] ?? $histogram[$i] ?? 0);
      if ($count > 0) {
        $curveParts[] = "{$count}× CMC{$i}";
      }
    }
    $curveStr = $curveParts !== [] ? implode(', ', $curveParts) : 'no data';

    $manaSources = is_array($metrics['manaSources'] ?? NULL) ? $metrics['manaSources'] : [];
    $nonLand = (int) ($manaSources['nonLandProducers'] ?? 0);
    $sourceNote = $nonLand > 0
      ? "{$landCount} lands + {$nonLand} non-land mana sources = {$totalSources} effective"
      : "{$landCount} lands";

    $archetypeLabel = $archetype['label'] ?? 'unknown';
    $landNorm = $archetype['landNorm'] ?? '';
    $cmcNorm = $archetype['cmcNorm'] ?? '';
    $coachFocus = $archetype['coachingFocus'] ?? '';
    $winCon = $archetype['winCon'] ?? 'win the game';

    return <<<PROMPT
You are a Magic: The Gathering deck-building coach who understands diverse archetypes.

CONTEXT — read this carefully before analysing:
Deck: "{$deckTitle}" — Format: {$format}
Archetype: {$archetypeLabel}
Win condition: {$winCon}
{$landNorm}
{$cmcNorm}
Coaching focus for this archetype: {$coachFocus}

MANA DATA:
- Average CMC: {$avgCmc}
- Mana sources: {$sourceNote}
- Colour sources vs pip demand (main colours only):
{$colorBlock}
- Probability of drawing ≥1 source of each main colour:
{$handBlock}
- Curve: {$curveStr}

Coaching task — answer these four questions specifically for this {$archetypeLabel} deck:
1. Are the colour sources well-matched to the specific spells this deck casts on turns 1, 2, and 3?
2. Could the deck be colour-screwed on its key early plays, and if so, which colours are the bottleneck?
3. Given the archetype and win condition, is there any meaningful risk from the current land count?
4. What is the ONE most impactful improvement to the manabase for THIS specific strategy?

Keep the response to four short paragraphs. Focus exclusively on this deck's actual game plan. Do not give generic MTG advice.
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
