<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

use Drupal\Core\Entity\FieldableEntityInterface;
use Drupal\Core\Entity\Query\QueryInterface;
use Drupal\Core\Field\Plugin\Field\FieldType\EntityReferenceItem;
use Drupal\graphql\GraphQL\Execution\FieldContext;
use Drupal\graphql\GraphQL\Execution\ResolveContext;
use Drupal\graphql\GraphQL\ResolverBuilder;
use Drupal\graphql\GraphQL\ResolverRegistryInterface;
use GraphQL\Type\Definition\ResolveInfo;
use Drupal\mtg_graphql\Service\CollectionEnsurer;
use Drupal\mtg_graphql\Service\DeckCardMutator;
use Drupal\mtg_graphql\Service\WishlistService;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;
use GraphQL\Error\UserError;

/**
 * Registers MTG custom GraphQL field resolvers.
 */
final class MtgGraphqlResolverRegistration {

  /**
   * Registers all MTG query, mutation, and type resolvers.
   */
  public static function register(ResolverRegistryInterface $registry): void {
    $builder = new ResolverBuilder();

    self::addQueryResolvers($registry, $builder);
    self::addMutationResolvers($registry, $builder);
    self::addCardPageResolvers($registry, $builder);
    self::addMtgCardResolvers($registry, $builder);
    self::addDeckResolvers($registry, $builder);
    self::addDeckCardResolvers($registry, $builder);
    self::addCollectionCardResolvers($registry, $builder);
    self::addPageResolvers($registry, $builder);
    self::addMetaDeckResolvers($registry, $builder);
    self::addSimulationResultResolvers($registry, $builder);
    self::addCardSearchResolvers($registry, $builder);
    self::addDeckCardSlotResolvers($registry, $builder);
    self::addFormatResolvers($registry, $builder);
    self::addScrapeMetaDecksResolver($registry, $builder);
    self::addWishlistResolvers($registry, $builder);
    self::addCollectionImportResolvers($registry, $builder);
    self::addDeckBuildPoolResolvers($registry, $builder);
    self::addPriceMoverResolvers($registry, $builder);
  }

  /**
   * Registers wishlist queries, mutations and type resolvers.
   */
  public static function addWishlistResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $wishlist = static fn(): WishlistService => \Drupal::service('mtg_graphql.wishlist');

