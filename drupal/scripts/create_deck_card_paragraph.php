<?php

/**
 * Creates the deck_card paragraph type with card reference, quantity, and
 * sideboard flag, then adds a field_deck_cards paragraphs field to the deck
 * content type.
 *
 * Run with: ddev drush php-script scripts/create_deck_card_paragraph.php
 */

use Drupal\paragraphs\Entity\ParagraphsType;
use Drupal\field\Entity\FieldStorageConfig;
use Drupal\field\Entity\FieldConfig;

// ---------------------------------------------------------------------------
// 1. Create the paragraph type.
// ---------------------------------------------------------------------------

if (!\Drupal::entityTypeManager()->getStorage('paragraphs_type')->load('deck_card')) {
  ParagraphsType::create([
    'id' => 'deck_card',
    'label' => 'Deck Card',
  ])->save();
  echo "Created paragraph type: deck_card\n";
}
else {
  echo "Paragraph type deck_card already exists.\n";
}

// ---------------------------------------------------------------------------
// 2. field_card — entity reference to mtg_card node.
// ---------------------------------------------------------------------------

if (!FieldStorageConfig::loadByName('paragraph', 'field_card')) {
  FieldStorageConfig::create([
    'field_name' => 'field_card',
    'entity_type' => 'paragraph',
    'type' => 'entity_reference',
    'cardinality' => 1,
    'settings' => ['target_type' => 'node'],
  ])->save();
  echo "Created field storage: paragraph.field_card\n";
}

if (!FieldConfig::loadByName('paragraph', 'deck_card', 'field_card')) {
  FieldConfig::create([
    'field_name' => 'field_card',
    'entity_type' => 'paragraph',
    'bundle' => 'deck_card',
    'label' => 'Card',
    'required' => TRUE,
    'settings' => [
      'handler' => 'default:node',
      'handler_settings' => [
        'target_bundles' => ['mtg_card' => 'mtg_card'],
        'auto_create' => FALSE,
      ],
    ],
  ])->save();
  echo "Created field config: paragraph.deck_card.field_card\n";
}

// ---------------------------------------------------------------------------
// 3. field_quantity — integer, default 1.
// ---------------------------------------------------------------------------

if (!FieldStorageConfig::loadByName('paragraph', 'field_quantity')) {
  FieldStorageConfig::create([
    'field_name' => 'field_quantity',
    'entity_type' => 'paragraph',
    'type' => 'integer',
    'cardinality' => 1,
  ])->save();
  echo "Created field storage: paragraph.field_quantity\n";
}

if (!FieldConfig::loadByName('paragraph', 'deck_card', 'field_quantity')) {
  FieldConfig::create([
    'field_name' => 'field_quantity',
    'entity_type' => 'paragraph',
    'bundle' => 'deck_card',
    'label' => 'Quantity',
    'required' => TRUE,
    'default_value' => [['value' => 1]],
  ])->save();
  echo "Created field config: paragraph.deck_card.field_quantity\n";
}

// ---------------------------------------------------------------------------
// 4. field_is_sideboard — boolean.
// ---------------------------------------------------------------------------

if (!FieldStorageConfig::loadByName('paragraph', 'field_is_sideboard')) {
  FieldStorageConfig::create([
    'field_name' => 'field_is_sideboard',
    'entity_type' => 'paragraph',
    'type' => 'boolean',
    'cardinality' => 1,
  ])->save();
  echo "Created field storage: paragraph.field_is_sideboard\n";
}

if (!FieldConfig::loadByName('paragraph', 'deck_card', 'field_is_sideboard')) {
  FieldConfig::create([
    'field_name' => 'field_is_sideboard',
    'entity_type' => 'paragraph',
    'bundle' => 'deck_card',
    'label' => 'Is Sideboard',
    'required' => FALSE,
    'default_value' => [['value' => 0]],
  ])->save();
  echo "Created field config: paragraph.deck_card.field_is_sideboard\n";
}

// ---------------------------------------------------------------------------
// 5. field_deck_cards — paragraphs field on the deck node type.
// ---------------------------------------------------------------------------

if (!FieldStorageConfig::loadByName('node', 'field_deck_cards')) {
  FieldStorageConfig::create([
    'field_name' => 'field_deck_cards',
    'entity_type' => 'node',
    'type' => 'entity_reference_revisions',
    'cardinality' => -1,
    'settings' => ['target_type' => 'paragraph'],
  ])->save();
  echo "Created field storage: node.field_deck_cards\n";
}

if (!FieldConfig::loadByName('node', 'deck', 'field_deck_cards')) {
  FieldConfig::create([
    'field_name' => 'field_deck_cards',
    'entity_type' => 'node',
    'bundle' => 'deck',
    'label' => 'Deck Cards',
    'required' => FALSE,
    'settings' => [
      'handler' => 'default:paragraph',
      'handler_settings' => [
        'target_bundles' => ['deck_card' => 'deck_card'],
        'target_bundles_drag_drop' => ['deck_card' => ['enabled' => TRUE, 'weight' => 0]],
      ],
    ],
  ])->save();
  echo "Created field config: node.deck.field_deck_cards\n";
}

echo "Done.\n";
