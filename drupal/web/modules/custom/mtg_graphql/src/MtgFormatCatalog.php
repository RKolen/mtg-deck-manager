<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

use Drupal\taxonomy\TermInterface;

/**
 * Canonical MTG formats for the mtg_format vocabulary.
 *
 * Includes Scryfall constructed formats plus common community formats.
 * MTGGoldfish slugs are set only when a /metagame/{slug} page exists.
 */
final class MtgFormatCatalog {

  /**
   * Format display names and optional Goldfish slugs.
   *
   * @return list<array{name: string, slug: string}>
   *   Each item is a term name and Goldfish slug (empty when not scrapeable).
   */
  public static function definitions(): array {
    return [
      ['name' => 'Standard', 'slug' => 'standard'],
      ['name' => 'Pioneer', 'slug' => 'pioneer'],
      ['name' => 'Modern', 'slug' => 'modern'],
      ['name' => 'Legacy', 'slug' => 'legacy'],
      ['name' => 'Vintage', 'slug' => 'vintage'],
      ['name' => 'Pauper', 'slug' => 'pauper'],
      ['name' => 'Historic', 'slug' => 'historic'],
      ['name' => 'Explorer', 'slug' => 'explorer'],
      ['name' => 'Timeless', 'slug' => 'timeless'],
      ['name' => 'Alchemy', 'slug' => 'alchemy'],
      ['name' => 'Premodern', 'slug' => 'premodern'],
      ['name' => 'Penny Dreadful', 'slug' => 'penny_dreadful'],
      ['name' => 'Commander', 'slug' => 'commander'],
      ['name' => 'Duel Commander', 'slug' => 'duel_commander'],
      ['name' => 'Brawl', 'slug' => 'brawl'],
      ['name' => 'Standard Brawl', 'slug' => ''],
      ['name' => 'Historic Brawl', 'slug' => ''],
      ['name' => 'Pauper Commander', 'slug' => ''],
      ['name' => 'Oathbreaker', 'slug' => ''],
      ['name' => 'Predh', 'slug' => ''],
      ['name' => 'Tiny Leaders', 'slug' => ''],
      ['name' => 'Gladiator', 'slug' => ''],
      ['name' => 'Old School', 'slug' => ''],
      ['name' => 'Canadian Highlander', 'slug' => ''],
      ['name' => 'Peasant', 'slug' => ''],
      ['name' => 'Other', 'slug' => ''],
    ];
  }

  /**
   * Whether the format uses a designated commander card.
   *
   * Gladiator and Canadian Highlander are singleton but have no commander.
   */
  public static function usesCommanderCard(string $formatName): bool {
    $aliases = [
      'EDH' => 'Commander',
      'TLR' => 'Tiny Leaders',
    ];
    $name = $aliases[$formatName] ?? $formatName;
    $normalized = strtolower(trim(preg_replace('/[:\-]+/', ' ', $name) ?? $name));
    $normalized = preg_replace('/\s+/', ' ', $normalized) ?? $normalized;
    return in_array($normalized, [
      'edh',
      'commander',
      'tiny leader',
      'tiny leaders',
      'tinyleaders',
      'tlr',
      'tiny leaders reborn',
      'duel commander',
      'pauper commander',
      'predh',
      'brawl',
      'standard brawl',
      'historic brawl',
      'oathbreaker',
    ], TRUE);
  }

  /**
   * Creates missing mtg_format terms and refreshes Goldfish slugs.
   *
   * @return array{created: string[], updated: string[]}
   *   Term names that were created or had their slug updated.
   */
  public static function ensureTerms(): array {
    $storage = \Drupal::entityTypeManager()->getStorage('taxonomy_term');
    $created = [];
    $updated = [];

    foreach (self::definitions() as $definition) {
      $existing = $storage->loadByProperties([
        'vid' => 'mtg_format',
        'name' => $definition['name'],
      ]);
      $term = reset($existing);
      if (!$term instanceof TermInterface) {
        $term = $storage->create([
          'vid' => 'mtg_format',
          'name' => $definition['name'],
          'field_goldfish_slug' => $definition['slug'],
        ]);
        $term->save();
        $created[] = $definition['name'];
        continue;
      }

      $current = (string) ($term->get('field_goldfish_slug')->value ?? '');
      if ($current !== $definition['slug']) {
        $term->set('field_goldfish_slug', $definition['slug']);
        $term->save();
        $updated[] = $definition['name'];
      }
    }

    return [
      'created' => $created,
      'updated' => $updated,
    ];
  }

}
