<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

/**
 * Builds the per-deck and per-set statistics pages from flat rows.
 *
 * Pure functions, so the numbers can be unit tested without a database.
 * Prices use CollectionStatsCalculator::unitPrice().
 */
final class StatsDetailCalculator {

  /**
   * Deck statistics: every card with its price and how much of it you own.
   *
   * Ownership is matched by card name (any printing), like the wishlist. A
   * name that appears in several slots (e.g. main and sideboard) shares the
   * owned copies, filled in slot order. Missing copies are priced at the
   * cheapest printing of the name.
   *
   * @param array<int, array<string, mixed>> $slots
   *   Deck slots: cardId, title, board (commander|main|side), quantity, foil,
   *   setCode, setName, collectorNumber, rarity, eur, eurFoil, usd, usdFoil.
   * @param array<string, int> $ownedByName
   *   Copies owned (regular plus foil) per card name.
   * @param array<string, array<string, mixed>> $cheapestByName
   *   Lowest prices per card name, keyed eur, eurFoil, usd, usdFoil.
   * @param array<string, int> $otherDecksByName
   *   Number of other decks using each card name.
   * @param bool $eur
   *   TRUE for EUR.
   * @param float $usdToEur
   *   Euros per US dollar.
   *
   * @return array{totals: array<string, mixed>, cards: array<int, array<string, mixed>>}
   *   Totals and one row per slot.
   */
  public static function deck(
    array $slots,
    array $ownedByName,
    array $cheapestByName,
    array $otherDecksByName,
    bool $eur,
    float $usdToEur,
  ): array {
    $left = $ownedByName;
    $cards = [];
    $totals = [
      'cards' => 0,
      'ownedCopies' => 0,
      'missingCopies' => 0,
      'value' => 0.0,
      'ownedValue' => 0.0,
      'costToComplete' => 0.0,
      'unpricedMissing' => 0,
      'sharedCards' => 0,
    ];
    foreach ($slots as $slot) {
      $title = (string) $slot['title'];
      $quantity = max(1, (int) ($slot['quantity'] ?? 1));
      $unit = CollectionStatsCalculator::unitPrice($slot, (bool) ($slot['foil'] ?? FALSE), $eur, $usdToEur);
      $covered = min($quantity, max(0, $left[$title] ?? 0));
      $left[$title] = ($left[$title] ?? 0) - $covered;
      $missing = $quantity - $covered;
      $cheapest = isset($cheapestByName[$title])
        ? CollectionStatsCalculator::unitPrice($cheapestByName[$title], FALSE, $eur, $usdToEur)
        : NULL;
      $missingUnit = $cheapest ?? $unit;
      $otherDecks = (int) ($otherDecksByName[$title] ?? 0);

      $cards[] = [
        'cardId' => (string) ($slot['cardId'] ?? ''),
        'title' => $title,
        'board' => (string) ($slot['board'] ?? 'main'),
        'quantity' => $quantity,
        'foil' => (bool) ($slot['foil'] ?? FALSE),
        'setCode' => (string) ($slot['setCode'] ?? ''),
        'setName' => (string) ($slot['setName'] ?? ''),
        'collectorNumber' => (string) ($slot['collectorNumber'] ?? ''),
        'rarity' => (string) ($slot['rarity'] ?? ''),
        'unitPrice' => $unit === NULL ? NULL : round($unit, 2),
        'value' => round(($unit ?? 0.0) * $quantity, 2),
        'owned' => (int) ($ownedByName[$title] ?? 0),
        'covered' => $covered,
        'missing' => $missing,
        'cheapestPrice' => $cheapest === NULL ? NULL : round($cheapest, 2),
        'costToComplete' => round(($missingUnit ?? 0.0) * $missing, 2),
        'otherDecks' => $otherDecks,
        'status' => $missing === 0 ? 'owned' : ($covered > 0 ? 'partial' : 'missing'),
      ];

      $totals['cards'] += $quantity;
      $totals['ownedCopies'] += $covered;
      $totals['missingCopies'] += $missing;
      $totals['value'] += ($unit ?? 0.0) * $quantity;
      $totals['ownedValue'] += ($unit ?? 0.0) * $covered;
      $totals['costToComplete'] += ($missingUnit ?? 0.0) * $missing;
      if ($missing > 0 && $missingUnit === NULL) {
        $totals['unpricedMissing'] += $missing;
      }
      if ($otherDecks > 0) {
        $totals['sharedCards']++;
      }
    }
    foreach (['value', 'ownedValue', 'costToComplete'] as $key) {
      $totals[$key] = round($totals[$key], 2);
    }
    return ['totals' => $totals, 'cards' => $cards];
  }

