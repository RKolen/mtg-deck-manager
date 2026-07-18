<?php

declare(strict_types=1);

namespace Drupal\mtg_card_search;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\search_api\IndexInterface;
use Drupal\search_api\Query\QueryInterface;
use Psr\Log\LoggerInterface;

/**
 * Solr-backed card search shared by REST and GraphQL.
 */
final class CardSearchService {

  private const INDEX_ID = 'mtg_card_search';

  private const MAX_LIMIT = 100;

  private const DEFAULT_LIMIT = 20;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly LoggerInterface $logger,
  ) {}

  /**
   * @param array<string, mixed> $params
   *   Keys: q, type, oracleText, legalIn, cmcMin, cmcMax, colors, colorIdentity,
   *   manaProducer, rarity, setCodes, setExclude, deckIds, deckExclude, page, limit.
   *
   * @return array{cards: \Drupal\node\NodeInterface[], count: int, pages: int}
   */
  public function search(array $params): array {
    $index = $this->loadIndex();
    if ($index === NULL) {
      return ['cards' => [], 'count' => 0, 'pages' => 0];
    }

    $page = max(0, (int) ($params['page'] ?? 0));
    $limit = min(self::MAX_LIMIT, max(1, (int) ($params['limit'] ?? self::DEFAULT_LIMIT)));

    $query = $index->query();
    $query->range($page * $limit, $limit);
    $this->applyFulltextSearch($query, $params);
    $this->applyConditions($query, $params);

    $results = $query->execute();
    $count = $results->getResultCount();

    $cards = [];
    foreach ($results->getResultItems() as $item) {
      $object = $item->getOriginalObject();
      if ($object === NULL) {
        continue;
      }
      $node = $object->getValue();
      if ($node instanceof NodeInterface) {
        $cards[] = $node;
      }
    }

    return [
      'cards' => $cards,
      'count' => $count,
      'pages' => (int) ceil($count / max(1, $limit)),
    ];
  }

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
   * @param array<string, mixed> $params
   */
  private function applyFulltextSearch(QueryInterface $query, array $params): void {
    $q = trim((string) ($params['q'] ?? ''));
    $oracleText = trim((string) ($params['oracleText'] ?? ''));

    // Search API allows one keys() call. Scope each field separately:
    // - name alone → title only (never oracle)
    // - oracle alone → oracle only
    // - both → oracle fulltext here; title constrained via nids in applyConditions
    if ($q !== '' && $oracleText === '') {
      $query->keys($q);
      $query->setFulltextFields(['title']);
    }
    elseif ($oracleText !== '') {
      $query->keys($oracleText);
      $query->setFulltextFields(['field_oracle_text']);
    }
  }

  /**
   * @param array<string, mixed> $params
   */
  private function applyConditions(QueryInterface $query, array $params): void {
    $conditions = $query->createConditionGroup('AND');
    $hasCondition = FALSE;

    $q = trim((string) ($params['q'] ?? ''));
    $oracleText = trim((string) ($params['oracleText'] ?? ''));
    // When both name and oracle are set, constrain title via SQL (keys used for oracle).
    if ($q !== '' && $oracleText !== '') {
      $nids = $this->nidsWithTitleContains($q);
      $conditions->addCondition('nid', $nids === [] ? [-1] : $nids, 'IN');
      $hasCondition = TRUE;
    }

    $type = trim((string) ($params['type'] ?? ''));
    if ($type !== '') {
      // Use the text field — Solr string CONTAINS is effectively exact-match only,
      // so "Land" missed "Basic Land — Mountain".
      $conditions->addCondition('field_type_line', $type, 'CONTAINS');
      $hasCondition = TRUE;
    }

    $legalIn = trim((string) ($params['legalIn'] ?? ''));
    if ($legalIn !== '') {
      $conditions->addCondition('field_legal_formats', $legalIn);
      $hasCondition = TRUE;
    }

    if (isset($params['cmcMin']) && is_numeric($params['cmcMin'])) {
      $conditions->addCondition('field_cmc', (float) $params['cmcMin'], '>=');
      $hasCondition = TRUE;
    }

    if (isset($params['cmcMax']) && is_numeric($params['cmcMax'])) {
      $conditions->addCondition('field_cmc', (float) $params['cmcMax'], '<=');
      $hasCondition = TRUE;
    }

    foreach ($this->sanitizeColors($params['colors'] ?? []) as $color) {
      $conditions->addCondition('field_colors', $color);
      $hasCondition = TRUE;
    }

    foreach ($this->sanitizeColors($params['colorIdentity'] ?? []) as $color) {
      $conditions->addCondition('field_color_identity', $color);
      $hasCondition = TRUE;
    }

    if (array_key_exists('manaProducer', $params) && $params['manaProducer'] !== NULL) {
      $conditions->addCondition('field_is_mana_producer', (bool) $params['manaProducer']);
      $hasCondition = TRUE;
    }

    $rarity = trim((string) ($params['rarity'] ?? ''));
    if ($rarity !== '' && in_array($rarity, ['common', 'uncommon', 'rare', 'mythic'], TRUE)) {
      $conditions->addCondition('field_rarity', $rarity);
      $hasCondition = TRUE;
    }

    $setCodes = $this->sanitizeSetCodes($params['setCodes'] ?? []);
    if ($setCodes !== []) {
      $exclude = !empty($params['setExclude']);
      if ($exclude) {
        foreach ($setCodes as $code) {
          $conditions->addCondition('field_set_code', $code, '<>');
        }
      }
      else {
        $setGroup = $query->createConditionGroup('OR');
        foreach ($setCodes as $code) {
          $setGroup->addCondition('field_set_code', $code);
        }
        $conditions->addConditionGroup($setGroup);
      }
      $hasCondition = TRUE;
    }

    $deckIds = $this->sanitizeDeckIds($params['deckIds'] ?? []);
    if ($deckIds !== []) {
      $cardNids = $this->cardNidsInDecks($deckIds);
      $excludeDeck = !empty($params['deckExclude']);
      if (!$excludeDeck) {
        // Empty deck → no matches.
        $conditions->addCondition('nid', $cardNids === [] ? [-1] : $cardNids, 'IN');
      }
      elseif ($cardNids !== []) {
        $conditions->addCondition('nid', $cardNids, 'NOT IN');
      }
      $hasCondition = TRUE;
    }

    if ($hasCondition) {
      $query->addConditionGroup($conditions);
    }
  }

  /**
   * @param mixed $raw
   *   Raw deck ID list (nids or UUIDs).
   *
   * @return string[]
   */
  private function sanitizeDeckIds(mixed $raw): array {
    if (!is_array($raw)) {
      return [];
    }
    $valid = [];
    foreach ($raw as $id) {
      $id = trim((string) $id);
      if ($id === '' || in_array($id, $valid, TRUE)) {
        continue;
      }
      if (ctype_digit($id) || preg_match('/^[a-f0-9-]{36}$/i', $id)) {
        $valid[] = $id;
      }
    }
    return $valid;
  }

  /**
   * @param string[] $deckIds
   *   Deck nids or UUIDs.
   *
   * @return int[]
   *   Distinct mtg_card node IDs used in those decks.
   */
  private function cardNidsInDecks(array $deckIds): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $cardNids = [];

    foreach ($deckIds as $deckId) {
      $deck = NULL;
      if (ctype_digit($deckId)) {
        $loaded = $storage->load((int) $deckId);
        if ($loaded && $loaded->bundle() === 'deck') {
          $deck = $loaded;
        }
      }
      else {
        $found = $storage->loadByProperties(['type' => 'deck', 'uuid' => $deckId]);
        $deck = $found ? reset($found) : NULL;
      }
      if ($deck === NULL || !$deck->hasField('field_deck_cards')) {
        continue;
      }
      foreach ($deck->get('field_deck_cards')->referencedEntities() as $para) {
        if (!$para->hasField('field_card') || $para->get('field_card')->isEmpty()) {
          continue;
        }
        $card = $para->get('field_card')->entity;
        if ($card !== NULL) {
          $cardNids[(int) $card->id()] = (int) $card->id();
        }
      }
    }

    return array_values($cardNids);
  }

  /**
   * Card node IDs whose title contains $name (DB collation handles case).
   *
   * @return int[]
   */
  private function nidsWithTitleContains(string $name): array {
    $ids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'mtg_card')
      ->condition('status', 1)
      ->condition('title', $name, 'CONTAINS')
      ->range(0, 5000)
      ->execute();
    return array_map('intval', array_values($ids));
  }

  /**
   * @param mixed $raw
   *   Raw set code list (array or null).
   *
   * @return string[]
   *   Lowercase Scryfall set codes.
   */
  private function sanitizeSetCodes(mixed $raw): array {
    if (!is_array($raw)) {
      return [];
    }
    $valid = [];
    foreach ($raw as $code) {
      $normalized = strtolower(trim((string) $code));
      if ($normalized !== '' && preg_match('/^[a-z0-9]{2,6}$/', $normalized) && !in_array($normalized, $valid, TRUE)) {
        $valid[] = $normalized;
      }
    }
    return $valid;
  }

  /**
   * @param mixed[] $colors
   *
   * @return string[]
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

}
