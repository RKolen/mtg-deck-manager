<?php

/**
 * Adds field_main_cards (cardinality 60) and field_sideboard_cards
 * (cardinality 15) entity reference fields to the deck content type.
 *
 * Run with: ddev drush php:script scripts/add_deck_fields.php
 */

declare(strict_types=1);

// -----------------------------------------------------------------------
// field_main_cards storage + instance
// -----------------------------------------------------------------------

$main_storage = \Drupal\field\Entity\FieldStorageConfig::loadByName('node', 'field_main_cards');
if (!$main_storage) {
  $main_storage = \Drupal\field\Entity\FieldStorageConfig::create([
    'field_name' => 'field_main_cards',
    'entity_type' => 'node',
    'type' => 'entity_reference',
    'cardinality' => 60,
    'settings' => ['target_type' => 'node'],
  ]);
  $main_storage->save();
  echo 'Created field_main_cards storage.' . PHP_EOL;
}
else {
  echo 'field_main_cards storage already exists.' . PHP_EOL;
}

$main_field = \Drupal\field\Entity\FieldConfig::loadByName('node', 'deck', 'field_main_cards');
if (!$main_field) {
  $main_field = \Drupal\field\Entity\FieldConfig::create([
    'field_storage' => $main_storage,
    'bundle' => 'deck',
    'label' => 'Main Deck',
    'required' => FALSE,
    'settings' => [
      'handler' => 'default:node',
      'handler_settings' => [
        'target_bundles' => ['mtg_card' => 'mtg_card'],
      ],
    ],
  ]);
  $main_field->save();
  echo 'Created field_main_cards on deck bundle.' . PHP_EOL;
}
else {
  echo 'field_main_cards on deck already exists.' . PHP_EOL;
}

// -----------------------------------------------------------------------
// field_sideboard_cards storage + instance
// -----------------------------------------------------------------------

$sb_storage = \Drupal\field\Entity\FieldStorageConfig::loadByName('node', 'field_sideboard_cards');
if (!$sb_storage) {
  $sb_storage = \Drupal\field\Entity\FieldStorageConfig::create([
    'field_name' => 'field_sideboard_cards',
    'entity_type' => 'node',
    'type' => 'entity_reference',
    'cardinality' => 15,
    'settings' => ['target_type' => 'node'],
  ]);
  $sb_storage->save();
  echo 'Created field_sideboard_cards storage.' . PHP_EOL;
}
else {
  echo 'field_sideboard_cards storage already exists.' . PHP_EOL;
}

$sb_field = \Drupal\field\Entity\FieldConfig::loadByName('node', 'deck', 'field_sideboard_cards');
if (!$sb_field) {
  $sb_field = \Drupal\field\Entity\FieldConfig::create([
    'field_storage' => $sb_storage,
    'bundle' => 'deck',
    'label' => 'Sideboard',
    'required' => FALSE,
    'settings' => [
      'handler' => 'default:node',
      'handler_settings' => [
        'target_bundles' => ['mtg_card' => 'mtg_card'],
      ],
    ],
  ]);
  $sb_field->save();
  echo 'Created field_sideboard_cards on deck bundle.' . PHP_EOL;
}
else {
  echo 'field_sideboard_cards on deck already exists.' . PHP_EOL;
}

// -----------------------------------------------------------------------
// Update deck form display.
// -----------------------------------------------------------------------

$form_display = \Drupal\Core\Entity\Entity\EntityFormDisplay::load('node.deck.default');
if ($form_display) {
  $form_display->setComponent('field_main_cards', [
    'type' => 'entity_reference_autocomplete',
    'weight' => 10,
    'settings' => [
      'match_operator' => 'CONTAINS',
      'size' => 60,
      'placeholder' => '',
    ],
  ]);
  $form_display->setComponent('field_sideboard_cards', [
    'type' => 'entity_reference_autocomplete',
    'weight' => 11,
    'settings' => [
      'match_operator' => 'CONTAINS',
      'size' => 60,
      'placeholder' => '',
    ],
  ]);
  $form_display->save();
  echo 'Updated deck form display.' . PHP_EOL;
}
else {
  echo 'WARNING: deck form display not found.' . PHP_EOL;
}

echo 'Done.' . PHP_EOL;
