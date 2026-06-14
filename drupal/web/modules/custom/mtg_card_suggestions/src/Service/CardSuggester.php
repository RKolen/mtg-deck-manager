<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Service;

use Drupal\Core\Entity\EntityStorageInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Logger\LoggerChannelInterface;
use Drupal\mtg_card_suggestions\Support\SidecarUrl;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;

/**
 * Generates AI-powered card suggestions for a deck.
 *
 * Pipeline:
 *  1. Fetch all cards in the deck via field_deck_cards paragraphs.
 *  2. Build a semantic query string from card names + oracle text.
 *  3. Run a Milvus vector search (via Search API) to find similar cards.
 *  4. Send candidates + deck context to Ollama for ranked suggestions.
 */
class CardSuggester {

  /**
   * The node entity storage.
   *
   * @var \Drupal\Core\Entity\EntityStorageInterface
   */
  private readonly EntityStorageInterface $nodeStorage;

  /**
   * The Search API index entity storage.
   *
   * @var \Drupal\Core\Entity\EntityStorageInterface
   */
  private readonly EntityStorageInterface $indexStorage;

  /**
   * Constructs a CardSuggester.
   *
   * @param \GuzzleHttp\ClientInterface $httpClient
   *   HTTP client for direct Ollama calls.
   * @param \Drupal\Core\Entity\EntityTypeManagerInterface $entityTypeManager
   *   The entity type manager.
   * @param \Drupal\Core\Logger\LoggerChannelInterface $logger
   *   The logger channel.
   *
   * @throws \Drupal\Component\Plugin\Exception\InvalidPluginDefinitionException
   * @throws \Drupal\Component\Plugin\Exception\PluginNotFoundException
   */
  public function __construct(
    private readonly ClientInterface $httpClient,
    EntityTypeManagerInterface $entityTypeManager,
    private readonly LoggerChannelInterface $logger,
  ) {
    $this->nodeStorage = $entityTypeManager->getStorage('node');
    $this->indexStorage = $entityTypeManager->getStorage('search_api_index');
  }

  /**
   * Generates card suggestions for a given deck node ID.
   *
   * @param int $deckNid
   *   The deck node ID.
   * @param int $limit
   *   Max number of suggestions to return.
   *
   * @return list<array{card: array<string, mixed>, reason: string, score: float}>
   *   Ranked suggestions with reason text and similarity score.
   */
  public function suggest(int $deckNid, int $limit = 10): array {
    $deckCards = $this->fetchDeckCards($deckNid);
    if ($deckCards === []) {
      return [];
    }

    $archetype = $this->detectArchetype($deckCards);
    $semanticQuery = $this->buildSemanticQuery($deckCards, $archetype);
    $candidates = $this->runMilvusSearch($semanticQuery, $limit * 8);
    $candidates = $this->filterAlreadyInDeck($candidates, $deckCards);
    $candidates = $this->filterByColorIdentity($candidates, $archetype['colors']);
    $candidates = array_slice($candidates, 0, $limit * 2);

    if ($candidates === []) {
      return [];
    }

    return $this->rankWithOllama($deckCards, $candidates, $limit, $archetype);
  }

  /**
   * Loads all main-deck cards for a deck via field_deck_cards paragraphs.
   *
   * @param int $deckNid
   *   The deck node ID.
   *
   * @return list<array{nid: int, name: string, oracle_text: string, type_line: string, cmc: float, colors: list<string>, quantity: int}>
   *   Simplified card data for prompt building (main deck only).
   */
  private function fetchDeckCards(int $deckNid): array {
    /** @var \Drupal\node\NodeInterface|null $deck */
    $deck = $this->nodeStorage->load($deckNid);
    if ($deck === NULL || !$deck->hasField('field_deck_cards')) {
      return [];
    }

    $cards = [];
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
      $colors = [];
      if ($card->hasField('field_colors')) {
        foreach ($card->get('field_colors') as $colorItem) {
          $colors[] = (string) $colorItem->value;
        }
      }
      $cards[] = [
        'nid' => (int) $card->id(),
        'name' => (string) $card->label(),
        'oracle_text' => (string) ($card->hasField('field_oracle_text') ? $card->get('field_oracle_text')->value : ''),
        'type_line' => (string) ($card->hasField('field_type_line') ? $card->get('field_type_line')->value : ''),
        'cmc' => (float) ($card->hasField('field_cmc') ? $card->get('field_cmc')->value : 0),
        'colors' => $colors,
        'quantity' => $qty,
      ];
    }

