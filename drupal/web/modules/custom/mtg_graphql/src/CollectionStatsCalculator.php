<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

/**
 * Turns flat collection rows into the collection statistics page data.
 *
 * Pure functions only, so the numbers can be unit tested without a database.
 * Prices follow CollectionReader::value(): a regular copy takes the regular
 * price, then foil, then the same in the other currency converted; a foil
 * copy the same with foil first. A price of 0 counts as no price.
 */
final class CollectionStatsCalculator {

  /**
   * Upper edges of the value bands, per copy.
   */
  public const BAND_EDGES = [0.25, 1.0, 5.0, 20.0, 100.0];

  /**
   * How many of the most valuable copies the concentration lines look at.
   */
  public const TOP_SHARES = [10, 50, 100, 250];

  /**
   * Rarities in display order; anything else is grouped as "other".
   */
  public const RARITIES = ['mythic', 'rare', 'uncommon', 'common', 'special'];

  /**
   * Number of most valuable printings listed.
   */
  public const TOP_CARDS = 25;

  /**
   * Builds every statistic for the page.
   *
   * @param array<int, array<string, mixed>> $rows
   *   Collection rows: title, setCode, setName, rarity, regular, foil, trade,
   *   eur, eurFoil, usd, usdFoil.
   * @param array<int, array{deck: string, nid?: int, card: string, quantity: int}> $deckNeeds
   *   Copies of each card name each deck uses (main deck, sideboard and
   *   commanders; maybeboards excluded).
   * @param array<string, int> $setSizes
   *   Number of printings in the card database per set code.
   * @param bool $eur
   *   TRUE to value in EUR, FALSE for USD.
   * @param float $usdToEur
   *   Euros per US dollar.
   * @param bool $includeTrade
   *   FALSE leaves trade copies out (regular copies first, then foil).
   * @param float $cutoff
   *   Per-copy price that splits valuable cards from bulk.
   *
   * @return array<string, mixed>
   *   Data keyed like the CollectionStats GraphQL type.
   */
  public static function compute(
    array $rows,
    array $deckNeeds,
    array $setSizes,
    bool $eur,
    float $usdToEur,
    bool $includeTrade,
    float $cutoff,
  ): array {
    $lines = self::lines($rows, $eur, $usdToEur, $includeTrade);
    $copies = array_sum(array_column($lines, 'quantity'));
    $value = self::sum($lines);

    $printings = [];
    foreach ($lines as $line) {
      $printings[$line['key']] = TRUE;
    }

    return [
      'currency' => $eur ? 'EUR' : 'USD',
      'includeTrade' => $includeTrade,
      'cutoff' => $cutoff,
      'totals' => [
        'printings' => count($printings),
        'copies' => $copies,
        'regular' => array_sum(array_map(fn($l) => $l['foil'] ? 0 : $l['quantity'], $lines)),
        'foil' => array_sum(array_map(fn($l) => $l['foil'] ? $l['quantity'] : 0, $lines)),
        'trade' => array_sum(array_map(fn($r) => self::tradeCopies($r), $rows)),
        'value' => round($value, 2),
        'average' => $copies > 0 ? round($value / $copies, 2) : 0.0,
        'median' => self::median($lines),
        'unpricedCopies' => array_sum(array_map(fn($l) => $l['unit'] === NULL ? $l['quantity'] : 0, $lines)),
      ],
      'rarities' => self::rarities($lines, $value),
      'bands' => self::bands($lines),
      'aboveCutoff' => self::bucket(array_filter($lines, fn($l) => ($l['unit'] ?? 0.0) >= $cutoff)),
      'belowCutoff' => self::bucket(array_filter($lines, fn($l) => ($l['unit'] ?? 0.0) < $cutoff)),
      'concentration' => self::concentration($lines, $value),
      'topCards' => self::topCards($lines),
      'sets' => self::sets($lines, $setSizes),
      'decks' => self::decks($lines, $deckNeeds),
    ];
  }

