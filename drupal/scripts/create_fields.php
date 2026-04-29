<?php

/**
 * Drush PHP script: create all custom fields for MTG content types.
 *
 * Run with: ddev drush php:script scripts/create_fields.php
 */

use Drupal\field\Entity\FieldConfig;
use Drupal\field\Entity\FieldStorageConfig;

/**
 * Helper: create a field storage if it doesn't exist.
 */
function ensure_field_storage(string $entity_type, string $field_name, string $field_type, array $settings = []): void {
  if (!FieldStorageConfig::loadByName($entity_type, $field_name)) {
    FieldStorageConfig::create([
      'field_name' => $field_name,
      'entity_type' => $entity_type,
      'type' => $field_type,
      'cardinality' => $settings['cardinality'] ?? 1,
      'settings' => $settings['storage_settings'] ?? [],
    ])->save();
  }
}

/**
 * Helper: attach a field to a bundle if it doesn't exist.
 */
function ensure_field(string $entity_type, string $bundle, string $field_name, string $label, array $settings = []): void {
  if (!FieldConfig::loadByName($entity_type, $bundle, $field_name)) {
    FieldConfig::create([
      'field_name' => $field_name,
      'entity_type' => $entity_type,
      'bundle' => $bundle,
      'label' => $label,
      'required' => $settings['required'] ?? FALSE,
      'settings' => $settings['field_settings'] ?? [],
    ])->save();
  }
}

// ---------------------------------------------------------------------------
// mtg_card fields
// ---------------------------------------------------------------------------

// Mana cost string, e.g. "{2}{B}{B}"
ensure_field_storage('node', 'field_mana_cost', 'string');
ensure_field('node', 'mtg_card', 'field_mana_cost', 'Mana Cost');

// Converted mana cost (decimal to support split cards)
ensure_field_storage('node', 'field_cmc', 'decimal', ['storage_settings' => ['precision' => 5, 'scale' => 1]]);
ensure_field('node', 'mtg_card', 'field_cmc', 'CMC');

// Type line, e.g. "Creature — Human Wizard"
ensure_field_storage('node', 'field_type_line', 'string');
ensure_field('node', 'mtg_card', 'field_type_line', 'Type Line');

// Colors: list of W/U/B/R/G values (multi-value)
ensure_field_storage('node', 'field_colors', 'string', ['cardinality' => -1]);
ensure_field('node', 'mtg_card', 'field_colors', 'Colors');

// Color identity (Commander rule, may differ from colors)
ensure_field_storage('node', 'field_color_identity', 'string', ['cardinality' => -1]);
ensure_field('node', 'mtg_card', 'field_color_identity', 'Color Identity');

// Oracle text (long text)
ensure_field_storage('node', 'field_oracle_text', 'text_long');
ensure_field('node', 'mtg_card', 'field_oracle_text', 'Oracle Text');

// Scryfall ID for deduplication
ensure_field_storage('node', 'field_scryfall_id', 'string');
ensure_field('node', 'mtg_card', 'field_scryfall_id', 'Scryfall ID', ['required' => TRUE]);

// Card image URI from Scryfall
ensure_field_storage('node', 'field_image_uri', 'string', ['storage_settings' => ['max_length' => 512]]);
ensure_field('node', 'mtg_card', 'field_image_uri', 'Image URI');

// Whether this card can produce mana (Birds of Paradise, land, etc.)
ensure_field_storage('node', 'field_is_mana_producer', 'boolean');
ensure_field('node', 'mtg_card', 'field_is_mana_producer', 'Is Mana Producer');

// Colors this card can produce (for 0.5-land rule)
ensure_field_storage('node', 'field_produced_mana', 'string', ['cardinality' => -1]);
ensure_field('node', 'mtg_card', 'field_produced_mana', 'Produced Mana');

echo "mtg_card fields done.\n";

// ---------------------------------------------------------------------------
// deck fields
// ---------------------------------------------------------------------------

ensure_field_storage('node', 'field_format', 'string');
ensure_field('node', 'deck', 'field_format', 'Format');

ensure_field_storage('node', 'field_notes', 'text_long');
ensure_field('node', 'deck', 'field_notes', 'Notes');

echo "deck fields done.\n";

// ---------------------------------------------------------------------------
// deck_card fields
// ---------------------------------------------------------------------------

// Entity reference to deck node
ensure_field_storage('node', 'field_deck', 'entity_reference', [
  'storage_settings' => ['target_type' => 'node'],
]);
ensure_field('node', 'deck_card', 'field_deck', 'Deck', [
  'required' => TRUE,
  'field_settings' => ['handler' => 'default:node', 'handler_settings' => ['target_bundles' => ['deck' => 'deck']]],
]);

