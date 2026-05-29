<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

use Drupal\Core\Entity\FieldableEntityInterface;
use Drupal\Core\Entity\Query\QueryInterface;
use Drupal\Core\Field\Plugin\Field\FieldType\EntityReferenceItem;
use Drupal\graphql\GraphQL\ResolverBuilder;
use Drupal\graphql\GraphQL\ResolverRegistryInterface;
use Drupal\node\NodeInterface;

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
        $slug  = $args['slug'];
        $parts = explode('-', $slug);
        $first = $parts[0] ?? $slug;

        $prefix = (substr($first, -1) === 's' && strlen($first) > 2)
          ? substr($first, 0, -1)
          : $first;
        $search = ucfirst($prefix);

        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->condition('title', $search . '%', 'LIKE')
          ->accessCheck(FALSE)
          ->range(0, 50)
          ->execute();

        foreach ($storage->loadMultiple($ids) as $node) {
          if (self::slugify($node->getTitle()) === $slug) {
            return $node;
          }
        }
        return NULL;
      })
    );

    $registry->addFieldResolver('Query', 'cardsByName',
      $builder->callback(function ($value, array $args): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->condition('title', $args['name'])
          ->accessCheck(FALSE)
          ->execute();
        return array_values($storage->loadMultiple($ids));
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
      $builder->callback(function (): float {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'collection_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->execute();

        $total = 0.0;
        foreach ($storage->loadMultiple($ids) as $cc) {
          $qty = (int) ($cc->get('field_quantity_owned')->value ?? 0);
          if ($qty === 0) {
            continue;
          }
          $ref = $cc->get('field_card')->first();
          if (!$ref instanceof EntityReferenceItem || !$ref->entity) {
            continue;
          }
          $card = $ref->entity;
          if (!$card instanceof FieldableEntityInterface) {
            continue;
          }
          $price  = (float) ($card->get('field_price_usd')->value ?? 0);
          $total += $price * $qty;
        }
        return round($total, 2);
      })
    );
  }

  /**
   * Registers all GraphQL mutation field resolvers.
   */
  public static function addMutationResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {

    $registry->addFieldResolver('Mutation', 'createDeck',
      $builder->callback(function ($value, array $args): NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $formatTerm = \Drupal::entityTypeManager()
          ->getStorage('taxonomy_term')
          ->loadByProperties(['vid' => 'mtg_format', 'name' => $args['format']]);
        $node = $storage->create([
          'type'              => 'deck',
          'title'             => $args['title'],
          'field_format_term' => ['target_id' => (int) reset($formatTerm)->id()],
          'field_notes'       => $args['notes'] ?? NULL,
          'status'            => 1,
        ]);
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
          $formatTerm = \Drupal::entityTypeManager()
            ->getStorage('taxonomy_term')
            ->loadByProperties(['vid' => 'mtg_format', 'name' => $args['format']]);
          $node->set('field_format_term', ['target_id' => (int) reset($formatTerm)->id()]);
        }
        if (array_key_exists('notes', $args)) {
          $node->set('field_notes', $args['notes']);
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
            $node->save();
            return $node;
          }
        }

        $cardNodes = $storage->loadByProperties(['type' => 'mtg_card', 'uuid' => $args['cardId']]);
        $cardNode  = reset($cardNodes);

        $node = $storage->create([
          'type'                 => 'collection_card',
          'title'                => $args['cardName'],
          'field_quantity_owned' => $args['quantityOwned'],
          'field_quantity_foil'  => $args['quantityFoil'] ?? 0,
          'field_card'           => ['target_id' => $cardNode->id()],
          'status'               => 1,
        ]);
        $node->save();
        return $node;
      })
    );

    $mutator = \Drupal::service('mtg_graphql.deck_card_mutator');

    $registry->addFieldResolver('Mutation', 'deckCardAdd',
      $builder->callback(function ($value, array $args) use ($mutator): array {
        return $mutator->add(
          (string) $args['deckId'],
          (string) $args['cardId'],
          (int) $args['quantity'],
          (bool) $args['isSideboard'],
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
      'imageUri'       => fn($n) => $n->get('field_image_uri')->value,
      'isManaProducer' => fn($n) => (bool) ($n->get('field_is_mana_producer')->value ?? FALSE),
      'priceUsd'       => fn($n) => $n->get('field_price_usd')->value,
      'priceUsdFoil'   => fn($n) => $n->get('field_price_usd_foil')->value,
      'setCode'        => fn($n) => $n->get('field_set_code')->value,
      'setName'        => fn($n) => $n->get('field_set_name')->value,
      'rarity'         => fn($n) => $n->get('field_rarity')->value,
      'collectorNumber' => fn($n) => $n->get('field_collector_number')->value,
      'power'          => fn($n) => $n->get('field_power')->value,
      'toughness'      => fn($n) => $n->get('field_toughness')->value,
      'loyalty'        => fn($n) => $n->get('field_loyalty')->value,
    ];

    foreach ($scalar as $field => $fn) {
      $registry->addFieldResolver('MtgCard', $field, $builder->callback($fn));
    }

    $multiValueFields = [
      'colors'        => 'field_colors',
      'colorIdentity' => 'field_color_identity',
      'producedMana'  => 'field_produced_mana',
      'legalFormats'  => 'field_legal_formats',
    ];
    foreach ($multiValueFields as $gql => $drupal) {
      $registry->addFieldResolver('MtgCard', $gql,
        $builder->callback(function ($node) use ($drupal): array {
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
    $registry->addFieldResolver('Deck', 'format', $builder->callback(function ($n): string {
      $ref = $n->get('field_format_term')->first();
      return $ref && $ref->entity ? $ref->entity->getName() : '';
    }));
    $registry->addFieldResolver('Deck', 'notes', $builder->callback(fn($n) => $n->get('field_notes')->value));
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
  }

  /**
   * Registers field resolvers for the SimulationResult type and query.
   */
  public static function addSimulationResultResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'simulationHistory',
      $builder->callback(function ($value, array $args): array {
        $deckNid = (int) $args['deckNid'];
        $limit   = (int) ($args['limit'] ?? 20);
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

    $registry->addFieldResolver('CardSearchResult', 'cards',
      $builder->callback(fn(array $page) => $page['cards'])
    );
    $registry->addFieldResolver('CardSearchResult', 'count',
      $builder->callback(fn(array $page) => $page['count'])
    );
    $registry->addFieldResolver('CardSearchResult', 'pages',
      $builder->callback(fn(array $page) => $page['pages'])
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
   * Mirrors the JS slugify() in mtg-app/src/utils/slugify.ts.
   */
  public static function slugify(string $title): string {
    $lower    = mb_strtolower($title, 'UTF-8');
    $stripped = preg_replace("/['\x{2019}\x{2018}`]/u", '', $lower);
    $dashed   = preg_replace('/[^a-z0-9]+/', '-', $stripped ?? '');
    return trim($dashed ?? '', '-');
  }

}
