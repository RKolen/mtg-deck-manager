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
   *   manaProducer, rarity, page, limit.
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

    if ($q !== '') {
      $query->keys($q);
      $query->setFulltextFields(['title', 'field_oracle_text']);
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

    $type = trim((string) ($params['type'] ?? ''));
    if ($type !== '') {
      $conditions->addCondition('field_type_line_string', $type, 'CONTAINS');
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

    if ($hasCondition) {
      $query->addConditionGroup($conditions);
    }
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