// Entity reference to mtg_card node
ensure_field_storage('node', 'field_card', 'entity_reference', [
  'storage_settings' => ['target_type' => 'node'],
]);
ensure_field('node', 'deck_card', 'field_card', 'Card', [
  'required' => TRUE,
  'field_settings' => ['handler' => 'default:node', 'handler_settings' => ['target_bundles' => ['mtg_card' => 'mtg_card']]],
]);

ensure_field_storage('node', 'field_quantity', 'integer');
ensure_field('node', 'deck_card', 'field_quantity', 'Quantity', ['required' => TRUE]);

ensure_field_storage('node', 'field_is_sideboard', 'boolean');
ensure_field('node', 'deck_card', 'field_is_sideboard', 'Is Sideboard');

echo "deck_card fields done.\n";

// ---------------------------------------------------------------------------
// collection_card fields
// ---------------------------------------------------------------------------

// Reuse field_card storage (already created above)
ensure_field('node', 'collection_card', 'field_card', 'Card', [
  'required' => TRUE,
  'field_settings' => ['handler' => 'default:node', 'handler_settings' => ['target_bundles' => ['mtg_card' => 'mtg_card']]],
]);

ensure_field_storage('node', 'field_quantity_owned', 'integer');
ensure_field('node', 'collection_card', 'field_quantity_owned', 'Quantity Owned');

ensure_field_storage('node', 'field_quantity_foil', 'integer');
ensure_field('node', 'collection_card', 'field_quantity_foil', 'Quantity Foil');

echo "collection_card fields done.\n";
echo "All fields created successfully.\n";

// ---------------------------------------------------------------------------
// Form displays: create all entity_form_display configs with field groups.
// ---------------------------------------------------------------------------

use Drupal\Core\Entity\Entity\EntityFormDisplay;

/**
 * Returns an EntityFormDisplay, creating it if it does not yet exist.
 */
function get_or_create_form_display(string $entity_type, string $bundle): EntityFormDisplay {
  $display = EntityFormDisplay::load("{$entity_type}.{$bundle}.default");
  if ($display === NULL) {
    $display = EntityFormDisplay::create([
      'targetEntityType' => $entity_type,
      'bundle'           => $bundle,
      'mode'             => 'default',
      'status'           => TRUE,
    ]);
  }
  return $display;
}

// ---------------------------------------------------------------------------
// mtg_card: tabs: Identity | Gameplay | Scryfall Data
// ---------------------------------------------------------------------------

$mtg_card_display = get_or_create_form_display('node', 'mtg_card');

// Standard node fields.
$mtg_card_display->setComponent('title', [
  'type'   => 'string_textfield',
  'weight' => 0,
  'region' => 'content',
  'settings' => ['size' => 60, 'placeholder' => ''],
]);

// Identity tab fields.
foreach ([
  'field_mana_cost'     => ['type' => 'string_textfield', 'weight' => 1],
  'field_cmc'           => ['type' => 'number',            'weight' => 2],
  'field_type_line'     => ['type' => 'string_textfield',  'weight' => 3],
  'field_colors'        => ['type' => 'string_textfield',  'weight' => 4],
  'field_color_identity'=> ['type' => 'string_textfield',  'weight' => 5],
] as $field => $options) {
  $mtg_card_display->setComponent($field, $options + ['region' => 'content']);
}

// Gameplay tab fields.
foreach ([
  'field_oracle_text'      => ['type' => 'text_textarea',     'weight' => 6],
  'field_is_mana_producer' => ['type' => 'boolean_checkbox',  'weight' => 7],
  'field_produced_mana'    => ['type' => 'string_textfield',  'weight' => 8],
] as $field => $options) {
  $mtg_card_display->setComponent($field, $options + ['region' => 'content']);
}

// Scryfall tab fields.
foreach ([
  'field_scryfall_id' => ['type' => 'string_textfield', 'weight' => 9],
  'field_image_uri'   => ['type' => 'string_textfield', 'weight' => 10],
] as $field => $options) {
  $mtg_card_display->setComponent($field, $options + ['region' => 'content']);
}

// Field groups: tabs wrapper → three tab children.
$mtg_card_display->setThirdPartySetting('field_group', 'group_mtg_card_tabs', [
  'label'           => 'Card details',
  'children'        => ['group_identity', 'group_gameplay', 'group_scryfall'],
  'parent_name'     => '',
  'weight'          => 1,
  'region'          => 'content',
  'format_type'     => 'tabs',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => '',
  ],
]);

$mtg_card_display->setThirdPartySetting('field_group', 'group_identity', [
  'label'           => 'Identity',
  'children'        => ['title', 'field_mana_cost', 'field_cmc', 'field_type_line', 'field_colors', 'field_color_identity'],
  'parent_name'     => 'group_mtg_card_tabs',
  'weight'          => 0,
  'region'          => 'content',
  'format_type'     => 'tab',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => 'Identity',
    'description'    => '',
    'show_empty_fields' => FALSE,
  ],
]);