  /**
   * Splits rows into priced regular and foil lines with positive quantities.
   *
   * @param array<int, array<string, mixed>> $rows
   *   Collection rows.
   * @param bool $eur
   *   TRUE for EUR.
   * @param float $usdToEur
   *   Euros per US dollar.
   * @param bool $includeTrade
   *   FALSE subtracts trade copies.
   *
   * @return array<int, array<string, mixed>>
   *   Lines with key, title, setCode, setName, rarity, foil, quantity and
   *   unit (NULL when unpriced).
   */
  public static function lines(array $rows, bool $eur, float $usdToEur, bool $includeTrade): array {
    $lines = [];
    foreach ($rows as $row) {
      $regular = max(0, (int) ($row['regular'] ?? 0));
      $foil = max(0, (int) ($row['foil'] ?? 0));
      if (!$includeTrade) {
        $trade = self::tradeCopies($row);
        $fromRegular = min($trade, $regular);
        $regular -= $fromRegular;
        $foil = max(0, $foil - ($trade - $fromRegular));
      }
      $units = [
        FALSE => self::unitPrice($row, FALSE, $eur, $usdToEur),
        TRUE => self::unitPrice($row, TRUE, $eur, $usdToEur),
      ];
      foreach ([FALSE => $regular, TRUE => $foil] as $isFoil => $quantity) {
        if ($quantity < 1) {
          continue;
        }
        $lines[] = [
          'key' => (string) ($row['card'] ?? (($row['setCode'] ?? '') . '|' . ($row['title'] ?? ''))),
          'title' => (string) ($row['title'] ?? ''),
          'setCode' => (string) ($row['setCode'] ?? ''),
          'setName' => (string) ($row['setName'] ?? ''),
          'rarity' => in_array($row['rarity'] ?? '', self::RARITIES, TRUE) ? $row['rarity'] : 'other',
          'foil' => (bool) $isFoil,
          'quantity' => $quantity,
          'unit' => $units[$isFoil],
        ];
      }
    }
    return $lines;
  }

  /**
   * Price of one copy of a printing, or NULL when it has no price.
   *
   * Regular: the regular price, then foil, then the same in the other
   * currency converted. Foil: the same with foil first. 0 means no price.
   *
   * @param array<string, mixed> $row
   *   Prices keyed eur, eurFoil, usd, usdFoil.
   * @param bool $foil
   *   TRUE for a foil copy.
   * @param bool $eur
   *   TRUE for EUR, FALSE for USD.
   * @param float $usdToEur
   *   Euros per US dollar.
   */
  public static function unitPrice(array $row, bool $foil, bool $eur, float $usdToEur): ?float {
    [$cur, $oth] = $eur ? ['eur', 'usd'] : ['usd', 'eur'];
    $factor = $eur ? $usdToEur : 1 / $usdToEur;
    $p = static fn(string $key): ?float => isset($row[$key]) && (float) $row[$key] > 0 ? (float) $row[$key] : NULL;
    $c = static fn(string $key): ?float => $p($key) === NULL ? NULL : $p($key) * $factor;
    return $foil
      ? $p($cur . 'Foil') ?? $p($cur) ?? $c($oth . 'Foil') ?? $c($oth)
      : $p($cur) ?? $p($cur . 'Foil') ?? $c($oth) ?? $c($oth . 'Foil');
  }

  /**
   * Trade copies of a row, capped at the copies it holds.
   *
   * @param array<string, mixed> $row
   *   Collection row.
   */
  private static function tradeCopies(array $row): int {
    $held = max(0, (int) ($row['regular'] ?? 0)) + max(0, (int) ($row['foil'] ?? 0));
    return min($held, max(0, (int) ($row['trade'] ?? 0)));
  }

  /**
   * Total value of lines.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   */
  private static function sum(array $lines): float {
    $total = 0.0;
    foreach ($lines as $line) {
      $total += ($line['unit'] ?? 0.0) * $line['quantity'];
    }
    return $total;
  }

