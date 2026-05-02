<?php
/**
 * Drush script: index all remaining Milvus card index items.
 *
 * Usage: ddev drush scr index_cards.php
 *
 * Bypasses Drush's broken batch runner by calling indexItems() directly
 * in a loop inside a single PHP process.
 */

declare(strict_types=1);

$index = \Drupal\search_api\Entity\Index::load('milvus_card_index');

if ($index === NULL) {
  echo "ERROR: milvus_card_index not found.\n";
  exit(1);
}

$batchSize = 25;
$total = 0;
$errors = 0;

echo "Starting indexing. Remaining: " . ($index->getTrackerInstance()->getIndexedItemsCount()) . " indexed, ";
echo ($index->getTrackerInstance()->getTotalItemsCount() - $index->getTrackerInstance()->getIndexedItemsCount()) . " to go.\n";
flush();

while (TRUE) {
  try {
    $indexed = $index->indexItems($batchSize);
  }
  catch (\Exception $e) {
    echo "ERROR: " . $e->getMessage() . "\n";
    $errors++;
    if ($errors >= 5) {
      echo "Too many errors, stopping.\n";
      break;
    }
    continue;
  }

  if ($indexed === 0) {
    echo "No more items to index.\n";
    break;
  }

  $total += $indexed;
  $remaining = $index->getTrackerInstance()->getTotalItemsCount()
    - $index->getTrackerInstance()->getIndexedItemsCount();
  echo "Indexed +{$indexed} (total this run: {$total}, remaining: {$remaining})\n";
  flush();
}

echo "Done. Indexed {$total} items this run.\n";
