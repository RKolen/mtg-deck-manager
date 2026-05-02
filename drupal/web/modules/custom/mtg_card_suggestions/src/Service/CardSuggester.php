<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Service;

use Drupal\ai\AiProviderPluginManager;
use Drupal\ai\OperationType\Chat\ChatInput;
use Drupal\ai\OperationType\Chat\ChatMessage;
use Drupal\Core\Entity\EntityStorageInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Logger\LoggerChannelInterface;

/**
 * Generates AI-powered card suggestions for a deck.
 *
 * Pipeline:
 *  1. Fetch all cards in the deck via deck_card entity references.
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
   * @param \Drupal\ai\AiProviderPluginManager $aiProvider
   *   The AI provider plugin manager.
   * @param \Drupal\Core\Entity\EntityTypeManagerInterface $entityTypeManager
   *   The entity type manager.
   * @param \Drupal\Core\Logger\LoggerChannelInterface $logger
   *   The logger channel.
   *
   * @throws \Drupal\Component\Plugin\Exception\InvalidPluginDefinitionException
   * @throws \Drupal\Component\Plugin\Exception\PluginNotFoundException
   */
  public function __construct(
    private readonly AiProviderPluginManager $aiProvider,
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

    $semanticQuery = $this->buildSemanticQuery($deckCards);
    $candidates = $this->runMilvusSearch($semanticQuery, $limit * 5);
    $candidates = $this->filterAlreadyInDeck($candidates, $deckCards);
    $candidates = array_slice($candidates, 0, $limit * 2);

    if ($candidates === []) {
      return [];
    }

    return $this->rankWithOllama($deckCards, $candidates, $limit);
  }

  /**
   * Loads all card nodes that belong to a deck.
   *
   * @param int $deckNid
   *   The deck node ID.
   *
   * @return list<array{nid: int, name: string, oracle_text: string, type_line: string}>
   *   Simplified card data for prompt building.
   */
  private function fetchDeckCards(int $deckNid): array {
    $deckCardNids = $this->nodeStorage
      ->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'deck_card')
      ->condition('field_deck', $deckNid)
      ->execute();

    if ($deckCardNids === []) {
      return [];
    }

    /** @var list<\Drupal\node\NodeInterface> $deckCardNodes */
    $deckCardNodes = $this->nodeStorage->loadMultiple(array_values($deckCardNids));

    $cards = [];
    foreach ($deckCardNodes as $deckCard) {
      $cardRef = $deckCard->get('field_card');
      if ($cardRef->isEmpty()) {
        continue;
      }
      /** @var \Drupal\node\NodeInterface|null $card */
      $card = $cardRef->entity;
      if ($card === NULL) {
        continue;
      }
      $cards[] = [
        'nid' => (int) $card->id(),
        'name' => (string) $card->label(),
        'oracle_text' => (string) ($card->hasField('field_oracle_text') ? $card->get('field_oracle_text')->value : ''),
        'type_line' => (string) ($card->hasField('field_type_line') ? $card->get('field_type_line')->value : ''),
      ];
    }

    return $cards;
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
  private function buildSemanticQuery(array $deckCards): string {
    $parts = [];
    foreach (array_slice($deckCards, 0, 20) as $card) {
      $parts[] = $card['name'];
      if ($card['type_line'] !== '') {
        $parts[] = $card['type_line'];
      }
    }
    return implode(' ', $parts);
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

    return array_values(
      array_filter($candidates, static fn(array $c) => !isset($deckNidSet[$c['nid']]))
    );
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
  private function rankWithOllama(array $deckCards, array $candidates, int $limit): array {
    $default = $this->aiProvider->getDefaultProviderForOperationType('chat');
    if (!is_array($default) || empty($default['provider_id'])) {
      return $this->buildFallbackSuggestions($candidates, $limit);
    }

    try {
      $provider = $this->aiProvider->createInstance($default['provider_id']);
      $input = new ChatInput([
        new ChatMessage('system', $this->buildSystemPrompt()),
        new ChatMessage('user', $this->buildUserPrompt($deckCards, $candidates, $limit)),
      ]);

      /** @var \Drupal\ai\OperationType\Chat\ChatOutput $output */
      $output = $provider->chat($input, (string) $default['model_id']);
      $text = (string) $output->getNormalized()->getText();
      $ranked = $this->parseSuggestions($text, $candidates);

      if ($ranked !== []) {
        return array_slice($ranked, 0, $limit);
      }
    }
    catch (\Throwable $e) {
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
  private function buildSystemPrompt(): string {
    return <<<PROMPT
You are a Magic: The Gathering deck-building assistant.
Given a list of cards already in a deck and a list of candidate cards,
return a JSON array of the best additions ranked by synergy.

Respond ONLY with valid JSON — no explanation outside the JSON.
Format: [{"name": "Card Name", "reason": "One-sentence explanation of synergy"}, ...]
PROMPT;
  }

  /**
   * Builds the user message listing deck cards and candidates.
   *
   * @param list<array{nid: int, name: string, oracle_text: string, type_line: string}> $deckCards
   *   Cards in the deck.
   * @param list<array{nid: int, name: string, score: float}> $candidates
   *   Candidate cards.
   * @param int $limit
   *   How many suggestions to request.
   *
   * @return string
   *   The user prompt.
   */
  private function buildUserPrompt(array $deckCards, array $candidates, int $limit): string {
    $deckList = implode(', ', array_column($deckCards, 'name'));
    $candidateList = implode(', ', array_column($candidates, 'name'));

    return "Deck contains: {$deckList}\n\nCandidate additions: {$candidateList}\n\nReturn the top {$limit} suggestions as JSON.";
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
          'nid' => $candidate['nid'],
          'name' => $candidate['name'],
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
          'nid' => $c['nid'],
          'name' => $c['name'],
        ],
        'reason' => 'Semantically similar to cards already in your deck.',
        'score' => $c['score'],
      ];
    }
    return $suggestions;
  }

}
