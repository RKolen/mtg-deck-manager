<?php

declare(strict_types=1);

namespace Drupal\Tests\mtg_graphql\Unit;

use Drupal\mtg_graphql\CollectionStatsCalculator;
use Drupal\Tests\UnitTestCase;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\Group;

/**
 * Tests the collection statistics numbers.
 */
#[CoversClass(CollectionStatsCalculator::class)]
#[Group('mtg_graphql')]
final class CollectionStatsCalculatorTest extends UnitTestCase {

  /**
   * Builds a collection row.
   *
   * @return array<string, mixed>
   *   Row data.
   */
  private static function row(int $card, string $title, string $set, string $rarity, int $regular, int $foil, ?float $eur, ?float $eurFoil = NULL, int $trade = 0, ?float $usd = NULL): array {
    return [
      'card' => $card,
      'title' => $title,
      'setCode' => $set,
      'setName' => strtoupper($set),
      'rarity' => $rarity,
      'regular' => $regular,
      'foil' => $foil,
      'trade' => $trade,
      'eur' => $eur,
      'eurFoil' => $eurFoil,
      'usd' => $usd,
      'usdFoil' => NULL,
    ];
  }

  /**
   * Sample collection.
   *
   * @return array<int, array<string, mixed>>
   *   Rows.
   */
  private static function rows(): array {
    return [
      self::row(1, 'Mox Diamond', 'sth', 'rare', 2, 0, 800.0),
      self::row(2, 'Sol Ring', 'c14', 'uncommon', 3, 1, 2.0, 10.0),
      self::row(3, 'Forest', 'thb', 'common', 10, 0, 0.1),
      self::row(4, 'Odd Promo', 'pxyz', 'special', 1, 0, NULL, NULL, 0, 4.0),
      self::row(5, 'Unpriced', 'zzz', 'common', 2, 0, NULL),
    ];
  }

  /**
   * Totals, rarities and price fallbacks.
   */
  public function testTotalsAndRarities(): void {
    $stats = CollectionStatsCalculator::compute(self::rows(), [], ['sth' => 350], TRUE, 0.5, TRUE, 1.0);
    $totals = $stats['totals'];
    // 1600 + 6 + 10 (foil Sol Ring) + 1 (Forests) + 2 (USD 4 * 0.5).
    $this->assertSame(1619.0, $totals['value']);
    $this->assertSame(19, $totals['copies']);
    $this->assertSame(1, $totals['foil']);
    $this->assertSame(5, $totals['printings']);
    $this->assertSame(2, $totals['unpricedCopies']);
    $this->assertSame(['rare', 'uncommon', 'common', 'special'], array_column($stats['rarities'], 'rarity'));
    $this->assertSame('sth', $stats['sets'][0]['setCode']);
    $this->assertSame(1600.0, $stats['sets'][0]['value']);
    $this->assertSame(2, $stats['sets'][0]['rare']);
    $this->assertSame(350, $stats['sets'][0]['setSize']);
  }

  /**
   * Price bands, cutoff and the median.
   */
  public function testBandsCutoffAndMedian(): void {
    $stats = CollectionStatsCalculator::compute(self::rows(), [], [], TRUE, 0.5, TRUE, 2.0);
    // At or above 2: Mox x2, Sol Ring x3 (2.00), foil Sol Ring, promo (2.00).
    $this->assertSame(7, $stats['aboveCutoff']['copies']);
    $this->assertSame(12, $stats['belowCutoff']['copies']);
    $unpriced = end($stats['bands']);
    $this->assertNull($unpriced['min']);
    $this->assertSame(2, $unpriced['copies']);
    $this->assertSame(10, $stats['bands'][0]['copies']);
    // 19 copies sorted: 2 unpriced (0), 10 at 0.1, ... so copy 10 is 0.1.
    $this->assertSame(0.1, $stats['totals']['median']);
    $this->assertSame('Mox Diamond', $stats['topCards'][0]['title']);
    // Top 10 copies: Mox x2, foil Sol Ring, Sol Ring x3, promo, Forest x3.
    $this->assertSame(10, $stats['concentration'][0]['top']);
    $this->assertSame(1618.3, $stats['concentration'][0]['value']);
  }

  /**
   * Trade copies come off regular copies first, then foil.
   */
  public function testTradeExcluded(): void {
    $rows = [self::row(2, 'Sol Ring', 'c14', 'uncommon', 1, 1, 2.0, 10.0, 2)];
    $with = CollectionStatsCalculator::compute($rows, [], [], TRUE, 1.0, TRUE, 1.0);
    $without = CollectionStatsCalculator::compute($rows, [], [], TRUE, 1.0, FALSE, 1.0);
    $this->assertSame(12.0, $with['totals']['value']);
    $this->assertSame(2, $with['totals']['trade']);
    $this->assertSame(0, $without['totals']['copies']);
    $this->assertSame(0.0, $without['totals']['value']);
  }

  /**
   * Deck usage matches by name and caps at owned copies.
   */
  public function testDeckUsage(): void {
    $needs = [
      ['deck' => 'A', 'card' => 'Sol Ring', 'quantity' => 1],
      ['deck' => 'B', 'card' => 'Sol Ring', 'quantity' => 1],
      ['deck' => 'B', 'card' => 'Mox Diamond', 'quantity' => 1],
      ['deck' => 'B', 'card' => 'Black Lotus', 'quantity' => 1],
    ];
    $decks = CollectionStatsCalculator::compute(self::rows(), $needs, [], TRUE, 0.5, TRUE, 1.0)['decks'];
    $this->assertSame(3, $decks['copiesInDecks']);
    // Sol Ring average (6 + 10) / 4 = 4 per copy, twice, plus one Mox.
    $this->assertSame(808.0, $decks['valueInDecks']);
    $this->assertSame(16, $decks['copiesFree']);
    $this->assertSame('B', $decks['decks'][0]['title']);
    $this->assertSame(3, $decks['decks'][0]['needed']);
    $this->assertSame(2, $decks['decks'][0]['owned']);
  }

}