    return $cards;
  }

  /**
   * Derives the deck's archetype from its card composition.
   *
   * Returns a structured description used to frame both the Milvus query
   * and the Ollama ranking prompt so that suggestions stay within the deck's
   * actual game plan.
   *
   * @param list<array<string, mixed>> $deckCards
   *   Enriched deck card data (includes cmc, colors, type_line, quantity).
   *
   * @return array<string, mixed>
   *   Archetype descriptor: speed, colors, win_condition, key_roles, label.
   */
  private function detectArchetype(array $deckCards): array {
    $totalQty = 0;
    $totalCmc = 0.0;
    $nonLandQty = 0;
    $creatureQty = 0;
    $instantSorcQty = 0;
    $colorCounts = [];

    foreach ($deckCards as $card) {
      $qty = (int) ($card['quantity'] ?? 1);
      $totalQty += $qty;
      $cmc = (float) ($card['cmc'] ?? 0);
      $typeLine = (string) ($card['type_line'] ?? '');

      if (stripos($typeLine, 'Land') === FALSE) {
        $totalCmc += $cmc * $qty;
        $nonLandQty += $qty;
        if (stripos($typeLine, 'Creature') !== FALSE) {
          $creatureQty += $qty;
        }
        if (stripos($typeLine, 'Instant') !== FALSE || stripos($typeLine, 'Sorcery') !== FALSE) {
          $instantSorcQty += $qty;
        }
      }

      foreach (($card['colors'] ?? []) as $color) {
        $colorCounts[$color] = ($colorCounts[$color] ?? 0) + $qty;
      }
    }

    $avgCmc = $nonLandQty > 0 ? $totalCmc / $nonLandQty : 2.5;
    arsort($colorCounts);
    $deckColors = array_keys($colorCounts);

    // Classify by speed
    if ($avgCmc < 1.6) {
      $speed = 'ultra-fast aggro';
      $winCondition = 'attack for lethal by turns 3–4 before the opponent stabilises';
      $keyRoles = ['aggressive 1-drop and 2-drop creatures', 'cheap pump spells that trigger heroic or prowess', 'targeted removal to clear blockers'];
      $keyConstraints = 'Low CMC is a feature, not a bug. Do NOT suggest cards above CMC 3. Do NOT suggest mana fixing or ramp. Do NOT suggest late-game threats.';
    }
    elseif ($avgCmc < 2.2) {
      $speed = 'aggressive';
      $winCondition = 'apply early pressure and close out by turns 4–6';
      $keyRoles = ['efficient threats', 'disruption or burn spells', 'cards that generate card advantage'];
      $keyConstraints = 'Prioritise efficiency. Avoid expensive finishers or slow value engines.';
    }
    elseif ($avgCmc > 3.5) {
      $speed = 'midrange or control';
      $winCondition = 'grind value and win in the mid-to-late game';
      $keyRoles = ['resilient threats', 'interaction', 'card advantage engines'];
      $keyConstraints = 'Card quality and resilience matter more than raw speed.';
    }
    else {
      $speed = 'midrange';
      $winCondition = 'balance early pressure with late-game threats';
      $keyRoles = ['efficient 2-for-1 threats', 'flexible interaction'];
      $keyConstraints = 'Balance is key — avoid cards that are too slow or too narrow.';
    }

    // Map color codes to names
    $colorNames = ['W' => 'White', 'U' => 'Blue', 'B' => 'Black', 'R' => 'Red', 'G' => 'Green'];
    $colorLabel = implode('/', array_map(static fn($c) => $colorNames[$c] ?? $c, $deckColors));

    // Detect key keywords from oracle text
    $keywords = [];
    $keywordCounts = [];
    $keywordMap = [
      'heroic' => 'heroic',
      'prowess' => 'prowess',
      'pump' => '+1/+1',
      'trample' => 'trample',
      'lifelink' => 'lifelink',
    ];
    foreach ($deckCards as $card) {
      $text = strtolower((string) ($card['oracle_text'] ?? ''));
      foreach ($keywordMap as $label => $trigger) {
        if (str_contains($text, $trigger)) {
          $keywordCounts[$label] = ($keywordCounts[$label] ?? 0) + (int) ($card['quantity'] ?? 1);
        }
      }
    }
    arsort($keywordCounts);
    $keywords = array_keys(array_slice($keywordCounts, 0, 3));

    return [
      'speed' => $speed,
      'avgCmc' => round($avgCmc, 1),
      'colors' => $deckColors,
      'colorLabel' => $colorLabel,
      'winCondition' => $winCondition,
      'keyRoles' => $keyRoles,
      'keyConstraints' => $keyConstraints,
      'keywords' => $keywords,
      'label' => "{$colorLabel} {$speed}",
    ];
  }

  /**
   * Filters Milvus candidates to those within the deck's color identity.
   *
   * A candidate is allowed if it is colorless OR shares at least one color
   * with the deck. This prevents off-color suggestions like Blue cards
   * appearing in a Red/Green aggro deck.
   *
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Raw Milvus candidates.
   * @param list<string> $deckColors
   *   The deck's color identity (e.g. ['R', 'G']).
   *
   * @return list<array{nid: int, name: string, score: float}>
   *   Filtered candidates.
   */
  private function filterByColorIdentity(array $candidates, array $deckColors): array {
    if ($deckColors === [] || $candidates === []) {
      return $candidates;
    }

    $deckColorSet = array_flip($deckColors);
    $nids = array_column($candidates, 'nid');

    // Batch-load all candidate nodes in one query.
    /** @var array<int, \Drupal\node\NodeInterface> $nodes */
    $nodes = $this->nodeStorage->loadMultiple($nids);

    // Build a nid → card-colors and image_uri map from the batch.
    $colorMap = [];
    $imageMap = [];
    foreach ($nodes as $nid => $node) {
      $imageMap[$nid] = $node->hasField('field_image_uri')
        ? ((string) ($node->get('field_image_uri')->value ?? '')) ?: NULL
        : NULL;
      if (!$node->hasField('field_color_identity')) {
        $colorMap[$nid] = [];
        continue;
      }
      $cardColors = [];
      foreach ($node->get('field_color_identity') as $item) {
        $cardColors[] = (string) $item->value;
      }
      $colorMap[$nid] = $cardColors;
    }

    $filtered = [];
    foreach ($candidates as $c) {
      $c['image_uri'] = $imageMap[$c['nid']] ?? NULL;
      $cardColors = $colorMap[$c['nid']] ?? [];

      if ($cardColors === []) {
        // Colorless — always eligible.
        $filtered[] = $c;
        continue;
      }

      // Include only if every color of the card is in the deck's palette.
      $offColor = FALSE;
      foreach ($cardColors as $color) {
        if (!isset($deckColorSet[$color])) {
          $offColor = TRUE;
          break;
        }
      }
      if (!$offColor) {
        $filtered[] = $c;
      }
    }

    return $filtered;
  }

  /**
   * Builds a short semantic query string from the deck's card names and types.
   *
   * @param list<array{nid: int, name: string, oracle_text: string, type_line: string}> $deckCards
   *   Deck card data.
   *
   * @return string
   *   A space-joined string of card names and type lines.
   */
  /**
   * Builds a Milvus semantic query that encodes the deck's game plan,
   * not just card names, so vector search finds strategically relevant cards.
   *
   * @param list<array<string, mixed>> $deckCards
   *   Enriched deck card data.
   * @param array<string, mixed> $archetype
   *   Archetype descriptor from detectArchetype().
   *
   * @return string
   *   Query string for the Milvus embedding search.
   */
  private function buildSemanticQuery(array $deckCards, array $archetype): string {
    // Lead with the archetype so the embedding captures the strategic intent.
    $parts = [
      $archetype['label'],
      $archetype['winCondition'],
      implode(' ', $archetype['keywords']),
    ];

    // Add the deck's key non-land card names (those with highest quantity first).
    usort($deckCards, static fn($a, $b) => ($b['quantity'] ?? 1) <=> ($a['quantity'] ?? 1));
    foreach (array_slice($deckCards, 0, 15) as $card) {
      if (stripos((string) ($card['type_line'] ?? ''), 'Land') === FALSE) {
        $parts[] = $card['name'];
        // Pull the most relevant keyword phrases from oracle text.
        $oracle = strtolower((string) ($card['oracle_text'] ?? ''));
        foreach (['heroic', 'prowess', 'trample', 'haste', '+1/+1 counter'] as $kw) {
          if (str_contains($oracle, $kw)) {
            $parts[] = $kw;
          }
        }
      }
    }

    return implode(' ', array_unique($parts));
  }

  /**
   * Queries the Milvus Search API index for semantically similar cards.
   *
   * @param string $query
   *   The semantic query string.
   * @param int $fetchLimit
   *   How many candidates to fetch.
   *
   * @return list<array{nid: int, name: string, score: float}>
   *   Candidate cards with similarity scores.
   */
  private function runMilvusSearch(string $query, int $fetchLimit): array {
    /** @var \Drupal\search_api\IndexInterface|null $index */
    $index = $this->indexStorage->load('milvus_card_index');
    if ($index === NULL) {
      $this->logger->warning('Milvus card index not found. Make sure milvus_card_index is enabled.');
      return [];
    }

    try {
      $apiQuery = $index->query();
      $apiQuery->keys($query);
      $apiQuery->range(0, $fetchLimit);
      $results = $apiQuery->execute()->getResultItems();

      $candidates = [];
      foreach ($results as $item) {
        $nid = (int) ($item->getField('nid')?->getValues()[0] ?? 0);
        if ($nid === 0) {
          continue;
        }
        $candidates[] = [
          'nid' => $nid,
          'name' => (string) ($item->getField('title')?->getValues()[0] ?? ''),
          'score' => round((float) $item->getScore(), 4),
        ];
      }
      return $candidates;
    }
    catch (\Exception $e) {
      $this->logger->warning('Milvus search failed: @msg', ['@msg' => $e->getMessage()]);
      return [];
    }
  }

  /**
   * Removes cards already present in the deck from the candidate list.
   *
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Milvus candidates.
   * @param list<array{nid: int, name: string, oracle_text: string, type_line: string}> $deckCards
   *   Cards already in the deck.
   *
   * @return list<array{nid: int, name: string, score: float}>
   *   Filtered candidates.
   */
  private function filterAlreadyInDeck(array $candidates, array $deckCards): array {
    $deckNids = array_column($deckCards, 'nid');
    $deckNidSet = array_flip($deckNids);
    $deckNames = array_map('strtolower', array_column($deckCards, 'name'));
    $deckNameSet = array_flip($deckNames);

    // Also deduplicate candidates by card name — Milvus indexes multiple
    // printings of the same card so the same name can appear many times.
    $seenNames = [];
    $result = [];
    foreach ($candidates as $c) {
      if (isset($deckNidSet[$c['nid']])) {
        continue;
      }
      $nameLower = strtolower($c['name']);
      if (isset($deckNameSet[$nameLower]) || isset($seenNames[$nameLower])) {
        continue;
      }
      $seenNames[$nameLower] = TRUE;
      $result[] = $c;
    }
    return $result;
  }

  /**
   * Uses Ollama to rank and explain the top candidates for the deck.
   *
   * Falls back to returning candidates with generic reasons if Ollama fails.
   *
   * @param list<array{nid: int, name: string, oracle_text: string, type_line: string}> $deckCards
   *   Cards in the deck (used for context).
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Semantically similar cards to evaluate.
   * @param int $limit
   *   Max suggestions to return.
   *
   * @return list<array{card: array<string, mixed>, reason: string, score: float}>
   *   Ranked suggestions.
   */
  private function rankWithOllama(array $deckCards, array $candidates, int $limit, array $archetype = []): array {
    $model = getenv('OLLAMA_CHAT_MODEL');
    $url = SidecarUrl::chatEndpoint();

    if (!$url || !$model) {
      return $this->buildFallbackSuggestions($candidates, $limit);
    }

    try {
      $response = $this->httpClient->request('POST', $url, [
        'json' => [
          'model'  => $model,
          'stream' => FALSE,
          'messages' => [
            ['role' => 'system', 'content' => $this->buildSystemPrompt($archetype)],
            ['role' => 'user', 'content' => $this->buildUserPrompt($deckCards, $candidates, $limit, $archetype)],
          ],
          'options' => ['num_ctx' => 4096],
        ],
        'timeout' => 600,
      ]);
      $body = json_decode((string) $response->getBody(), TRUE);
      $text = (string) ($body['message']['content'] ?? '');
      // Strip thinking blocks from qwen3 models.
      $text = (string) preg_replace('/<think>.*?<\/think>/s', '', $text);
      $ranked = $this->parseSuggestions($text, $candidates);

      if ($ranked !== []) {
        return array_slice($ranked, 0, $limit);
      }
    }
    catch (GuzzleException $e) {
      $this->logger->warning('Ollama ranking failed: @msg', ['@msg' => $e->getMessage()]);
    }

    return $this->buildFallbackSuggestions($candidates, $limit);
  }

  /**
   * Returns the system prompt for the Ollama ranking call.
   *
   * @return string
   *   The system prompt.
   */
  private function buildSystemPrompt(array $archetype): string {
    $label = $archetype['label'] ?? 'unknown archetype';
    $winCon = $archetype['winCondition'] ?? 'win the game';
    $constraints = $archetype['keyConstraints'] ?? '';
    $rolesStr = implode('; ', $archetype['keyRoles'] ?? []);

    return <<<PROMPT
You are a Magic: The Gathering deck-building expert specialising in optimising existing strategies.

CRITICAL: This deck is a {$label} deck. Its goal is to {$winCon}.

What this deck needs: {$rolesStr}.

Constraints you MUST respect:
{$constraints}

Given the deck's current cards and a list of candidates filtered to the correct colors and strategy,
return ONLY the candidates that genuinely fit this specific deck's game plan.
Reject any candidate that contradicts the archetype (e.g. slow finishers in an ultra-fast deck,
off-strategy value engines, or cards that require a different win condition).

Respond ONLY with valid JSON — no text outside the array.
Format: [{"name": "Card Name", "reason": "One sentence: which specific role in THIS deck this card fills"}, ...]
PROMPT;
  }

  /**
   * Builds the user message with full archetype framing.
   *
   * @param list<array<string, mixed>> $deckCards
   *   Cards in the deck (enriched with cmc, colors, quantity).
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Filtered candidates.
   * @param int $limit
   *   How many suggestions to request.
   * @param array<string, mixed> $archetype
   *   Archetype descriptor.
   *
   * @return string
   *   The user prompt.
   */
  private function buildUserPrompt(array $deckCards, array $candidates, int $limit, array $archetype = []): string {
    // Show the deck's key spells (non-lands, by quantity desc) to anchor context.
    $keyCards = array_filter($deckCards, static fn($c) => stripos((string) ($c['type_line'] ?? ''), 'Land') === FALSE);
    usort($keyCards, static fn($a, $b) => ($b['quantity'] ?? 1) <=> ($a['quantity'] ?? 1));
    $keyCardLines = [];
    foreach (array_slice($keyCards, 0, 12) as $card) {
      $qty = (int) ($card['quantity'] ?? 1);
      $cmc = number_format((float) ($card['cmc'] ?? 0), 1);
      $keyCardLines[] = "  {$qty}x {$card['name']} (CMC {$cmc}, {$card['type_line']})";
    }
    $deckContext = implode("\n", $keyCardLines);

    $candidateList = implode(', ', array_column($candidates, 'name'));
    $avgCmc = $archetype['avgCmc'] ?? '?';
    $label = $archetype['label'] ?? 'deck';

    return <<<PROMPT
This is a {$label} deck (avg CMC {$avgCmc}).

Key spells already in the deck:
{$deckContext}

Candidate cards (already filtered to correct colors):
{$candidateList}

Select the {$limit} candidates that best serve THIS deck's specific game plan.
Explain exactly how each card contributes to the win condition.
Return JSON only.
PROMPT;
  }

  /**
   * Parses the Ollama JSON response into suggestion rows.
   *
   * @param string $text
   *   Raw LLM output.
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Candidates to cross-reference for nid/score lookup.
   *
   * @return list<array{card: array<string, mixed>, reason: string, score: float}>
   *   Parsed suggestions, or empty on failure.
   */
  private function parseSuggestions(string $text, array $candidates): array {
    $cleaned = (string) preg_replace('/```(?:json)?\s*|\s*```/', '', $text);
    $cleaned = trim($cleaned);

    if (preg_match('/\[.*\]/s', $cleaned, $matches)) {
      $cleaned = $matches[0];
    }

    try {
      $data = json_decode($cleaned, TRUE, 512, JSON_THROW_ON_ERROR);
    }
    catch (\JsonException) {
      return [];
    }

    if (!is_array($data)) {
      return [];
    }

    $candidateByName = [];
    foreach ($candidates as $c) {
      $candidateByName[strtolower($c['name'])] = $c;
    }

    $suggestions = [];
    foreach ($data as $row) {
      if (!is_array($row) || empty($row['name'])) {
        continue;
      }
      $key = strtolower((string) $row['name']);
      $candidate = $candidateByName[$key] ?? NULL;
      if ($candidate === NULL) {
        continue;
      }
      $suggestions[] = [
        'card' => [
          'nid'       => $candidate['nid'],
          'name'      => $candidate['name'],
          'image_uri' => $candidate['image_uri'] ?? NULL,
        ],
        'reason' => (string) ($row['reason'] ?? ''),
        'score' => $candidate['score'],
      ];
    }

    return $suggestions;
  }

  /**
   * Builds a fallback suggestion list when Ollama is unavailable.
   *
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Milvus candidates sorted by score.
   * @param int $limit
   *   Max items to return.
   *
   * @return list<array{card: array<string, mixed>, reason: string, score: float}>
   *   Suggestions without Ollama reasoning.
   */
  private function buildFallbackSuggestions(array $candidates, int $limit): array {
    $suggestions = [];
    foreach (array_slice($candidates, 0, $limit) as $c) {
      $suggestions[] = [
        'card' => [
          'nid'       => $c['nid'],
          'name'      => $c['name'],
          'image_uri' => $c['image_uri'] ?? NULL,
        ],
        'reason' => 'Semantically similar to cards already in your deck.',
        'score' => $c['score'],
      ];
    }
    return $suggestions;
  }

}
