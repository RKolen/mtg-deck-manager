<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Service;

use Drupal\ai\AiProviderPluginManager;
use Drupal\ai\OperationType\Chat\ChatInput;
use Drupal\ai\OperationType\Chat\ChatMessage;
use Drupal\Core\Entity\EntityStorageInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Logger\LoggerChannelInterface;
use Drupal\node\NodeInterface;

/**
 * Generates LLM-powered matchup advice for a player deck vs a meta archetype.
 *
 * Pipeline:
 *  1. Load the player's deck cards from deck_card nodes.
 *  2. Load the meta_deck node for the opponent archetype.
 *  3. Compute basic deck stats (avg CMC, colours, land count) for both.
 *  4. Build a structured Ollama prompt with card lists + key threats.
 *  5. Parse and return the JSON response.
 */
class MatchupAdvisor {

  private readonly EntityStorageInterface $nodeStorage;

  public function __construct(
    private readonly AiProviderPluginManager $aiProvider,
    EntityTypeManagerInterface $entityTypeManager,
    private readonly LoggerChannelInterface $logger,
  ) {
    $this->nodeStorage = $entityTypeManager->getStorage('node');
  }

  /**
   * Returns matchup advice for the given player deck vs opponent archetype.
   *
   * @param int $playerDeckNid
   *   Node ID of the player's deck node.
   * @param string $opponentArchetype
   *   Archetype name, e.g. "Jund" — must match a meta_deck title.
   * @param float $confidence
   *   Classifier confidence (0–1), used for prompt context.
   * @param string $format
   *   MTG format name, e.g. "Modern".
   *
   * @return array{dynamic: string, threats: list<string>, sideboard: array{in: list<string>, out: list<string>}, keyPlay: string}
   *   Parsed advice, or a fallback with error messages.
   */
  public function advise(
    int $playerDeckNid,
    string $opponentArchetype,
    float $confidence,
    string $format,
  ): array {
    $playerCards = $this->loadDeckCards($playerDeckNid);
    $metaDeck = $this->loadMetaDeck($opponentArchetype, $format);

    if ($metaDeck === NULL) {
      return $this->errorAdvice("Meta deck not found for archetype '{$opponentArchetype}' in {$format}.");
    }

    $prompt = $this->buildPrompt($playerCards, $metaDeck, $opponentArchetype, $confidence, $format);
    return $this->runOllama($prompt);
  }

  /**
   * Loads and summarises main-deck cards via field_deck_cards paragraphs.
   *
   * @param int $deckNid
   *   Deck node ID.
   *
   * @return array{list: string, avgCmc: float, colors: list<string>, landCount: int, oneDrop: int}
   */
  private function loadDeckCards(int $deckNid): array {
    /** @var \Drupal\node\NodeInterface|null $deck */
    $deck = $this->nodeStorage->load($deckNid);
    $empty = ['list' => '(empty deck)', 'avgCmc' => 0.0, 'colors' => [], 'landCount' => 0, 'oneDrop' => 0];
    if ($deck === NULL || !$deck->hasField('field_deck_cards')) {
      return $empty;
    }

    $lines = [];
    $totalCmc = 0.0;
    $totalNonLand = 0;
    $colorSet = [];
    $landCount = 0;
    $oneDrop = 0;

    foreach ($deck->get('field_deck_cards') as $item) {
      /** @var \Drupal\paragraphs\Entity\Paragraph|null $para */
      $para = $item->entity;
      if ($para === NULL) {
        continue;
      }
      $isSideboard = (bool) ($para->hasField('field_is_sideboard') ? $para->get('field_is_sideboard')->value : FALSE);
      if ($isSideboard) {
        continue;
      }
      $cardRef = $para->hasField('field_card') ? $para->get('field_card') : NULL;
      if ($cardRef === NULL || $cardRef->isEmpty()) {
        continue;
      }
      /** @var \Drupal\node\NodeInterface|null $card */
      $card = $cardRef->entity;
      if ($card === NULL) {
        continue;
      }
      $qty = (int) ($para->hasField('field_quantity') ? $para->get('field_quantity')->value : 1);
      $name = (string) $card->label();
      $cmc = (float) ($card->hasField('field_cmc') ? $card->get('field_cmc')->value : 0);
      $typeLine = (string) ($card->hasField('field_type_line') ? $card->get('field_type_line')->value : '');
      $isLand = stripos($typeLine, 'land') !== FALSE;

      $lines[] = "{$qty}x {$name}";
      if ($isLand) {
        $landCount += $qty;
      }
      else {
        $totalCmc += $cmc * $qty;
        $totalNonLand += $qty;
        if ($cmc <= 1) {
          $oneDrop += $qty;
        }
      }
      if ($card->hasField('field_colors')) {
        foreach ($card->get('field_colors')->getValue() as $c) {
          $colorSet[$c['value']] = TRUE;
        }
      }
    }

    return [
      'list'      => implode(', ', $lines),
      'avgCmc'    => $totalNonLand > 0 ? round($totalCmc / $totalNonLand, 2) : 0.0,
      'colors'    => array_keys($colorSet),
      'landCount' => $landCount,
      'oneDrop'   => $oneDrop,
    ];
  }

