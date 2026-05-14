<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Plugin\GraphQL\Schema;

use Drupal\graphql\Annotation\Schema;
use Drupal\graphql\GraphQL\ResolverBuilder;
use Drupal\graphql\GraphQL\ResolverRegistryInterface;
use Drupal\graphql\Plugin\GraphQL\Schema\SdlSchemaPluginBase;
use Drupal\node\NodeInterface;

/**
 * @Schema(
 *   id = "mtg_schema",
 *   name = "MTG Deck Manager API"
 * )
 */
class MtgSchema extends SdlSchemaPluginBase {

  /**
   * {@inheritdoc}
   */
  protected function registerResolvers(ResolverRegistryInterface $registry): void {
    $builder = new ResolverBuilder();

    $this->addQueryResolvers($registry, $builder);
    $this->addMutationResolvers($registry, $builder);
    $this->addCardPageResolvers($registry, $builder);
    $this->addMtgCardResolvers($registry, $builder);
    $this->addDeckResolvers($registry, $builder);
    $this->addDeckCardResolvers($registry, $builder);
    $this->addCollectionCardResolvers($registry, $builder);
    $this->addPageResolvers($registry, $builder);
    $this->addMetaDeckResolvers($registry, $builder);
  }

  // ---------------------------------------------------------------------------
  // Query resolvers
  // ---------------------------------------------------------------------------

  private function addQueryResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {

    $registry->addFieldResolver('Query', 'cards',
      $builder->callback(function ($value, array $args): array {
        $page  = (int) ($args['page']  ?? 0);
        $limit = (int) ($args['limit'] ?? 50);
        $storage = \Drupal::entityTypeManager()->getStorage('node');

        $query = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->range($page * $limit, $limit)
          ->sort('title', 'ASC');

        $this->applyCardFilters($query, $args);

        $ids    = $query->execute();
        $nodes  = $storage->loadMultiple($ids);

        $countQuery = \Drupal::entityQuery('node')
          ->condition('type', 'mtg_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->count();

        $this->applyCardFilters($countQuery, $args);
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

    $registry->addFieldResolver('Query', 'decks',
      $builder->callback(function (): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'deck')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->sort('title', 'ASC')
          ->execute();
        return array_values($storage->loadMultiple($ids));
      })
    );

    $registry->addFieldResolver('Query', 'deck',
      $builder->callback(function ($value, array $args): ?NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $nodes = $storage->loadByProperties(['type' => 'deck', 'uuid' => $args['id']]);
        return $nodes ? reset($nodes) : NULL;
      })
    );

    $registry->addFieldResolver('Query', 'deckCards',
      $builder->callback(function ($value, array $args): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $nodes = $storage->loadByProperties(['type' => 'deck', 'uuid' => $args['deckId']]);
        $deck  = $nodes ? reset($nodes) : NULL;
        if (!$deck instanceof NodeInterface) {
          return [];
        }

        $result = [];
        foreach ($deck->get('field_deck_cards') as $item) {
          if ($item->entity) {
            $result[] = $item->entity;
          }
        }
        return $result;
      })
    );

    $registry->addFieldResolver('Query', 'collectionCards',
      $builder->callback(function (): array {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'collection_card')
          ->condition('status', 1)
          ->accessCheck(FALSE)
          ->execute();
        return array_values($storage->loadMultiple($ids));
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
          if (!$ref || !$ref->entity) {
            continue;
          }
          $price  = (float) ($ref->entity->get('field_price_usd')->value ?? 0);
          $total += $price * $qty;
        }
        return round($total, 2);
      })
    );
  }

  // ---------------------------------------------------------------------------
  // Mutation resolvers
  // ---------------------------------------------------------------------------

  private function addMutationResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {

    $registry->addFieldResolver('Mutation', 'createDeck',
      $builder->callback(function ($value, array $args): NodeInterface {
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $node = $storage->create([
          'type'         => 'deck',
          'title'        => $args['title'],
          'field_format' => $args['format'],
          'field_notes'  => $args['notes'] ?? NULL,
          'status'       => 1,
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
          $node->set('field_format', $args['format']);
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
  }

  // ---------------------------------------------------------------------------
  // Type field resolvers
  // ---------------------------------------------------------------------------

  private function addCardPageResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
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

  private function addMtgCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
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
      'collectorNumber'=> fn($n) => $n->get('field_collector_number')->value,
      'power'          => fn($n) => $n->get('field_power')->value,
      'toughness'      => fn($n) => $n->get('field_toughness')->value,
      'loyalty'        => fn($n) => $n->get('field_loyalty')->value,
    ];

    foreach ($scalar as $field => $fn) {
      $registry->addFieldResolver('MtgCard', $field, $builder->callback($fn));
    }

    foreach (['colors' => 'field_colors', 'colorIdentity' => 'field_color_identity', 'producedMana' => 'field_produced_mana', 'legalFormats' => 'field_legal_formats'] as $gql => $drupal) {
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

  private function addDeckResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Deck', 'id',     $builder->callback(fn($n) => $n->uuid()));
    $registry->addFieldResolver('Deck', 'nid',    $builder->callback(fn($n) => (int) $n->id()));
    $registry->addFieldResolver('Deck', 'title',  $builder->callback(fn($n) => $n->getTitle()));
    $registry->addFieldResolver('Deck', 'format', $builder->callback(fn($n) => $n->get('field_format')->value ?? ''));
    $registry->addFieldResolver('Deck', 'notes',  $builder->callback(fn($n) => $n->get('field_notes')->value));
  }

  private function addDeckCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
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

  private function addCollectionCardResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
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

  private function addPageResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
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

  // ---------------------------------------------------------------------------
  // Meta deck resolvers
  // ---------------------------------------------------------------------------

  private function addMetaDeckResolvers(ResolverRegistryInterface $registry, ResolverBuilder $builder): void {
    $registry->addFieldResolver('Query', 'metaDecks',
      $builder->callback(function ($value, array $args): array {
        $format  = $args['format'];
        $storage = \Drupal::entityTypeManager()->getStorage('node');
        $ids = \Drupal::entityQuery('node')
          ->condition('type', 'meta_deck')
          ->condition('status', 1)
          ->condition('field_format', $format)
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
      $builder->callback(fn($n) => $n->get('field_format')->value ?? '')
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
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /**
   * Applies card filter args to an entity query (shared by cards + count query).
   */
  private function applyCardFilters($query, array $args): void {
    if (!empty($args['name'])) {
      $query->condition('title', '%' . $args['name'] . '%', 'LIKE');
    }
    if (!empty($args['type'])) {
      $query->condition('field_type_line', '%' . $args['type'] . '%', 'LIKE');
    }
    if (isset($args['maxCmc']) && $args['maxCmc'] !== NULL) {
      $query->condition('field_cmc', (float) $args['maxCmc'], '<=');
    }
    if (!empty($args['colors'])) {
      $query->condition('field_colors', $args['colors'], 'IN');
    }
    if (!empty($args['titlePrefix'])) {
      $query->condition('title', $args['titlePrefix'] . '%', 'LIKE');
    }
  }

  /**
   * Mirrors the JS slugify() in mtg-app/src/utils/slugify.ts.
   */
  private static function slugify(string $title): string {
    $lower    = mb_strtolower($title, 'UTF-8');
    $stripped = preg_replace("/['\x{2019}\x{2018}`]/u", '', $lower);
    $dashed   = preg_replace('/[^a-z0-9]+/', '-', $stripped ?? '');
    return trim($dashed ?? '', '-');
  }

}