  /**
   * Set statistics: every printing in the set with owned copies and prices.
   *
   * @param array<int, array<string, mixed>> $printings
   *   Printings: cardId, title, collectorNumber, rarity, regular, foil, eur,
   *   eurFoil, usd, usdFoil.
   * @param bool $eur
   *   TRUE for EUR.
   * @param float $usdToEur
   *   Euros per US dollar.
   *
   * @return array{totals: array<string, mixed>, rarities: array<int, array<string, mixed>>, cards: array<int, array<string, mixed>>}
   *   Totals, completion per rarity and one row per printing.
   */
  public static function set(array $printings, bool $eur, float $usdToEur): array {
    usort($printings, fn($a, $b) => strnatcmp((string) $a['collectorNumber'], (string) $b['collectorNumber']));
    $cards = [];
    $totals = [
      'printings' => 0,
      'ownedPrintings' => 0,
      'copies' => 0,
      'foilCopies' => 0,
      'value' => 0.0,
      'costToComplete' => 0.0,
      'unpricedMissing' => 0,
    ];
    $byRarity = [];
    foreach ($printings as $p) {
      $regular = max(0, (int) ($p['regular'] ?? 0));
      $foil = max(0, (int) ($p['foil'] ?? 0));
      $unit = CollectionStatsCalculator::unitPrice($p, FALSE, $eur, $usdToEur);
      $foilUnit = CollectionStatsCalculator::unitPrice($p, TRUE, $eur, $usdToEur);
      $value = ($unit ?? 0.0) * $regular + ($foilUnit ?? 0.0) * $foil;
      $owned = $regular + $foil > 0;
      $rarity = (string) ($p['rarity'] ?? '');

      $cards[] = [
        'cardId' => (string) ($p['cardId'] ?? ''),
        'title' => (string) $p['title'],
        'collectorNumber' => (string) ($p['collectorNumber'] ?? ''),
        'rarity' => $rarity,
        'regular' => $regular,
        'foil' => $foil,
        'unitPrice' => $unit === NULL ? NULL : round($unit, 2),
        'foilPrice' => $foilUnit === NULL ? NULL : round($foilUnit, 2),
        'value' => round($value, 2),
        'owned' => $owned,
      ];

      $totals['printings']++;
      $totals['copies'] += $regular + $foil;
      $totals['foilCopies'] += $foil;
      $totals['value'] += $value;
      $byRarity[$rarity] ??= ['rarity' => $rarity, 'printings' => 0, 'owned' => 0, 'value' => 0.0];
      $byRarity[$rarity]['printings']++;
      $byRarity[$rarity]['value'] += $value;
      if ($owned) {
        $totals['ownedPrintings']++;
        $byRarity[$rarity]['owned']++;
      }
      elseif ($unit === NULL) {
        $totals['unpricedMissing']++;
      }
      else {
        $totals['costToComplete'] += $unit;
      }
    }
    foreach (['value', 'costToComplete'] as $key) {
      $totals[$key] = round($totals[$key], 2);
    }
    $order = array_flip([...CollectionStatsCalculator::RARITIES, '']);
    $rarities = array_values($byRarity);
    usort($rarities, fn($a, $b) => ($order[$a['rarity']] ?? 99) <=> ($order[$b['rarity']] ?? 99));
    foreach ($rarities as &$r) {
      $r['value'] = round($r['value'], 2);
    }
    unset($r);
    return ['totals' => $totals, 'rarities' => $rarities, 'cards' => $cards];
  }

}
