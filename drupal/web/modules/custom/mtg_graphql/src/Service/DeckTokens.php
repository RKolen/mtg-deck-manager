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

  /**
   * Face-down reminder cards, by the rules text that calls for them.
   *
   * Scryfall does not link morph or manifest cards to these reminder cards,
   * so they are found from the deck cards' oracle text instead.
   */
  private const REMINDERS = [
    'Morph' => '/\b(mega)?morph\b/i',
    'Manifest' => '/\bmanifest(s|ed)?\b/i',
    'A Mysterious Creature' => '/\b(disguise|cloak(s|ed)?)\b/i',
  ];

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
   * @return list<array{card: ?\Drupal\node\NodeInterface, priceEur: ?float, priceUsd: ?float, name: string, typeLine: string, power: ?string, toughness: ?string, colors: string[], oracleText: ?string, kind: string, madeBy: list<string>, owned: int}>
   *   One entry per distinct token, sorted by kind and name.
   */
  public function forDeck(string $deckUuid): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $decks = $storage->loadByProperties(['uuid' => $deckUuid, 'type' => 'deck']);
    $deck = reset($decks);
    if (!$deck instanceof NodeInterface) {
      return [];
    }

    // Deck card names with their rules text.
    $titles = [];
    $cards = [];
    foreach ($deck->get('field_deck_cards')->referencedEntities() as $slot) {
      $cards[] = $slot->get('field_card')->entity;
    }
    $cards[] = $deck->hasField('field_commander') ? $deck->get('field_commander')->entity : NULL;
    foreach ($cards as $card) {
      if ($card instanceof NodeInterface) {
        $titles[(string) $card->label()] = (string) ($card->get('field_oracle_text')->value ?? '');
      }
    }

    $links = array_merge(
      $this->cardParts->forCards(array_keys($titles)),
      $this->reminderLinks($titles),
    );
    if ($links === []) {
      return [];
    }
    $printings = $this->tokensByScryfallId(array_column($links, 'part_id'));

    $groups = [];
    $addTo = static function (array $info, string $maker) use (&$groups): string {
      $key = self::tokenKey($info['name'], $info['typeLine'], $info['power'], $info['toughness'], $info['colors'], $info['oracleText'] ?? '');
      if (!isset($groups[$key])) {
        $groups[$key] = $info + [
          'card' => NULL,
          'madeBy' => [],
          'owned' => 0,
          'priceEur' => NULL,
          'priceUsd' => NULL,
          'cheapest' => NULL,
          'cheapestPrice' => NULL,
        ];
      }
      $groups[$key]['madeBy'][$maker] = TRUE;
      return $key;
    };

    // Links to imported printings first: they carry the real stats.
    $unresolved = [];
    foreach ($links as $link) {
      $node = $printings[$link['part_id']] ?? NULL;
      if (!$node instanceof NodeInterface) {
        $unresolved[] = $link;
        continue;
      }
      $key = $addTo(self::nodeInfo($node), $link['card_name']);
      if ($groups[$key]['card'] === NULL && (string) $node->get('field_image_uri')->value !== '') {
        $groups[$key]['card'] = $node;
      }
    }

    // A link to a printing that was never imported (e.g. a digital one) has
    // no stats. Drop it when the card already makes that token, join the
    // only token with that name and type, or else list it on its own.
    foreach ($unresolved as $link) {
      $sameName = array_keys(array_filter($groups, static fn(array $g): bool =>
        strcasecmp($g['name'], $link['name']) === 0 && strcasecmp($g['typeLine'], $link['type_line']) === 0));
      $alreadyMade = array_filter($sameName, static fn(string $key): bool => isset($groups[$key]['madeBy'][$link['card_name']]));
      if ($alreadyMade !== []) {
        continue;
      }
      if (count($sameName) === 1) {
        $groups[$sameName[0]]['madeBy'][$link['card_name']] = TRUE;
        continue;
      }
      $addTo([
        'name' => $link['name'],
        'typeLine' => $link['type_line'],
        'power' => NULL,
        'toughness' => NULL,
        'colors' => [],
        'oracleText' => NULL,
      ], $link['card_name']);
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

    $this->applyCheapestPrices($groups);

    $result = [];
    foreach ($groups as $group) {
      $madeBy = array_keys($group['madeBy']);
      sort($madeBy);
      // A missing token shows the printing that is cheapest to buy.
      $card = $group['owned'] < 1 && $group['cheapest'] instanceof NodeInterface ? $group['cheapest'] : $group['card'];
      $result[] = [
        'card' => $card,
        'priceEur' => $group['priceEur'],
        'priceUsd' => $group['priceUsd'],
        'name' => $group['name'],
        'typeLine' => $group['typeLine'],
        'power' => $group['power'],
        'toughness' => $group['toughness'],
        'colors' => $group['colors'],
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
   *
   * Face-down reminder cards are typed just "Creature" and count as game
   * pieces.
   */
  public static function kind(string $typeLine): string {
    if (str_starts_with($typeLine, 'Emblem')) {
      return 'emblem';
    }
    if (str_starts_with($typeLine, 'Dungeon') || str_starts_with($typeLine, 'Card') || $typeLine === 'Creature') {
      return 'game';
    }
    return 'token';
  }

  /**
   * Links to face-down reminder cards for deck cards whose text calls for them.
   *
   * @param array<string, string> $oracleByTitle
   *   Deck card rules text keyed by card name.
   *
   * @return list<array{card_name: string, part_id: string, name: string, type_line: string, component: string}>
   *   Links in the same shape as CardParts::forCards(), one per printing.
   */
  private function reminderLinks(array $oracleByTitle): array {
    $links = [];
    $storage = $this->entityTypeManager->getStorage('node');
    foreach (self::REMINDERS as $reminder => $pattern) {
      $makers = array_keys(array_filter($oracleByTitle, static fn(string $text): bool => preg_match($pattern, $text) === 1));
      if ($makers === []) {
        continue;
      }
      $nids = $storage->getQuery()->accessCheck(FALSE)
        ->condition('type', 'mtg_card')
        ->condition('title', $reminder)
        ->condition('field_type_line', 'Creature')
        ->execute();
      foreach ($storage->loadMultiple($nids) as $node) {
        $id = (string) $node->get('field_scryfall_id')->value;
        foreach ($makers as $maker) {
          $links[] = [
            'card_name' => $maker,
            'part_id' => $id,
            'name' => $reminder,
            'type_line' => 'Creature',
            'component' => 'reminder',
          ];
        }
      }
    }
    return $links;
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
   * Sets the cheapest price of each token across all matching printings.
   *
   * Every printing with the same name, stats and abilities counts, not only
   * the ones Scryfall links to the deck's cards. Per currency the regular
   * price is used, or the foil price when no regular price exists.
   *
   * @param array<string, array<string, mixed>> $groups
   *   Token groups keyed by token key; priceEur, priceUsd and cheapest are
   *   filled in.
   */
  private function applyCheapestPrices(array &$groups): void {
    $names = array_values(array_unique(array_column($groups, 'name')));
    if ($names === []) {
      return;
    }
    $storage = $this->entityTypeManager->getStorage('node');
    $nids = $storage->getQuery()->accessCheck(FALSE)
      ->condition('type', 'mtg_card')
      ->condition('title', $names, 'IN')
      ->execute();
    foreach (array_chunk(array_values($nids), self::CHUNK) as $chunk) {
      foreach ($storage->loadMultiple($chunk) as $node) {
        if (!$node instanceof NodeInterface) {
          continue;
        }
        $info = self::nodeInfo($node);
        $key = self::tokenKey($info['name'], $info['typeLine'], $info['power'], $info['toughness'], $info['colors'], $info['oracleText'] ?? '');
        if (!isset($groups[$key])) {
          continue;
        }
        $eur = self::price($node, 'field_price_eur', 'field_price_eur_foil');
        $usd = self::price($node, 'field_price_usd', 'field_price_usd_foil');
        if ($eur !== NULL && ($groups[$key]['priceEur'] === NULL || $eur < $groups[$key]['priceEur'])) {
          $groups[$key]['priceEur'] = $eur;
        }
        if ($usd !== NULL && ($groups[$key]['priceUsd'] === NULL || $usd < $groups[$key]['priceUsd'])) {
          $groups[$key]['priceUsd'] = $usd;
        }
        // Cheapest printing to show for a missing token: by EUR, else USD.
        $rank = $eur ?? $usd;
        $hasImage = (string) $node->get('field_image_uri')->value !== '';
        if ($rank !== NULL && $hasImage && ($groups[$key]['cheapestPrice'] === NULL || $rank < $groups[$key]['cheapestPrice'])) {
          $groups[$key]['cheapest'] = $node;
          $groups[$key]['cheapestPrice'] = $rank;
        }
      }
      $storage->resetCache($chunk);
    }
  }

  /**
   * Regular price of a printing, or its foil price when there is none.
   */
  private static function price(NodeInterface $node, string $field, string $foilField): ?float {
    foreach ([$field, $foilField] as $name) {
      if ($node->hasField($name)) {
        $value = (float) ($node->get($name)->value ?? 0);
        if ($value > 0) {
          return $value;
        }
      }
    }
    return NULL;
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