  /**
   * Median price of a single copy (unpriced copies count as 0).
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   */
  private static function median(array $lines): float {
    $copies = array_sum(array_column($lines, 'quantity'));
    if ($copies === 0) {
      return 0.0;
    }
    usort($lines, fn($a, $b) => ($a['unit'] ?? 0.0) <=> ($b['unit'] ?? 0.0));
    $middle = intdiv($copies - 1, 2);
    $needTwo = $copies % 2 === 0;
    $seen = 0;
    $low = NULL;
    foreach ($lines as $line) {
      $seen += $line['quantity'];
      if ($low === NULL && $seen > $middle) {
        $low = $line['unit'] ?? 0.0;
        if (!$needTwo || $seen > $middle + 1) {
          return round($low, 2);
        }
        continue;
      }
      if ($low !== NULL) {
        return round(($low + ($line['unit'] ?? 0.0)) / 2, 2);
      }
    }
    return round((float) $low, 2);
  }

  /**
   * Printings, copies and value of a set of lines.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   *
   * @return array{printings: int, copies: int, value: float}
   *   Bucket totals.
   */
  private static function bucket(array $lines): array {
    return [
      'printings' => count(array_unique(array_column($lines, 'key'))),
      'copies' => array_sum(array_column($lines, 'quantity')),
      'value' => round(self::sum($lines), 2),
    ];
  }

  /**
   * Totals per rarity, in display order.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   * @param float $total
   *   Collection value, for the share.
   *
   * @return array<int, array<string, mixed>>
   *   Rarity rows.
   */
  private static function rarities(array $lines, float $total): array {
    $out = [];
    foreach ([...self::RARITIES, 'other'] as $rarity) {
      $bucket = self::bucket(array_filter($lines, fn($l) => $l['rarity'] === $rarity));
      if ($bucket['copies'] === 0) {
        continue;
      }
      $out[] = ['rarity' => $rarity, 'share' => $total > 0 ? round($bucket['value'] / $total, 4) : 0.0] + $bucket;
    }
    return $out;
  }

  /**
   * Copies and value per price band, plus a band for unpriced copies.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   *
   * @return array<int, array<string, mixed>>
   *   Bands with label, min, max, printings, copies and value.
   */
  private static function bands(array $lines): array {
    $out = [];
    $min = 0.0;
    foreach ([...self::BAND_EDGES, NULL] as $max) {
      $in = array_filter($lines, fn($l) => $l['unit'] !== NULL && $l['unit'] >= $min && ($max === NULL || $l['unit'] < $max));
      $out[] = ['min' => $min, 'max' => $max] + self::bucket($in);
      $min = (float) $max;
    }
    $out[] = ['min' => NULL, 'max' => NULL] + self::bucket(array_filter($lines, fn($l) => $l['unit'] === NULL));
    return $out;
  }

  /**
   * Share of the value held by the most valuable copies.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   * @param float $total
   *   Collection value.
   *
   * @return array<int, array{top: int, value: float, share: float}>
   *   One row per TOP_SHARES size.
   */
  private static function concentration(array $lines, float $total): array {
    usort($lines, fn($a, $b) => ($b['unit'] ?? 0.0) <=> ($a['unit'] ?? 0.0));
    $out = [];
    foreach (self::TOP_SHARES as $top) {
      $left = $top;
      $value = 0.0;
      foreach ($lines as $line) {
        if ($left <= 0) {
          break;
        }
        $take = min($left, $line['quantity']);
        $value += $take * ($line['unit'] ?? 0.0);
        $left -= $take;
      }
      $out[] = [
        'top' => $top,
        'value' => round($value, 2),
        'share' => $total > 0 ? round($value / $total, 4) : 0.0,
      ];
    }
    return $out;
  }

  /**
   * The most valuable printings by price per copy.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   *
   * @return array<int, array<string, mixed>>
   *   Top lines with their total value.
   */
  private static function topCards(array $lines): array {
    $lines = array_filter($lines, fn($l) => $l['unit'] !== NULL);
    usort($lines, fn($a, $b) => [$b['unit'], $b['quantity']] <=> [$a['unit'], $a['quantity']]);
    return array_map(fn($l) => [
      'title' => $l['title'],
      'setCode' => $l['setCode'],
      'setName' => $l['setName'],
      'rarity' => $l['rarity'],
      'foil' => $l['foil'],
      'unitPrice' => round($l['unit'], 2),
      'quantity' => $l['quantity'],
      'value' => round($l['unit'] * $l['quantity'], 2),
    ], array_slice($lines, 0, self::TOP_CARDS));
  }