  /**
   * Loads the meta_deck node matching the archetype and format.
   *
   * @param string $archetype
   *   Archetype title to search for.
   * @param string $format
   *   MTG format name.
   *
   * @return \Drupal\node\NodeInterface|null
   */
  private function loadMetaDeck(string $archetype, string $format): ?NodeInterface {
    $nids = $this->nodeStorage
      ->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'meta_deck')
      ->condition('title', $archetype)
      ->condition('field_format', $format)
      ->range(0, 1)
      ->execute();

    if ($nids === []) {
      // Try without format constraint in case the archetype spans formats.
      $nids = $this->nodeStorage
        ->getQuery()
        ->accessCheck(FALSE)
        ->condition('type', 'meta_deck')
        ->condition('title', $archetype)
        ->range(0, 1)
        ->execute();
    }

    if ($nids === []) {
      return NULL;
    }

    $node = $this->nodeStorage->load(reset($nids));
    return $node instanceof NodeInterface ? $node : NULL;
  }

  /**
   * Builds the structured matchup advice prompt.
   */
  private function buildPrompt(
    array $playerCards,
    NodeInterface $metaDeck,
    string $archetype,
    float $confidence,
    string $format,
  ): string {
    $colors = $playerCards['colors'] !== [] ? implode('/', $playerCards['colors']) : 'colourless';
    $playerSummary = implode(', ', array_filter([
      "avg CMC {$playerCards['avgCmc']}",
      "{$playerCards['landCount']} lands",
      "heavy {$colors}",
      $playerCards['oneDrop'] > 0 ? "{$playerCards['oneDrop']} one-drops" : '',
    ]));

    // Opponent archetype.
    $opponentCards = (string) ($metaDeck->get('field_cards')->value ?? '');
    $sideboardGuide = (string) ($metaDeck->get('field_sideboard_guide')->value ?? '');
    $archetype_tags = implode(', ', array_column($metaDeck->get('field_archetype_tags')->getValue(), 'value'));
    $confidencePct = round($confidence * 100);

    // Key threats: oracle text of the key_cards entity references.
    $keyThreatLines = [];
    foreach ($metaDeck->get('field_key_cards') as $ref) {
      /** @var \Drupal\node\NodeInterface|null $keyCard */
      $keyCard = $ref->entity;
      if ($keyCard === NULL) {
        continue;
      }
      $oracle = (string) ($keyCard->get('field_oracle_text')->value ?? '');
      $keyThreatLines[] = "- {$keyCard->label()}: {$oracle}";
      if (count($keyThreatLines) >= 5) {
        break;
      }
    }
    $keyThreatsBlock = $keyThreatLines !== []
      ? implode("\n", $keyThreatLines)
      : '(no key cards configured)';

    // If the meta_deck has a sideboard guide, include it.
    $sideboardSection = $sideboardGuide !== ''
      ? "\nARCHETYPE SIDEBOARD NOTES:\n{$sideboardGuide}"
      : '';

    return <<<PROMPT
You are an expert Magic: The Gathering player competing in {$format}.

YOUR DECK:
{$playerCards['list']}
Analysis: {$playerSummary}

OPPONENT ({$archetype} — {$confidencePct}% confidence, strategy: {$archetype_tags}):
{$opponentCards}
{$sideboardSection}

KEY THREATS TO YOUR DECK:
{$keyThreatsBlock}

Answer these four questions concisely and return ONLY valid JSON, no explanation outside the JSON:
{
  "dynamic": "<one sentence: fundamental matchup dynamic>",
  "threats": ["<card name>", "<card name>"],
  "sideboard": {
    "in":  ["<card name x2>", "<card name x1>"],
    "out": ["<card name x2>", "<card name x1>"]
  },
  "keyPlay": "<single most important play pattern for your side>"
}
PROMPT;
  }

  /**
   * Sends the prompt to Ollama and parses the JSON response.
   *
   * Falls back to an error advice structure rather than throwing.
   *
   * @return array{dynamic: string, threats: list<string>, sideboard: array{in: list<string>, out: list<string>}, keyPlay: string}
   */
  private function runOllama(string $prompt): array {
    $default = $this->aiProvider->getDefaultProviderForOperationType('chat');
    if (!is_array($default) || empty($default['provider_id'])) {
      return $this->errorAdvice('AI provider not configured.');
    }

    try {
      $provider = $this->aiProvider->createInstance($default['provider_id']);
      $input = new ChatInput([new ChatMessage('user', $prompt)]);
      $output = $provider->chat($input, (string) $default['model_id']);
      $text = (string) $output->getNormalized()->getText();
      return $this->parseAdvice($text);
    }
    catch (\Throwable $e) {
      $this->logger->warning('Matchup advisor Ollama call failed: @msg', ['@msg' => $e->getMessage()]);
      return $this->errorAdvice('Could not reach Ollama: ' . $e->getMessage());
    }
  }

  /**
   * Extracts the JSON advice object from the raw LLM output.
   *
   * @return array{dynamic: string, threats: list<string>, sideboard: array{in: list<string>, out: list<string>}, keyPlay: string}
   */
  private function parseAdvice(string $text): array {
    // Strip markdown code fences.
    $cleaned = (string) preg_replace('/```(?:json)?\s*|\s*```/', '', $text);
    $cleaned = trim($cleaned);

    // Extract the first JSON object.
    if (preg_match('/\{.*\}/s', $cleaned, $matches)) {
      $cleaned = $matches[0];
    }

    try {
      $data = json_decode($cleaned, TRUE, 512, JSON_THROW_ON_ERROR);
    }
    catch (\JsonException) {
      return $this->errorAdvice('LLM did not return valid JSON.');
    }

    if (!is_array($data)) {
      return $this->errorAdvice('Unexpected LLM response format.');
    }

    return [
      'dynamic'   => (string) ($data['dynamic'] ?? ''),
      'threats'   => array_values(array_filter((array) ($data['threats'] ?? []), 'is_string')),
      'sideboard' => [
        'in'  => array_values(array_filter((array) ($data['sideboard']['in'] ?? []), 'is_string')),
        'out' => array_values(array_filter((array) ($data['sideboard']['out'] ?? []), 'is_string')),
      ],
      'keyPlay'   => (string) ($data['keyPlay'] ?? ''),
    ];
  }

  /**
   * Returns a failure advice structure with the given error in 'dynamic'.
   *
   * @return array{dynamic: string, threats: list<string>, sideboard: array{in: list<string>, out: list<string>}, keyPlay: string}
   */
  private function errorAdvice(string $message): array {
    return [
      'dynamic'   => $message,
      'threats'   => [],
      'sideboard' => ['in' => [], 'out' => []],
      'keyPlay'   => '',
    ];
  }

}