    $registry->addFieldResolver('Query', 'wishlist',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext) use ($wishlist): array {
        $fieldContext->addCacheTags(['node_list:wishlist_item', 'node_list:collection_card']);
        return $wishlist()->items(
          isset($args['deckId']) ? (string) $args['deckId'] : NULL,
          isset($args['intentId']) ? (string) $args['intentId'] : NULL,
          !empty($args['includeDone']),
        );
      })
    );
    $registry->addFieldResolver('Query', 'wishlistForCard',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext) use ($wishlist): array {
        $fieldContext->addCacheTags(['node_list:wishlist_item', 'node_list:collection_card']);
        $card = \Drupal::service('entity.repository')->loadEntityByUuid('node', (string) $args['cardId']);
        return $card instanceof NodeInterface ? $wishlist()->itemsForCard($card) : [];
      })
    );
    $registry->addFieldResolver('Query', 'wishIntents',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext) use ($wishlist): array {
        $fieldContext->addCacheTags(['taxonomy_term_list:wish_intent']);
        return $wishlist()->intents();
      })
    );
    $registry->addFieldResolver('Mutation', 'saveWishlistItem',
      $builder->callback(fn($value, array $args) => $wishlist()->save($args))
    );
    $registry->addFieldResolver('Mutation', 'deleteWishlistItem',
      $builder->callback(fn($value, array $args) => $wishlist()->delete((string) $args['id']))
    );

    $registry->addFieldResolver('WishIntent', 'id', $builder->callback(fn($t) => (string) $t->id()));
    $registry->addFieldResolver('WishIntent', 'name', $builder->callback(fn($t) => $t->getName()));

    $registry->addFieldResolver('WishlistItem', 'id', $builder->callback(fn($n) => $n->uuid()));
    $registry->addFieldResolver('WishlistItem', 'quantity',
      $builder->callback(fn($n) => max(1, (int) ($n->get('field_wish_quantity')->value ?? 1)))
    );
    $registry->addFieldResolver('WishlistItem', 'anyPrinting',
      $builder->callback(fn($n) => $wishlist()->anyPrinting($n))
    );
    $registry->addFieldResolver('WishlistItem', 'foil',
      $builder->callback(fn($n) => DeckCardMutator::fieldIsOn($n, 'field_is_foil'))
    );
    $registry->addFieldResolver('WishlistItem', 'minCondition',
      $builder->callback(fn($n) => $n->get('field_min_condition')->value)
    );
    $registry->addFieldResolver('WishlistItem', 'notes',
      $builder->callback(fn($n) => $n->get('field_notes')->value)
    );
    $registry->addFieldResolver('WishlistItem', 'card',
      $builder->callback(fn($n) => $n->get('field_card')->entity)
    );
    $registry->addFieldResolver('WishlistItem', 'deck',
      $builder->callback(fn($n) => $n->get('field_wish_deck')->entity)
    );
    $registry->addFieldResolver('WishlistItem', 'intent',
      $builder->callback(fn($n) => $n->get('field_wish_intent')->entity)
    );
    $registry->addFieldResolver('WishlistItem', 'owned',
      $builder->callback(fn($n) => $wishlist()->owned($n))
    );
    $registry->addFieldResolver('WishlistItem', 'done',
      $builder->callback(fn($n) => $wishlist()->isDone($n))
    );
    $registry->addFieldResolver('WishlistItem', 'priceEur',
      $builder->callback(fn($n) => $wishlist()->price($n, 'eur'))
    );
    $registry->addFieldResolver('WishlistItem', 'priceUsd',
      $builder->callback(fn($n) => $wishlist()->price($n, 'usd'))
    );
  }

  /**
   * Registers the collection import mutation and result type.
   */
  public static function addCollectionImportResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Mutation', 'importCollection',
      $builder->callback(function ($value, array $args): array {
        /** @var \Drupal\mtg_graphql\Service\CollectionImporter $importer */
        $importer = \Drupal::service('mtg_graphql.collection_importer');
        return $importer->import($args['rows'] ?? [], (bool) $args['apply']);
      })
    );
    $registry->addFieldResolver('CollectionImportResult', 'row',
      $builder->callback(fn(array $r) => $r['row'])
    );
    $registry->addFieldResolver('CollectionImportResult', 'status',
      $builder->callback(fn(array $r) => $r['status'])
    );
    $registry->addFieldResolver('CollectionImportResult', 'matchedBy',
      $builder->callback(fn(array $r) => $r['matchedBy'])
    );
    $registry->addFieldResolver('CollectionImportResult', 'card',
      $builder->callback(fn(array $r) => $r['card'])
    );
  }

  /**
   * Registers the deck build pool query and its types.
   */
  public static function addDeckBuildPoolResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'deckBuildPool',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags([
          'node_list:collection_card',
          'node_list:deck',
          'node_list:mtg_card',
          'paragraph_list',
        ]);
        /** @var \Drupal\mtg_graphql\Service\DeckBuildPool $pool */
        $pool = \Drupal::service('mtg_graphql.deck_build_pool');
        return $pool->pool($args);
      })
    );
    foreach (['card', 'owned', 'trade', 'usedIn'] as $field) {
      $registry->addFieldResolver('PoolCard', $field,
        $builder->callback(fn(array $p) => $p[$field])
      );
    }
    foreach (['deckId', 'deckTitle', 'quantity'] as $field) {
      $registry->addFieldResolver('CardUse', $field,
        $builder->callback(fn(array $u) => $u[$field])
      );
    }

    $registry->addFieldResolver('Query', 'cardDeckUsage',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags([
          'node_list:collection_card',
          'node_list:deck',
          'paragraph_list',
        ]);
        /** @var \Drupal\mtg_graphql\Service\DeckBuildPool $pool */
        $pool = \Drupal::service('mtg_graphql.deck_build_pool');
        return $pool->usageForCard((string) $args['name']);
      })
    );
    foreach (['owned', 'inDecks', 'decks'] as $field) {
      $registry->addFieldResolver('CardDeckUsage', $field,
        $builder->callback(fn(array $u) => $u[$field])
      );
    }
    foreach (['deckId', 'deckTitle', 'board', 'quantity', 'setCode', 'foil'] as $field) {
      $registry->addFieldResolver('CardDeckUse', $field,
        $builder->callback(fn(array $u) => $u[$field])
      );
    }

    $registry->addFieldResolver('Query', 'deckTokens',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags([
          'node_list:collection_card',
          'node_list:deck',
          'node_list:mtg_card',
          'paragraph_list',
        ]);
        /** @var \Drupal\mtg_graphql\Service\DeckTokens $tokens */
        $tokens = \Drupal::service('mtg_graphql.deck_tokens');
        return $tokens->forDeck((string) $args['deckId']);
      })
    );
    foreach (['card', 'name', 'typeLine', 'power', 'toughness', 'oracleText', 'kind', 'madeBy', 'owned'] as $field) {
      $registry->addFieldResolver('DeckToken', $field,
        $builder->callback(fn(array $t) => $t[$field])
      );
    }

    $registry->addFieldResolver('Query', 'deckShortfalls',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags([
          'node_list:collection_card',
          'node_list:deck',
          'node_list:wishlist_item',
          'paragraph_list',
        ]);
        /** @var \Drupal\mtg_graphql\Service\DeckBuildPool $pool */
        $pool = \Drupal::service('mtg_graphql.deck_build_pool');
        return $pool->shortfalls();
      })
    );
    foreach (['deckId', 'deckTitle', 'format', 'cards'] as $field) {
      $registry->addFieldResolver('DeckShortfall', $field,
        $builder->callback(fn(array $d) => $d[$field])
      );
    }
    foreach (['card', 'needed', 'owned', 'wished', 'priceEur', 'priceUsd'] as $field) {
      $registry->addFieldResolver('MissingDeckCard', $field,
        $builder->callback(fn(array $c) => $c[$field])
      );
    }
  }

  /**
   * Registers the price movers query and its types.
   */
  public static function addPriceMoverResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'priceMovers',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags(['node_list:mtg_card']);
        /** @var \Drupal\mtg_scryfall_sync\Service\PriceHistory $history */
        $history = \Drupal::service('mtg_scryfall_sync.price_history');
        $limit = min(50, max(1, (int) ($args['limit'] ?? 10)));
        $movers = $history->movers(
          (string) ($args['currency'] ?? 'EUR'),
          $limit,
          max(0.0, (float) ($args['minPrice'] ?? 1.0)),
        );
        $cards = \Drupal::entityTypeManager()->getStorage('node')->loadMultiple(array_column($movers, 'nid'));
        $rows = [];
        foreach ($movers as $mover) {
          if (isset($cards[$mover['nid']])) {
            $rows[] = ['card' => $cards[$mover['nid']]] + $mover;
          }
        }
        return ['since' => $history->snapshotTime(), 'movers' => $rows];
      })
    );
    $registry->addFieldResolver('PriceMovers', 'since', $builder->callback(fn(array $r) => $r['since']));
    $registry->addFieldResolver('PriceMovers', 'movers', $builder->callback(fn(array $r) => $r['movers']));
    foreach (['card', 'previous', 'current', 'changePct'] as $field) {
      $registry->addFieldResolver('PriceMover', $field,
        $builder->callback(fn(array $m) => $m[$field])
      );
    }
  }

  /**
   * Applies optional trade arguments to a collection row before saving.
   *
   * @param \Drupal\node\NodeInterface $node
   *   The collection_card node.
   * @param array<string, mixed> $args
   *   Mutation arguments (quantityTrade, binderLocation).
   */
  private static function applyTradeArgs(NodeInterface $node, array $args): void {
    if (array_key_exists('quantityTrade', $args) && $args['quantityTrade'] !== NULL && $node->hasField('field_quantity_trade')) {
      $node->set('field_quantity_trade', max(0, (int) $args['quantityTrade']));
    }
    if (array_key_exists('binderLocation', $args) && $args['binderLocation'] !== NULL && $node->hasField('field_binder_location')) {
      $location = trim((string) $args['binderLocation']);
      $node->set('field_binder_location', $location === '' ? NULL : $location);
    }
    CollectionEnsurer::clampTrade($node);
  }

  /**
   * Registers all GraphQL query field resolvers.
   */
  public static function addQueryResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {

    $registry->addFieldResolver('Query', 'cards',
      $builder->callback(function ($value, array $args): array {
        $page = (int) ($args['page'] ?? 0);
        $limit = (int) ($args['limit'] ?? 50);
        $storage = \Drupal::entityTypeManager()->getStorage('node');

        $query = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->range($page * $limit, $limit)
          ->sort('title', 'ASC');

        self::applyCardFilters($query, $args);

        $ids   = $query->execute();
        $nodes = $storage->loadMultiple($ids);

        $countQuery = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->count();

        self::applyCardFilters($countQuery, $args);
        $total   = (int) $countQuery->execute();
        $hasNext = ($page + 1) * $limit < $total;

        return [
          'nodes'      => array_values($nodes),
          'nextCursor' => $hasNext ? (string) ($page + 1) : NULL,
          'total'      => $total,
        ];
      })
    );

    $registry->addFieldResolver('Query', 'card',
      $builder->callback(function ($value, array $args): ?NodeInterface {
        $slug = (string) $args['slug'];
        $storage = \Drupal::entityTypeManager()->getStorage('node');

        // Allow lookup by printing UUID (used when slug resolution fails).
        if (preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i', $slug) === 1) {
          $nodes = $storage->loadByProperties([
            'type' => 'mtg_card',
            'uuid' => $slug,
            'status' => 1,
          ]);
          $node = reset($nodes);
          return $node instanceof NodeInterface ? $node : NULL;
        }

        $parts = array_values(array_filter(explode('-', $slug), static fn(string $p): bool => $p !== ''));
        if ($parts === []) {
          return NULL;
        }

        // Try tight LIKE first, then first+last (diacritics / split segments),
        // then first-segment only with a wider window.
        $patterns = [self::slugLikePattern($parts)];
        if (count($parts) >= 3) {
          $patterns[] = self::slugLikePattern([
            $parts[0],
            $parts[count($parts) - 1],
          ]);
        }
        $patterns[] = ucfirst($parts[0]);

        foreach ($patterns as $index => $search) {
          $limit = $index === array_key_last($patterns) ? 200 : 50;
          $ids = \Drupal::entityQuery('node')
            ->condition('type', 'mtg_card')
            ->condition('status', 1)
            ->condition('title', $search . '%', 'LIKE')
            ->accessCheck(FALSE)
            ->sort('nid', 'DESC')
            ->range(0, $limit)
            ->execute();

          foreach ($storage->loadMultiple($ids) as $node) {
            if (self::slugify($node->getTitle()) === $slug) {
              return $node;
            }
          }
        }
        return NULL;
      })
    );

    $registry->addFieldResolver('Query', 'cardsByName',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags(['node_list:mtg_card']);
        $contains = !empty($args['contains']);
        $name = (string) $args['name'];
        $set = trim((string) ($args['set'] ?? ''));
        $storage = \Drupal::entityTypeManager()->getStorage('node');

        $exact = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->condition('title', $name)
          ->accessCheck(FALSE)
          ->sort('field_set_name', 'ASC')
          ->sort('field_collector_number', 'ASC');
        self::applySetQuery($exact, $set);
        $ids = $exact->execute();

        if ($contains) {
          $fuzzy = \Drupal::entityQuery('node')
            ->condition('type', 'mtg_card')
            ->condition('status', 1)
            ->condition('title', $name, 'CONTAINS')
            ->accessCheck(FALSE)
            ->sort('field_set_name', 'ASC');
          self::applySetQuery($fuzzy, $set);
          $ids += $fuzzy->execute();
        }

        $nodes = array_values($storage->loadMultiple($ids));
        $needle = mb_strtolower($name);
        // Prefer printings with a market price when sorting within a set.
        usort($nodes, static function ($a, $b) use ($contains, $needle): int {
          if ($contains) {
            $ta = mb_strtolower((string) $a->getTitle());
            $tb = mb_strtolower((string) $b->getTitle());
            $ra = self::titleMatchRank($ta, $needle);
            $rb = self::titleMatchRank($tb, $needle);
            if ($ra !== $rb) {
              return $ra <=> $rb;
            }
            if ($ta !== $tb) {
              return $ta <=> $tb;
            }
          }
          $sa = (string) ($a->get('field_set_name')->value ?? '');
          $sb = (string) ($b->get('field_set_name')->value ?? '');
          if ($sa !== $sb) {
            return $sa <=> $sb;
          }
          $pa = (float) ($a->get('field_price_eur')->value ?? 0);
          $pb = (float) ($b->get('field_price_eur')->value ?? 0);
          return $pb <=> $pa;
        });
        return $nodes;
      })
    );

    $registry->addFieldResolver('Query', 'deckCards',
      $builder->callback(fn($value, array $args): array => self::loadDeckCards($args['deckId']))
    );

    $registry->addFieldResolver('Query', 'deckCardsByNid',
      $builder->callback(function ($value, array $args): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $deck = $storage->load((int) $args['nid']);
        if (!$deck instanceof NodeInterface || $deck->bundle() !== 'deck') {
          return [];
        }
        return self::loadDeckCards($deck->uuid());
      })
    );

    $registry->addFieldResolver('Query', 'collectionCardByCardId',
      $builder->callback(function ($value, array $args): ?NodeInterface {
        $cardStorage = \Drupal::entityTypeManager()->getStorage('node');
        $cardNodes   = $cardStorage->loadByProperties(['type' => 'mtg_card', 'uuid' => $args['cardId']]);
        $card        = $cardNodes ? reset($cardNodes) : NULL;
        if (!$card instanceof NodeInterface) {
          return NULL;
        }

        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'collection_card')
          ->condition('status', 1)
          ->condition('field_card', $card->id())
          ->accessCheck(FALSE)
          ->range(0, 1)
          ->execute();

        $nodes = $storage->loadMultiple($ids);
        return $nodes ? reset($nodes) : NULL;
      })
    );

    $registry->addFieldResolver('Query', 'collectionValue',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): float {
        // Drop the cached total when collection rows or card prices change.
        $fieldContext->addCacheTags([
          'node_list:collection_card',
          'node_list:mtg_card',
        ]);
        // Cards priced only in the other currency follow the exchange rate.
        $fieldContext->mergeCacheMaxAge(3600);
        $usdToEur = \Drupal::service('mtg_scryfall_sync.exchange_rate')->usdToEur();
        $currency = strtoupper((string) ($args['currency'] ?? 'EUR'));
        return \Drupal::service('mtg_graphql.collection_reader')->value($currency === 'EUR', $usdToEur);
      })
    );

    $registry->addFieldResolver('Query', 'collectionRows',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $fieldContext->addCacheTags(['node_list:collection_card', 'node_list:mtg_card']);
        return \Drupal::service('mtg_graphql.collection_reader')->rows();
      })
    );
    foreach (['id', 'cardId', 'title', 'quantityOwned', 'quantityFoil', 'quantityTrade', 'binderLocation', 'setCode',
      'setName', 'collectorNumber', 'typeLine', 'cmc', 'priceUsd', 'priceUsdFoil', 'priceEur', 'priceEurFoil',
      'imageUri', 'fullArt', 'borderColor',
    ] as $field) {
      $registry->addFieldResolver('CollectionRow', $field,
        $builder->callback(fn(array $row) => $row[$field] ?? NULL)
      );
    }

    $registry->addFieldResolver('Query', 'usdToEurRate',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): float {
        $fieldContext->mergeCacheMaxAge(3600);
        return \Drupal::service('mtg_scryfall_sync.exchange_rate')->usdToEur();
      })
    );
  }

  /**
   * Price of one copy with fallbacks, 0 when the card has no price at all.
   *
   * Order: the asked finish in the asked currency, the other finish in that
   * currency, then the same two in the other currency converted at the
   * USD to EUR rate. Foil-only and regular-only printings are valued instead
   * of counting as 0.
   *
   * @param \Drupal\Core\Entity\FieldableEntityInterface $card
   *   The mtg_card printing.
   * @param bool $eur
   *   TRUE for a EUR price, FALSE for USD.
   * @param bool $foil
   *   TRUE for the foil finish.
   * @param float $usdToEur
   *   Euros per US dollar.
   */
  public static function bestPrice(FieldableEntityInterface $card, bool $eur, bool $foil, float $usdToEur): float {
    $other = $eur ? $usdToEur : 1 / $usdToEur;
    foreach ([[$eur, 1.0], [!$eur, $other]] as [$inEur, $factor]) {
      $regular = $inEur ? 'field_price_eur' : 'field_price_usd';
      foreach ($foil ? ["{$regular}_foil", $regular] : [$regular, "{$regular}_foil"] as $field) {
        if (!$card->hasField($field)) {
          continue;
        }
        $value = (float) ($card->get($field)->value ?? 0);
        if ($value > 0) {
          return $value * $factor;
        }
      }
    }
    return 0.0;
  }

  /**
   * Registers all GraphQL mutation field resolvers.
   */
  public static function addMutationResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {

    $registry->addFieldResolver('Mutation', 'createDeck',
      $builder->callback(function ($value, array $args): NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $formatName = (string) $args['format'];
        $node = $storage->create([
          'type'              => 'deck',
          'title'             => $args['title'],
          'field_format'      => $formatName,
          'field_format_term' => ['target_id' => self::formatTermId($formatName)],
          'field_notes'       => $args['notes'] ?? NULL,
          'status'            => 1,
        ]);
        if (isset($args['commanderId'])) {
          self::setCommander($node, (string) $args['commanderId']);
        }
        $node->save();
        return $node;
      })
    );

    $registry->addFieldResolver('Mutation', 'updateDeck',
      $builder->callback(function ($value, array $args): NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $nodes   = $storage->loadByProperties(['uuid' => $args['id'], 'type' => 'deck']);
        $node    = reset($nodes);

        if (isset($args['title'])) {
          $node->setTitle($args['title']);
        }
        if (isset($args['format'])) {
          $formatName = (string) $args['format'];
          $node->set('field_format', $formatName);
          $node->set('field_format_term', ['target_id' => self::formatTermId($formatName)]);
          if (!MtgFormatCatalog::usesCommanderCard($formatName)) {
            self::setCommander($node, '');
          }
        }
        if (array_key_exists('notes', $args)) {
          $node->set('field_notes', $args['notes']);
        }
        if (isset($args['commanderId'])) {
          self::setCommander($node, (string) $args['commanderId']);
        }
        if (isset($args['commanderFoil']) && $node->hasField('field_commander_foil')) {
          $node->set('field_commander_foil', (bool) $args['commanderFoil']);
        }
        $node->save();
        return $node;
      })
    );

    $registry->addFieldResolver('Mutation', 'deleteDeck',
      $builder->callback(function ($value, array $args): bool {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $nodes   = $storage->loadByProperties(['uuid' => $args['id'], 'type' => 'deck']);
        $node    = reset($nodes);
        if ($node) {
          $node->delete();
          return TRUE;
        }
        return FALSE;
      })
    );

    $registry->addFieldResolver('Mutation', 'upsertCollectionCard',
      $builder->callback(function ($value, array $args): NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');

        if (!empty($args['existingId'])) {
          $nodes = $storage->loadByProperties(['uuid' => $args['existingId'], 'type' => 'collection_card']);
          $node  = reset($nodes);
          if ($node instanceof NodeInterface) {
            $node->set('field_quantity_owned', $args['quantityOwned']);
            $node->set('field_quantity_foil', $args['quantityFoil'] ?? 0);
            self::applyTradeArgs($node, $args);
            $node->save();
            return $node;
          }
        }

        $cardNodes = $storage->loadByProperties(['type' => 'mtg_card', 'uuid' => $args['cardId']]);
        $cardNode  = reset($cardNodes);
        if (!$cardNode instanceof NodeInterface) {
          throw new \InvalidArgumentException('Card not found: ' . $args['cardId']);
        }

        // Prefer updating an existing collection row for this card.
        $existingIds = $storage->getQuery()
          ->accessCheck(FALSE)
          ->condition('type', 'collection_card')
          ->condition('field_card', $cardNode->id())
          ->range(0, 1)
          ->execute();
        if ($existingIds !== []) {
          $node = $storage->load(reset($existingIds));
          if ($node instanceof NodeInterface) {
            $node->set('title', $args['cardName']);
            $node->set('field_quantity_owned', $args['quantityOwned']);
            $node->set('field_quantity_foil', $args['quantityFoil'] ?? 0);
            self::applyTradeArgs($node, $args);
            $node->save();
            return $node;
          }
        }

        $node = $storage->create([
          'type'                 => 'collection_card',
          'title'                => $args['cardName'],
          'field_quantity_owned' => $args['quantityOwned'],
          'field_quantity_foil'  => $args['quantityFoil'] ?? 0,
          'field_card'           => ['target_id' => $cardNode->id()],
          'status'               => 1,
        ]);
        self::applyTradeArgs($node, $args);
        $node->save();
        return $node;
      })
    );

    $mutator = \Drupal::service('mtg_graphql.deck_card_mutator');

    $registry->addFieldResolver('Mutation', 'deckCardAdd',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        $foil = array_key_exists('foil', $args) && $args['foil'] !== NULL
          ? (bool) $args['foil']
          : NULL;
        $board = isset($args['board']) && $args['board'] !== '' ? (string) $args['board'] : NULL;
        return $mutator->add(
          (string) $args['deckId'],
          (string) $args['cardId'],
          (int) $args['quantity'],
          (bool) $args['isSideboard'],
          $foil,
          $board,
        );
      })
    );

    $registry->addFieldResolver('Mutation', 'deckCardMove',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        return $mutator->move(
          (string) $args['deckId'],
          (string) $args['slotId'],
          (string) $args['board'],
        );
      })
    );

    $registry->addFieldResolver('Mutation', 'deckCardUpdate',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        return $mutator->update(
          (string) $args['deckId'],
          (string) $args['slotId'],
          (int) $args['quantity'],
        );
      })
    );

    $registry->addFieldResolver('Mutation', 'deckCardSetFoil',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        return $mutator->setFoil(
          (string) $args['deckId'],
          (string) $args['slotId'],
          (bool) $args['foil'],
        );
      })
    );

    $registry->addFieldResolver('Mutation', 'deckCardReplacePrinting',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        return $mutator->replacePrinting(
          (string) $args['deckId'],
          (string) $args['slotId'],
          (string) $args['cardId'],
          (string) $args['collectionMode'],
          (bool) ($args['foil'] ?? FALSE),
        );
      })
    );

    $registry->addFieldResolver('Mutation', 'deckCardRemove',
      $builder->callback(function ($value, array $args) use ($mutator): bool {
        return $mutator->remove((string) $args['deckId'], (string) $args['slotId']);
      })
    );
  }

  /**
   * Registers field resolvers for the CardPage type.
   */
  public static function addCardPageResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('CardPage', 'cards',
      $builder->callback(fn($p) => $p['nodes'])
    );
    $registry->addFieldResolver('CardPage', 'nextCursor',
      $builder->callback(fn($p) => $p['nextCursor'])
    );
    $registry->addFieldResolver('CardPage', 'total',
      $builder->callback(fn($p) => $p['total'])
    );
  }

  /**
   * Registers field resolvers for the MtgCard type.
   */
  public static function addMtgCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $scalar = [
      'id'             => fn($n) => $n->uuid(),
      'title'          => fn($n) => $n->getTitle(),
      'manaCost'       => fn($n) => $n->get('field_mana_cost')->value,
      'cmc'            => fn($n) => $n->get('field_cmc')->value !== NULL ? (float) $n->get('field_cmc')->value : NULL,
      'typeLine'       => fn($n) => $n->get('field_type_line')->value,
      'oracleText'     => fn($n) => $n->get('field_oracle_text')->value,
      'imageUri'       => function ($n) {
        // Prefer locally cached media once available; otherwise return Scryfall
        // CDN URI and lazily enqueue a download for the sim / offline path.
        if (\Drupal::hasService('mtg_card_images.fetcher')) {
          /** @var \Drupal\mtg_card_images\CardImageFetcher $fetcher */
          $fetcher = \Drupal::service('mtg_card_images.fetcher');
          $local = $fetcher->localUrl($n);
          if ($local !== NULL) {
            return $local;
          }
          $fetcher->enqueueNode($n);
        }
        return $n->get('field_image_uri')->value;
      },
      'imageLocalUri'  => function ($n) {
        if (!\Drupal::hasService('mtg_card_images.fetcher')) {
          return NULL;
        }
        /** @var \Drupal\mtg_card_images\CardImageFetcher $fetcher */
        $fetcher = \Drupal::service('mtg_card_images.fetcher');
        return $fetcher->localUrl($n);
      },
      'isManaProducer' => fn($n) => (bool) ($n->get('field_is_mana_producer')->value ?? FALSE),
      'priceUsd'       => fn($n) => $n->get('field_price_usd')->value,
      'priceUsdFoil'   => fn($n) => $n->get('field_price_usd_foil')->value,
      'priceEur'       => fn($n) => $n->get('field_price_eur')->value,
      'priceEurFoil'   => fn($n) => $n->hasField('field_price_eur_foil')
        ? $n->get('field_price_eur_foil')->value
        : NULL,
      'setCode'        => fn($n) => $n->get('field_set_code')->value,
      'setName'        => fn($n) => $n->get('field_set_name')->value,
      'rarity'         => fn($n) => $n->get('field_rarity')->value,
      'collectorNumber' => fn($n) => $n->get('field_collector_number')->value,
      'power'          => fn($n) => $n->get('field_power')->value,
      'toughness'      => fn($n) => $n->get('field_toughness')->value,
      'loyalty'        => fn($n) => $n->get('field_loyalty')->value,
      'fullArt'        => fn($n) => $n->hasField('field_full_art')
        ? (bool) $n->get('field_full_art')->value
        : FALSE,
      'borderColor'    => fn($n) => $n->hasField('field_border_color')
        ? $n->get('field_border_color')->value
        : NULL,
    ];

    foreach ($scalar as $field => $fn) {
      $registry->addFieldResolver('MtgCard', $field, $builder->callback($fn));
    }

    $multiValueFields = [
      'colors'        => 'field_colors',
      'colorIdentity' => 'field_color_identity',
      'producedMana'  => 'field_produced_mana',
      'legalFormats'  => 'field_legal_formats',
      'restrictedFormats' => 'field_restricted_formats',
    ];
    foreach ($multiValueFields as $gql => $drupal) {
      $registry->addFieldResolver('MtgCard', $gql,
        $builder->callback(function ($node) use ($drupal): array {
          if (!$node->hasField($drupal)) {
            return [];
          }
          $out = [];
          foreach ($node->get($drupal) as $item) {
            $out[] = $item->value;
          }
          return $out;
        })
      );
    }
  }

  /**
   * Registers field resolvers for the Deck type.
   */
  public static function addDeckResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Deck', 'id', $builder->callback(fn($n) => $n->uuid()));
    $registry->addFieldResolver('Deck', 'nid', $builder->callback(fn($n) => (int) $n->id()));
    $registry->addFieldResolver('Deck', 'title', $builder->callback(fn($n) => $n->getTitle()));
    $registry->addFieldResolver('Deck', 'format',
      $builder->callback(fn($n) => self::deckFormatName($n))
    );
    $registry->addFieldResolver('NodeDeck', 'format',
      $builder->callback(fn($n) => self::deckFormatName($n))
    );
    $registry->addFieldResolver('Deck', 'notes', $builder->callback(fn($n) => $n->get('field_notes')->value));
    $registry->addFieldResolver('Deck', 'commander',
      $builder->callback(fn($n) => self::commanderCard($n))
    );
    $registry->addFieldResolver('NodeDeck', 'commander',
      $builder->callback(fn($n) => self::commanderCard($n))
    );
    $registry->addFieldResolver('Deck', 'commanderIsFoil',
      $builder->callback(fn($n) => self::commanderIsFoil($n))
    );
    $registry->addFieldResolver('NodeDeck', 'commanderIsFoil',
      $builder->callback(fn($n) => self::commanderIsFoil($n))
    );
  }

  /**
   * Registers field resolvers for the DeckCard type.
   */
  public static function addDeckCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('DeckCard', 'id',
      $builder->callback(fn($p) => $p->uuid())
    );
    $registry->addFieldResolver('DeckCard', 'quantity',
      $builder->callback(fn($p) => (int) ($p->get('field_quantity')->value ?? 1))
    );
    $registry->addFieldResolver('DeckCard', 'isSideboard',
      $builder->callback(fn($p) => (bool) ($p->get('field_is_sideboard')->value ?? FALSE))
    );
    $registry->addFieldResolver('DeckCard', 'isFoil',
      $builder->callback(fn($p) => DeckCardMutator::fieldIsOn($p, 'field_is_foil'))
    );
    $registry->addFieldResolver('DeckCard', 'board',
      $builder->callback(fn($p) => DeckCardMutator::boardOf($p))
    );
    $registry->addFieldResolver('DeckCard', 'card',
      $builder->callback(function ($p): ?NodeInterface {
        $ref = $p->get('field_card')->first();
        return $ref ? $ref->entity : NULL;
      })
    );
  }

  /**
   * Registers field resolvers for the CollectionCard type.
   */
  public static function addCollectionCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('CollectionCard', 'id',
      $builder->callback(fn($n) => $n->uuid())
    );
    $registry->addFieldResolver('CollectionCard', 'quantityOwned',
      $builder->callback(fn($n) => (int) ($n->get('field_quantity_owned')->value ?? 0))
    );
    $registry->addFieldResolver('CollectionCard', 'quantityFoil',
      $builder->callback(fn($n) => (int) ($n->get('field_quantity_foil')->value ?? 0))
    );
    $registry->addFieldResolver('CollectionCard', 'quantityTrade',
      $builder->callback(fn($n) => $n->hasField('field_quantity_trade')
        ? (int) ($n->get('field_quantity_trade')->value ?? 0)
        : 0)
    );
    $registry->addFieldResolver('CollectionCard', 'binderLocation',
      $builder->callback(fn($n) => $n->hasField('field_binder_location')
        ? $n->get('field_binder_location')->value
        : NULL)
    );
    $registry->addFieldResolver('CollectionCard', 'card',
      $builder->callback(function ($n): ?NodeInterface {
        $ref = $n->get('field_card')->first();
        return $ref ? $ref->entity : NULL;
      })
    );
  }

  /**
   * Registers field resolvers for the Page type and query.
   */
  public static function addPageResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'pages',
      $builder->callback(function (): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'page')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->execute();
        return array_values($storage->loadMultiple($ids));
      })
    );

    $registry->addFieldResolver('Page', 'id',
      $builder->callback(fn($n) => $n->uuid())
    );
    $registry->addFieldResolver('Page', 'title',
      $builder->callback(fn($n) => $n->getTitle())
    );
    $registry->addFieldResolver('Page', 'body',
      $builder->callback(fn($n) => $n->get('body')->processed)
    );
    $registry->addFieldResolver('Page', 'pathAlias',
      $builder->callback(function ($n): ?string {
        $alias = \Drupal::service('path_alias.manager')
          ->getAliasByPath('/node/' . $n->id(), $n->language()->getId());
        return $alias !== '/node/' . $n->id() ? $alias : NULL;
      })
    );
  }

  /**
   * Registers field resolvers for the MetaDeck type and query.
   */
  public static function addMetaDeckResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'metaDecks',
      $builder->callback(function ($value, array $args): array {
        $format  = $args['format'];
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'meta_deck')
          ->condition('status', 1)
          ->condition('field_format_term.entity:taxonomy_term.name', $format)
          ->accessCheck(FALSE)
          ->sort('field_meta_share', 'DESC')
          ->execute();
        return array_values($storage->loadMultiple($ids));
      })
    );

    $registry->addFieldResolver('MetaDeck', 'id',
      $builder->callback(fn($n) => $n->uuid())
    );
    $registry->addFieldResolver('MetaDeck', 'title',
      $builder->callback(fn($n) => $n->getTitle())
    );
    $registry->addFieldResolver('MetaDeck', 'format',
      $builder->callback(function ($n): string {
        $ref = $n->get('field_format_term')->first();
        return $ref && $ref->entity ? $ref->entity->getName() : '';
      })
    );
    $registry->addFieldResolver('MetaDeck', 'metaShare',
      $builder->callback(function ($n): ?float {
        $val = $n->get('field_meta_share')->value;
        return $val !== NULL ? (float) $val : NULL;
      })
    );
    $registry->addFieldResolver('MetaDeck', 'archetypeTags',
      $builder->callback(function ($n): array {
        $out = [];
        foreach ($n->get('field_archetype_tags') as $item) {
          $out[] = $item->value;
        }
        return $out;
      })
    );
    $registry->addFieldResolver('MetaDeck', 'fetchedAt',
      $builder->callback(fn($n) => $n->get('field_fetched_at')->value)
    );
    $registry->addFieldResolver('MetaDeck', 'cardsJson',
      $builder->callback(function ($n): string {
        $raw = $n->get('field_cards_json')->value ?? '';
        return is_string($raw) ? $raw : '';
      })
    );
    $registry->addFieldResolver('MetaDeck', 'pilotPrompt',
      $builder->callback(function ($n): ?string {
        $raw = $n->get('field_pilot_prompt')->value ?? NULL;
        return is_string($raw) && $raw !== '' ? $raw : NULL;
      })
    );
  }

  /**
   * Registers field resolvers for the SimulationResult type and query.
   */
  public static function addSimulationResultResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'simulationHistory',
      $builder->callback(function ($value, array $args, ResolveContext $context, ResolveInfo $info, FieldContext $fieldContext): array {
        $deckNid = (int) $args['deckNid'];
        $limit   = (int) ($args['limit'] ?? 20);
        // Tag the response so it is automatically invalidated when any
        // simulation_result node is created, updated, or deleted.
        $fieldContext->addCacheTags(['node_list:simulation_result']);
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids     = \Drupal::entityQuery('node')
          ->condition('type', 'simulation_result')
          ->condition('status', 1)
          ->condition('field_sim_player_deck_nid', $deckNid)
          ->accessCheck(FALSE)
          ->sort('created', 'DESC')
          ->range(0, $limit)
          ->execute();
        return array_values($storage->loadMultiple($ids));
      })
    );

    $registry->addFieldResolver('SimulationResult', 'id',
      $builder->callback(fn($n) => $n->uuid())
    );
    $registry->addFieldResolver('SimulationResult', 'nid',
      $builder->callback(fn($n) => (int) $n->id())
    );
    $registry->addFieldResolver('SimulationResult', 'opponent',
      $builder->callback(fn($n) => (string) ($n->get('field_sim_opponent')->value ?? ''))
    );
    $registry->addFieldResolver('SimulationResult', 'format',
      $builder->callback(fn($n) => (string) ($n->get('field_sim_format')->value ?? ''))
    );
    $registry->addFieldResolver('SimulationResult', 'games',
      $builder->callback(fn($n) => (int) ($n->get('field_sim_games')->value ?? 0))
    );
    $registry->addFieldResolver('SimulationResult', 'wins',
      $builder->callback(fn($n) => (int) ($n->get('field_sim_wins')->value ?? 0))
    );
    $registry->addFieldResolver('SimulationResult', 'winRate',
      $builder->callback(fn($n) => (float) ($n->get('field_sim_win_rate')->value ?? 0.0))
    );
    $registry->addFieldResolver('SimulationResult', 'resultJson',
      $builder->callback(fn($n) => (string) ($n->get('field_sim_result_json')->value ?? '{}'))
    );
    $registry->addFieldResolver('SimulationResult', 'created',
      $builder->callback(fn($n) => date('c', (int) $n->getCreatedTime()))
    );
    $registry->addFieldResolver('SimulationResult', 'deckTitle',
      $builder->callback(function ($n): string {
        $deckNid = (int) ($n->get('field_sim_player_deck_nid')->value ?? 0);
        $revision = self::loadDeckRevisionAtTime($deckNid, (int) $n->getCreatedTime());
        return $revision instanceof NodeInterface ? $revision->getTitle() : '';
      })
    );
    $registry->addFieldResolver('SimulationResult', 'deckNotes',
      $builder->callback(function ($n): ?string {
        $deckNid = (int) ($n->get('field_sim_player_deck_nid')->value ?? 0);
        $revision = self::loadDeckRevisionAtTime($deckNid, (int) $n->getCreatedTime());
        return $revision instanceof NodeInterface ? ($revision->get('field_notes')->value ?? NULL) : NULL;
      })
    );
    $registry->addFieldResolver('SimulationResult', 'deckCards',
      $builder->callback(function ($n): array {
        $deckNid = (int) ($n->get('field_sim_player_deck_nid')->value ?? 0);
        $revision = self::loadDeckRevisionAtTime($deckNid, (int) $n->getCreatedTime());
        return self::loadDeckCardsFromRevision($revision);
      })
    );
  }

  /**
   * Finds and loads the deck node revision current at or before a timestamp.
   *
   * Uses a per-request static cache so repeated calls for the same deck within
   * a single GraphQL response do not repeat the database lookup.
   *
   * @param int $deckNid
   *   The node ID of the deck.
   * @param int $timestamp
   *   Unix timestamp; the most recent revision at or before this time is used.
   *
   * @return \Drupal\node\NodeInterface|null
   *   The revision entity, or NULL if none found.
   */
  private static function loadDeckRevisionAtTime(int $deckNid, int $timestamp): ?NodeInterface {
    static $cache = [];
    $key = $deckNid . ':' . $timestamp;
    if (array_key_exists($key, $cache)) {
      return $cache[$key];
    }
    $vid = \Drupal::database()
      ->select('node_revision', 'nr')
      ->fields('nr', ['vid'])
      ->condition('nid', $deckNid)
      ->condition('revision_timestamp', $timestamp, '<=')
      ->orderBy('revision_timestamp', 'DESC')
      ->range(0, 1)
      ->execute()
      ->fetchField();
    $revision = $vid ? \Drupal::entityTypeManager()->getStorage('node')->loadRevision($vid) : NULL;
    $cache[$key] = $revision instanceof NodeInterface ? $revision : NULL;
    return $cache[$key];
  }

  /**
   * Returns the deck card paragraph entities from a node revision.
   *
   * @param \Drupal\node\NodeInterface|null $revision
   *   A deck node revision, or NULL.
   *
   * @return \Drupal\Core\Entity\EntityInterface[]
   *   Paragraph entities for each card slot.
   */
  private static function loadDeckCardsFromRevision(?NodeInterface $revision): array {
    if (!$revision instanceof NodeInterface) {
      return [];
    }
    $result = [];
    foreach ($revision->get('field_deck_cards') as $item) {
      if ($item instanceof EntityReferenceItem && $item->entity) {
        $result[] = $item->entity;
      }
    }
    return $result;
  }

  /**
   * Loads all deck card paragraph entities for a deck UUID.
   *
   * @return \Drupal\Core\Entity\EntityInterface[]
   *   Array of paragraph entities representing deck card slots.
   */
  private static function loadDeckCards(string $deckUuid): array {
    $storage = \Drupal::entityTypeManager()->getStorage('node');
    $nodes = $storage->loadByProperties(['type' => 'deck', 'uuid' => $deckUuid]);
    $deck = $nodes ? reset($nodes) : NULL;
    if (!$deck instanceof NodeInterface) {
      return [];
    }

    $result = [];
    foreach ($deck->get('field_deck_cards') as $item) {
      if ($item instanceof EntityReferenceItem && $item->entity) {
        $result[] = $item->entity;
      }
    }
    return $result;
  }

  /**
   * Applies optional card filter arguments to an entity query.
   */
  private static function applyCardFilters(QueryInterface $query, array $args): void {
    if (!empty($args['name'])) {
      $query->condition('title', '%' . $args['name'] . '%', 'LIKE');
    }
    if (!empty($args['type'])) {
      $query->condition('field_type_line', '%' . $args['type'] . '%', 'LIKE');
    }
    if (isset($args['maxCmc'])) {
      $query->condition('field_cmc', (string) (float) $args['maxCmc'], '<=');
    }
    if (!empty($args['colors'])) {
      $query->condition('field_colors', $args['colors'], 'IN');
    }
    if (!empty($args['titlePrefix'])) {
      $query->condition('title', $args['titlePrefix'] . '%', 'LIKE');
    }
    // Tokens and emblems (type lines start with Token / Emblem) are hidden
    // unless asked for; tokens: true lists only them.
    if (($args['tokens'] ?? NULL) === TRUE) {
      $query->condition($query->orConditionGroup()
        ->condition('field_type_line', 'Token%', 'LIKE')
        ->condition('field_type_line', 'Emblem%', 'LIKE'));
    }
    else {
      $query->condition('field_type_line', 'Token%', 'NOT LIKE');
      $query->condition('field_type_line', 'Emblem%', 'NOT LIKE');
    }
  }

  /**
   * Registers the card search query and result type resolvers.
   */
  public static function addCardSearchResolvers(
    ResolverRegistryInterface $registry,
    ResolverBuilder $builder,
  ): void {
    $registry->addFieldResolver('Query', 'cardSearch',
      $builder->callback(function ($value, array $args): array {
        $search = \Drupal::service('mtg_card_search.search');
        $result = $search->search($args);
        return [
          'cards' => $result['cards'],
          'count' => $result['count'],
          'pages' => $result['pages'],
        ];
      })
    );

    $registry->addFieldResolver('Query', 'cardSets',
      $builder->callback(function ($value, array $args): array {
        $q = (string) ($args['q'] ?? '');
        $limit = min(2000, max(1, (int) ($args['limit'] ?? 1000)));
        /** @var \Drupal\mtg_scryfall_sync\Service\SetTaxonomy $sets */
        $sets = \Drupal::service('mtg_scryfall_sync.set_taxonomy');
        return $sets->search($q, $limit);
      })
    );

    $registry->addFieldResolver('CardSearchResult', 'cards',
      $builder->callback(fn(array $page) => $page['cards'])
    );
    $registry->addFieldResolver('CardSearchResult', 'count',
      $builder->callback(fn(array $page) => $page['count'])
    );
    $registry->addFieldResolver('CardSearchResult', 'pages',
      $builder->callback(fn(array $page) => $page['pages'])
    );

    $registry->addFieldResolver('CardSet', 'code',
      $builder->callback(fn(array $set) => $set['code'])
    );
    $registry->addFieldResolver('CardSet', 'name',
      $builder->callback(fn(array $set) => $set['name'])
    );
    $registry->addFieldResolver('CardSet', 'count',
      $builder->callback(fn(array $set) => $set['count'])
    );
  }

  /**
   * Registers field resolvers for the DeckCardSlot type.
   */
  public static function addDeckCardSlotResolvers(
    ResolverRegistryInterface $registry,
    ResolverBuilder $builder,
  ): void {
    $registry->addFieldResolver('DeckCardSlot', 'id',
      $builder->callback(fn(array $slot) => $slot['id'])
    );
    $registry->addFieldResolver('DeckCardSlot', 'quantity',
      $builder->callback(fn(array $slot) => $slot['quantity'])
    );
    $registry->addFieldResolver('DeckCardSlot', 'isSideboard',
      $builder->callback(fn(array $slot) => $slot['isSideboard'])
    );
    $registry->addFieldResolver('DeckCardSlot', 'isFoil',
      $builder->callback(fn(array $slot) => (bool) ($slot['isFoil'] ?? FALSE))
    );
    $registry->addFieldResolver('DeckCardSlot', 'board',
      $builder->callback(fn(array $slot) => (string) ($slot['board'] ?? 'main'))
    );
  }

  /**
   * Registers field resolvers for MtgFormat and the formats query.
   */
  public static function addFormatResolvers(
    ResolverRegistryInterface $registry,
    ResolverBuilder $builder,
  ): void {
    $registry->addFieldResolver('Query', 'formats',
      $builder->callback(function (): array {
        $terms = \Drupal::entityTypeManager()
          ->getStorage('taxonomy_term')
          ->loadByProperties(['vid' => 'mtg_format']);
        return array_values($terms);
      })
    );

    $registry->addFieldResolver('MtgFormat', 'name',
      $builder->callback(fn($term) => $term->getName())
    );
    $registry->addFieldResolver('MtgFormat', 'slug',
      $builder->callback(fn($term) => $term->get('field_goldfish_slug')->value ?? '')
    );
  }

  /**
   * Registers the scrapeMetaDecks mutation resolver.
   */
  public static function addScrapeMetaDecksResolver(
    ResolverRegistryInterface $registry,
    ResolverBuilder $builder,
  ): void {
    $registry->addFieldResolver('Mutation', 'scrapeMetaDecks',
      $builder->callback(function ($value, array $args): array {
        $scraper = \Drupal::service('mtg_graphql.meta_deck_scraper');
        return $scraper->scrape(
          (string) $args['format'],
          (int) ($args['limit'] ?? 20),
        );
      })
    );

    $registry->addFieldResolver('ScrapeMetaDecksResult', 'format',
      $builder->callback(fn(array $r) => $r['format'])
    );
    $registry->addFieldResolver('ScrapeMetaDecksResult', 'created',
      $builder->callback(fn(array $r) => $r['created'])
    );
    $registry->addFieldResolver('ScrapeMetaDecksResult', 'updated',
      $builder->callback(fn(array $r) => $r['updated'])
    );
    $registry->addFieldResolver('ScrapeMetaDecksResult', 'skipped',
      $builder->callback(fn(array $r) => $r['skipped'])
    );
  }

  /**
   * Format display name from the taxonomy term, with the string field fallback.
   */
  public static function deckFormatName(mixed $node): string {
    if (!$node instanceof NodeInterface) {
      return '';
    }
    if ($node->hasField('field_format_term') && !$node->get('field_format_term')->isEmpty()) {
      $item = $node->get('field_format_term')->first();
      if ($item instanceof EntityReferenceItem && $item->entity !== NULL) {
        return (string) $item->entity->label();
      }
    }
    if ($node->hasField('field_format') && !$node->get('field_format')->isEmpty()) {
      return (string) $node->get('field_format')->value;
    }
    return '';
  }

  /**
   * Sets or clears the deck commander from a card UUID.
   *
   * @throws \GraphQL\Error\UserError
   *   When the UUID does not match an mtg_card node.
   */
  private static function setCommander(NodeInterface $node, string $commanderId): void {
    if (!$node->hasField('field_commander')) {
      return;
    }
    if ($commanderId === '') {
      $node->set('field_commander', []);
      if ($node->hasField('field_commander_foil')) {
        $node->set('field_commander_foil', FALSE);
      }
      return;
    }
    $cards = \Drupal::entityTypeManager()
      ->getStorage('node')
      ->loadByProperties(['uuid' => $commanderId, 'type' => 'mtg_card']);
    $card = reset($cards);
    if (!$card instanceof NodeInterface) {
      throw new UserError('Commander card not found.');
    }
    $node->set('field_commander', ['target_id' => (int) $card->id()]);
  }

  /**
   * Referenced commander card, or NULL when unset.
   */
  private static function commanderCard(mixed $node): ?NodeInterface {
    if (!$node instanceof NodeInterface || !$node->hasField('field_commander')) {
      return NULL;
    }
    if ($node->get('field_commander')->isEmpty()) {
      return NULL;
    }
    $item = $node->get('field_commander')->first();
    if (!$item instanceof EntityReferenceItem) {
      return NULL;
    }
    $entity = $item->entity;
    return $entity instanceof NodeInterface ? $entity : NULL;
  }

  /**
   * Whether the deck commander is foil.
   */
  private static function commanderIsFoil(mixed $node): bool {
    if (!$node instanceof NodeInterface || !$node->hasField('field_commander_foil')) {
      return FALSE;
    }
    return (bool) $node->get('field_commander_foil')->value;
  }

  /**
   * Restricts a card query to set code, set name, or collector number.
   */
  private static function applySetQuery(QueryInterface $query, string $set): void {
    $set = trim($set);
    if ($set === '') {
      return;
    }
    if (str_starts_with($set, '#') || preg_match('/^\d+$/', $set)) {
      $bare = ltrim($set, '#');
      if ($bare !== '') {
        $query->condition('field_collector_number', $bare, 'STARTS_WITH');
      }
      return;
    }
    if (preg_match('/^(?=[a-z0-9]{2,5}$)(?=.*[a-z])[a-z0-9]+$/i', $set)) {
      $query->condition('field_set_code', $set, 'STARTS_WITH');
      return;
    }
    $group = $query->orConditionGroup()
      ->condition('field_set_code', $set, 'CONTAINS')
      ->condition('field_set_name', $set, 'CONTAINS')
      ->condition('field_collector_number', $set, 'CONTAINS');
    $query->condition($group);
  }

  /**
   * Ranks a card title against a search needle (lower is better).
   *
   * Exact match, then prefix, then contains.
   */
  private static function titleMatchRank(string $title, string $needle): int {
    if ($title === $needle) {
      return 0;
    }
    if ($needle !== '' && str_starts_with($title, $needle)) {
      return 1;
    }
    return 2;
  }

  /**
   * Returns the mtg_format term ID for a deck format name.
   *
   * Accepts common aliases (EDH, TLR). Throws a GraphQL user error when
   * the format is not in the taxonomy.
   *
   * @throws \GraphQL\Error\UserError
   *   When no matching format term exists.
   */
  private static function formatTermId(string $formatName): int {
    $aliases = [
      'EDH' => 'Commander',
      'TLR' => 'Tiny Leaders',
    ];
    $name = $aliases[$formatName] ?? $formatName;
    $terms = \Drupal::entityTypeManager()
      ->getStorage('taxonomy_term')
      ->loadByProperties(['vid' => 'mtg_format', 'name' => $name]);
    $term = reset($terms);
    if (!$term instanceof TermInterface) {
      throw new UserError(sprintf(
        'Unknown format "%s". Add it to the mtg_format taxonomy or choose an existing format.',
        $formatName,
      ));
    }
    return (int) $term->id();
  }

  /**
   * Builds a LIKE prefix from URL slug segments.
   *
   * A trailing "s" is dropped on every segment so possessives in any
   * word still match the stored title ("white-suns-zenith" ->
   * "White%Sun%Zenith", matching "White Sun's Zenith").
   *
   * @param list<string> $parts
   *   Non-empty slug segments.
   *
   * @return string
   *   LIKE prefix without the trailing wildcard.
   */
  public static function slugLikePattern(array $parts): string {
    $like_parts = [];
    foreach ($parts as $part) {
      if (str_ends_with($part, 's') && strlen($part) > 2) {
        $like_parts[] = ucfirst(substr($part, 0, -1));
      }
      else {
        $like_parts[] = ucfirst($part);
      }
    }
    return implode('%', $like_parts);
  }

  /**
   * Mirrors the JS slugify() in mtg-app/src/utils/slugify.ts.
   */
  public static function slugify(string $title): string {
    $lower = mb_strtolower($title, 'UTF-8');
    if (class_exists(\Normalizer::class)) {
      $normalized = \Normalizer::normalize($lower, \Normalizer::FORM_D);
      if (is_string($normalized)) {
        $folded = preg_replace('/\p{Mn}/u', '', $normalized);
        if (is_string($folded)) {
          $lower = $folded;
        }
      }
    }
    $stripped = preg_replace("/['\x{2019}\x{2018}`]/u", '', $lower);
    $dashed = preg_replace('/[^a-z0-9]+/', '-', $stripped ?? '');
    return trim($dashed ?? '', '-');
  }

}
