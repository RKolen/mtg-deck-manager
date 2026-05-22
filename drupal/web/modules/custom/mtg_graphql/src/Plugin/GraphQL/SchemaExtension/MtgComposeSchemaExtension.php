<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Plugin\GraphQL\SchemaExtension;

use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\graphql\Attribute\SchemaExtension;
use Drupal\graphql\GraphQL\ResolverBuilder;
use Drupal\graphql\GraphQL\ResolverRegistryInterface;
use Drupal\graphql\Plugin\GraphQL\SchemaExtension\SdlSchemaExtensionPluginBase;
use Drupal\mtg_graphql\MtgGraphqlResolverRegistration;

/**
 * Extends GraphQL Compose with MTG queries, mutations, and types.
 */
#[SchemaExtension(
  id: 'mtg_compose',
  name: new TranslatableMarkup('MTG Deck Manager'),
  description: new TranslatableMarkup('Card search, deck mutations, meta decks, and simulation history.'),
  schema: 'graphql_compose',
)]
final class MtgComposeSchemaExtension extends SdlSchemaExtensionPluginBase {

  /**
   * {@inheritdoc}
   */
  public function registerResolvers(ResolverRegistryInterface $registry): void {
    MtgGraphqlResolverRegistration::register($registry);
  }

}