$mtg_card_display->setThirdPartySetting('field_group', 'group_gameplay', [
  'label'           => 'Gameplay',
  'children'        => ['field_oracle_text', 'field_is_mana_producer', 'field_produced_mana'],
  'parent_name'     => 'group_mtg_card_tabs',
  'weight'          => 1,
  'region'          => 'content',
  'format_type'     => 'tab',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => 'Gameplay',
    'description'    => '',
    'show_empty_fields' => FALSE,
  ],
]);

$mtg_card_display->setThirdPartySetting('field_group', 'group_scryfall', [
  'label'           => 'Scryfall Data',
  'children'        => ['field_scryfall_id', 'field_image_uri'],
  'parent_name'     => 'group_mtg_card_tabs',
  'weight'          => 2,
  'region'          => 'content',
  'format_type'     => 'tab',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => 'Scryfall Data',
    'description'    => '',
    'show_empty_fields' => FALSE,
  ],
]);

$mtg_card_display->save();
echo "mtg_card form display + field groups saved.\n";

// ---------------------------------------------------------------------------
// deck: tabs: Details | Notes
// ---------------------------------------------------------------------------

$deck_display = get_or_create_form_display('node', 'deck');

$deck_display->setComponent('title', [
  'type'     => 'string_textfield',
  'weight'   => 0,
  'region'   => 'content',
  'settings' => ['size' => 60, 'placeholder' => ''],
]);

$deck_display->setComponent('field_format', [
  'type'   => 'string_textfield',
  'weight' => 1,
  'region' => 'content',
]);

$deck_display->setComponent('field_notes', [
  'type'   => 'text_textarea',
  'weight' => 2,
  'region' => 'content',
]);

$deck_display->setThirdPartySetting('field_group', 'group_deck_tabs', [
  'label'           => 'Deck',
  'children'        => ['group_deck_details', 'group_deck_notes'],
  'parent_name'     => '',
  'weight'          => 1,
  'region'          => 'content',
  'format_type'     => 'tabs',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => '',
  ],
]);

$deck_display->setThirdPartySetting('field_group', 'group_deck_details', [
  'label'           => 'Details',
  'children'        => ['title', 'field_format'],
  'parent_name'     => 'group_deck_tabs',
  'weight'          => 0,
  'region'          => 'content',
  'format_type'     => 'tab',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => 'Details',
    'description'    => '',
    'show_empty_fields' => FALSE,
  ],
]);

$deck_display->setThirdPartySetting('field_group', 'group_deck_notes', [
  'label'           => 'Notes',
  'children'        => ['field_notes'],
  'parent_name'     => 'group_deck_tabs',
  'weight'          => 1,
  'region'          => 'content',
  'format_type'     => 'tab',
  'format_settings' => [
    'direction'      => 'horizontal',
    'id'             => '',
    'classes'        => '',
    'label'          => 'Notes',
    'description'    => '',
    'show_empty_fields' => FALSE,
  ],
]);

$deck_display->save();
echo "deck form display + field groups saved.\n";

// ---------------------------------------------------------------------------
// deck_card: flat form, no tabs needed
// ---------------------------------------------------------------------------

$deck_card_display = get_or_create_form_display('node', 'deck_card');
$deck_card_display->setComponent('title',            ['type' => 'string_textfield',           'weight' => 0, 'region' => 'content']);
$deck_card_display->setComponent('field_deck',       ['type' => 'entity_reference_autocomplete', 'weight' => 1, 'region' => 'content']);
$deck_card_display->setComponent('field_card',       ['type' => 'entity_reference_autocomplete', 'weight' => 2, 'region' => 'content']);
$deck_card_display->setComponent('field_quantity',   ['type' => 'number',                     'weight' => 3, 'region' => 'content']);
$deck_card_display->setComponent('field_is_sideboard', ['type' => 'boolean_checkbox',         'weight' => 4, 'region' => 'content']);
$deck_card_display->save();
echo "deck_card form display saved.\n";

// ---------------------------------------------------------------------------
// collection_card: flat form, no tabs needed
// ---------------------------------------------------------------------------

$cc_display = get_or_create_form_display('node', 'collection_card');
$cc_display->setComponent('title',                ['type' => 'string_textfield',              'weight' => 0, 'region' => 'content']);
$cc_display->setComponent('field_card',           ['type' => 'entity_reference_autocomplete', 'weight' => 1, 'region' => 'content']);
$cc_display->setComponent('field_quantity_owned', ['type' => 'number',                        'weight' => 2, 'region' => 'content']);
$cc_display->setComponent('field_quantity_foil',  ['type' => 'number',                        'weight' => 3, 'region' => 'content']);
$cc_display->save();
echo "collection_card form display saved.\n";

echo "All form displays configured.\n";
