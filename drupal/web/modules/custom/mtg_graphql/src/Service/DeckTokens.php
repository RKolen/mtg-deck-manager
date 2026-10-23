<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\mtg_scryfall_sync\Service\CardParts;
use Drupal\node\NodeInterface;

/**
 * Lists the tokens, emblems and game pieces a deck can make.
 *
 * Built from the Scryfall links in mtg_card_part, not from oracle text.
 * Printings of a token merge when name, type, power, toughness, colors and
 * abilities all match, so a Food from any set is one entry while a 0/0 and
 * a 1/1 Construct stay apart. Card quantities do not matter.
 */
final class DeckTokens {

  /**
   * Node IDs loaded per query.
   */
  private const CHUNK = 500;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly Connection $database,
    private readonly CardParts $cardParts,
  ) {}

  /**
   * Tokens for a deck's main deck, sideboard and commander.
   *
   * Maybeboard cards are left out, like elsewhere in the deck tools.
   *
   * @return list<array{card: ?\Drupal\node\NodeInterface, name: string, typeLine: string, power: ?string, toughness: ?string, oracleText: ?string, kind: string, madeBy: list<string>, owned: int}>
   *   One entry per distinct token, sorted by kind and name.
   */
  public function forDeck(string $deckUuid): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $decks = $storage->loadByProperties(['uuid' => $deckUuid, 'type' => 'deck']);
    $deck = reset($decks);
    if (!$deck instanceof NodeInterface) {
      return [];
    }

    $titles = [];
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $slot) {
      $card = $slot->get('field_card')->entity;
      if ($card instanceof NodeInterface) {
        $titles[$card->label()] = TRUE;
      }
    }
    $commander = $deck->hasField('field_commander') ? $deck->get('field_commander')->entity : NULL;
    if ($commander instanceof NodeInterface) {
      $titles[$commander->label()] = TRUE;
    }

    $links = $this->cardParts->forCards(array_keys($titles));
    if ($links === []) {
      return [];
    }
    $printings = $this->tokensByScryfallId(array_column($links, 'part_id'));

    $groups = [];
    foreach ($links as $link) {
      $node = $printings[$link['part_id']] ?? NULL;
      $info = $node instanceof NodeInterface ? self::nodeInfo($node) : [
        'name' => $link['name'],
        'typeLine' => $link['type_line'],
        'power' => NULL,
        'toughness' => NULL,
        'colors' => [],
        'oracleText' => NULL,
      ];
      $key = self::tokenKey($info['name'], $info['typeLine'], $info['power'], $info['toughness'], $info['colors'], $info['oracleText'] ?? '');
      if (!isset($groups[$key])) {
        $groups[$key] = $info + ['card' => NULL, 'madeBy' => [], 'owned' => 0];
      }
      $groups[$key]['madeBy'][$link['card_name']] = TRUE;
      if ($groups[$key]['card'] === NULL && $node instanceof NodeInterface && (string) $node->get('field_image_uri')->value !== '') {
        $groups[$key]['card'] = $node;
      }
    }

    foreach ($this->ownedTokens(array_unique(array_column($groups, 'name'))) as [$node, $quantity]) {
      $info = self::nodeInfo($node);
      $key = self::tokenKey($info['name'], $info['typeLine'], $info['power'], $info['toughness'], $info['colors'], $info['oracleText'] ?? '');
      if (isset($groups[$key])) {
        $groups[$key]['owned'] += $quantity;
        // Show the printing the owner actually has.
        $groups[$key]['card'] = $node;
      }
    }

    $result = [];
    foreach ($groups as $group) {
      $madeBy = array_keys($group['madeBy']);
      sort($madeBy);
      $result[] = [
        'card' => $group['card'],
        'name' => $group['name'],
        'typeLine' => $group['typeLine'],
        'power' => $group['power'],
        'toughness' => $group['toughness'],
        'oracleText' => $group['oracleText'],
        'kind' => self::kind($group['typeLine']),
        'madeBy' => $madeBy,
        'owned' => $group['owned'],
      ];
    }
    $order = ['token' => 0, 'emblem' => 1, 'game' => 2];
    $sortKey = static fn(array $t): array => [$order[$t['kind']], $t['name'], $t['power'] ?? '', $t['typeLine']];
    usort($result, static fn(array $a, array $b): int => $sortKey($a) <=> $sortKey($b));
    return $result;
  }

  /**
   * Identity of a token: printings with the same key are interchangeable.
   *
   * Reminder text in parentheses and letter case are ignored, so printings
   * worded slightly differently still match.
   *
   * @param string $name
   *   Token name.
   * @param string $typeLine
   *   Type line.
   * @param string|null $power
   *   Power, if any.
   * @param string|null $toughness
   *   Toughness, if any.
   * @param string[] $colors
   *   Color letters.
   * @param string $oracleText
   *   Rules text.
   */
  public static function tokenKey(string $name, string $typeLine, ?string $power, ?string $toughness, array $colors, string $oracleText): string {
    sort($colors);
    $text = preg_replace('/\([^)]*\)/', '', $oracleText) ?? $oracleText;
    $text = strtolower(trim(preg_replace('/\s+/', ' ', $text) ?? $text));
    return implode('|', [
      strtolower(trim($name)),
      strtolower(trim($typeLine)),
      $power ?? '',
      $toughness ?? '',
      implode('', $colors),
      $text,
    ]);
  }

  /**
   * Kind of part from its type line: token, emblem or game piece.
   */
  public static function kind(string $typeLine): string {
    if (str_starts_with($typeLine, 'Emblem')) {
      return 'emblem';
    }
    if (str_starts_with($typeLine, 'Dungeon') || str_starts_with($typeLine, 'Card')) {
      return 'game';
    }
    return 'token';
  }

  /**
   * Characteristics of a token printing.
   *
   * @return array{name: string, typeLine: string, power: ?string, toughness: ?string, colors: string[], oracleText: ?string}
   *   Values used for display and for the token key.
   */
  private static function nodeInfo(NodeInterface $node): array {
    $value = static fn(string $field): ?string => $node->hasField($field) && $node->get($field)->value !== NULL
      ? (string) $node->get($field)->value
      : NULL;
    $colors = $node->hasField('field_colors')
      ? array_map('strval', array_column($node->get('field_colors')->getValue(), 'value'))
      : [];
    return [
      'name' => (string) $node->label(),
      'typeLine' => (string) ($value('field_type_line') ?? ''),
      'power' => $value('field_power'),
      'toughness' => $value('field_toughness'),
      'colors' => $colors,
      'oracleText' => $value('field_oracle_text'),
    ];
  }

  /**
   * Imported token printings by Scryfall ID.
   *
   * @param string[] $ids
   *   Scryfall IDs.
   *
   * @return array<string, \Drupal\node\NodeInterface>
   *   Nodes keyed by Scryfall ID; printings not imported are missing.
   */
  private function tokensByScryfallId(array $ids): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $found = [];
    foreach (array_chunk(array_values(array_unique($ids)), self::CHUNK) as $chunk) {
      $nids = $storage->getQuery()->accessCheck(FALSE)
        ->condition('type', 'mtg_card')
        ->condition('field_scryfall_id', $chunk, 'IN')
        ->execute();
      foreach ($storage->loadMultiple($nids) as $node) {
        if ($node instanceof NodeInterface) {
          $found[(string) $node->get('field_scryfall_id')->value] = $node;
        }
      }
    }
    return $found;
  }

  /**
   * Owned token printings with these names, with copies owned.
   *
   * @param string[] $names
   *   Token names.
   *
   * @return list<array{0: \Drupal\node\NodeInterface, 1: int}>
   *   Each owned printing and its regular plus foil copies.
   */
  private function ownedTokens(array $names): array {
    if ($names === []) {
      return [];
    }
    $query = $this->database->select('node_field_data', 'card');
    $query->join('node__field_card', 'ref', 'ref.field_card_target_id = card.nid');
    $query->join('node_field_data', 'cc', "cc.nid = ref.entity_id AND cc.type = 'collection_card'");
    $query->leftJoin('node__field_quantity_owned', 'q', 'q.entity_id = cc.nid');
    $query->leftJoin('node__field_quantity_foil', 'f', 'f.entity_id = cc.nid');
    $query->addField('card', 'nid');
    $query->addExpression('SUM(COALESCE(q.field_quantity_owned_value, 0) + COALESCE(f.field_quantity_foil_value, 0))', 'copies');
    $query->condition('card.type', 'mtg_card')
      ->condition('card.title', array_values($names), 'IN')
      ->groupBy('card.nid')
      ->having('SUM(COALESCE(q.field_quantity_owned_value, 0) + COALESCE(f.field_quantity_foil_value, 0)) > 0');
    $copies = $query->execute()->fetchAllKeyed();
    if ($copies === []) {
      return [];
    }
    $owned = [];
    foreach ($this->entityTypeManager->getStorage('node')->loadMultiple(array_keys($copies)) as $nid => $node) {
      if ($node instanceof NodeInterface) {
        $owned[] = [$node, (int) $copies[$nid]];
      }
    }
    return $owned;
  }

}