  /**
   * Totals per set, most valuable first.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   * @param array<string, int> $setSizes
   *   Printings per set code in the card database.
   *
   * @return array<int, array<string, mixed>>
   *   Set rows.
   */
  private static function sets(array $lines, array $setSizes): array {
    $bySet = [];
    foreach ($lines as $line) {
      $bySet[$line['setCode']][] = $line;
    }
    $out = [];
    foreach ($bySet as $code => $setLines) {
      $row = [
        'setCode' => (string) $code,
        'setName' => $setLines[0]['setName'],
        'setSize' => (int) ($setSizes[$code] ?? 0),
      ] + self::bucket($setLines);
      foreach (['mythic', 'rare', 'uncommon', 'common'] as $rarity) {
        $row[$rarity] = array_sum(array_map(fn($l) => $l['rarity'] === $rarity ? $l['quantity'] : 0, $setLines));
      }
      $out[] = $row;
    }
    usort($out, fn($a, $b) => [$b['value'], $b['copies']] <=> [$a['value'], $a['copies']]);
    return $out;
  }

  /**
   * Copies and value tied up in decks, matched by card name.
   *
   * A card name used by several decks needs that many copies in total; the
   * owned copies cover it up to what you have. Value uses the average price
   * of your copies of that name.
   *
   * @param array<int, array<string, mixed>> $lines
   *   Lines.
   * @param array<int, array{deck: string, nid?: int, card: string, quantity: int}> $deckNeeds
   *   Deck usage per card name.
   *
   * @return array<string, mixed>
   *   Totals plus one row per deck.
   */
  private static function decks(array $lines, array $deckNeeds): array {
    $owned = [];
    $value = [];
    foreach ($lines as $line) {
      $owned[$line['title']] = ($owned[$line['title']] ?? 0) + $line['quantity'];
      $value[$line['title']] = ($value[$line['title']] ?? 0.0) + ($line['unit'] ?? 0.0) * $line['quantity'];
    }
    $average = static fn(string $name): float => ($owned[$name] ?? 0) > 0 ? $value[$name] / $owned[$name] : 0.0;

    $needed = [];
    $perDeck = [];
    $deckNids = [];
    foreach ($deckNeeds as $need) {
      $needed[$need['card']] = ($needed[$need['card']] ?? 0) + $need['quantity'];
      $perDeck[$need['deck']][$need['card']] = ($perDeck[$need['deck']][$need['card']] ?? 0) + $need['quantity'];
      $deckNids[$need['deck']] = (int) ($need['nid'] ?? 0);
    }

    $inDecks = 0;
    $inDecksValue = 0.0;
    foreach ($needed as $name => $quantity) {
      $used = min($quantity, $owned[$name] ?? 0);
      $inDecks += $used;
      $inDecksValue += $used * $average($name);
    }

    $decks = [];
    foreach ($perDeck as $deck => $cards) {
      $have = 0;
      $deckValue = 0.0;
      foreach ($cards as $name => $quantity) {
        $used = min($quantity, $owned[$name] ?? 0);
        $have += $used;
        $deckValue += $used * $average($name);
      }
      $decks[] = [
        'nid' => $deckNids[$deck] ?? 0,
        'title' => (string) $deck,
        'needed' => array_sum($cards),
        'owned' => $have,
        'value' => round($deckValue, 2),
      ];
    }
    usort($decks, fn($a, $b) => $b['value'] <=> $a['value']);

    $total = self::sum($lines);
    $copies = array_sum($owned);
    return [
      'copiesInDecks' => $inDecks,
      'valueInDecks' => round($inDecksValue, 2),
      'copiesFree' => $copies - $inDecks,
      'valueFree' => round($total - $inDecksValue, 2),
      'decks' => $decks,
    ];
  }

}
