<?php

declare(strict_types=1);

namespace Drupal\Tests\mtg_graphql\Unit;

use Drupal\mtg_graphql\StatsDetailCalculator;
use Drupal\Tests\UnitTestCase;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\Group;

/**
 * Tests the per-deck and per-set statistics.
 */
#[CoversClass(StatsDetailCalculator::class)]
#[Group('mtg_graphql')]
final class StatsDetailCalculatorTest extends UnitTestCase {

  /**
   * Owned copies fill slots in order; missing copies use the cheapest price.
   */
  public function testDeck(): void {
    $slots = [
      ['title' => 'Sol Ring', 'board' => 'main', 'quantity' => 1, 'foil' => FALSE, 'eur' => 2.0],
      ['title' => 'Forest', 'board' => 'main', 'quantity' => 3, 'foil' => FALSE, 'eur' => 0.5],
      ['title' => 'Forest', 'board' => 'side', 'quantity' => 2, 'foil' => FALSE, 'eur' => 0.5],
      ['title' => 'Mox', 'board' => 'main', 'quantity' => 1, 'foil' => TRUE, 'eur' => 100.0, 'eurFoil' => 300.0],
      ['title' => 'Promo', 'board' => 'side', 'quantity' => 1, 'foil' => FALSE],
    ];
    $owned = ['Sol Ring' => 4, 'Forest' => 4];
    $cheapest = ['Mox' => ['eur' => 80.0]];
    $stats = StatsDetailCalculator::deck($slots, $owned, $cheapest, ['Sol Ring' => 2], TRUE, 1.0);
    $cards = $stats['cards'];

    $this->assertSame('owned', $cards[0]['status']);
    $this->assertSame(2, $cards[0]['otherDecks']);
    // Four Forests: three in the main deck, one of the two in the sideboard.
    $this->assertSame(3, $cards[1]['covered']);
    $this->assertSame(1, $cards[2]['covered']);
    $this->assertSame('partial', $cards[2]['status']);
    // The foil Mox is valued foil but completed at the cheapest printing.
    $this->assertSame(300.0, $cards[3]['unitPrice']);
    $this->assertSame(80.0, $cards[3]['costToComplete']);
    $this->assertSame('missing', $cards[3]['status']);

    $totals = $stats['totals'];
    $this->assertSame(8, $totals['cards']);
    $this->assertSame(5, $totals['ownedCopies']);
    $this->assertSame(3, $totals['missingCopies']);
    // 2 + 1.5 + 1 + 300.
    $this->assertSame(304.5, $totals['value']);
    $this->assertSame(4.0, $totals['ownedValue']);
    // One Forest at 0.5 and the Mox at 80; the promo has no price.
    $this->assertSame(80.5, $totals['costToComplete']);
    $this->assertSame(1, $totals['unpricedMissing']);
    $this->assertSame(1, $totals['sharedCards']);
  }

  /**
   * Printings are sorted naturally and completion is counted per rarity.
   */
  public function testSet(): void {
    $printings = [
      ['title' => 'B', 'collectorNumber' => '10', 'rarity' => 'common', 'regular' => 0, 'foil' => 0, 'eur' => 0.2],
      [
        'title' => 'A',
        'collectorNumber' => '2',
        'rarity' => 'rare',
        'regular' => 1,
        'foil' => 1,
        'eur' => 5.0,
        'eurFoil' => 9.0,
      ],
      ['title' => 'C', 'collectorNumber' => '3', 'rarity' => 'mythic', 'regular' => 0, 'foil' => 0],
    ];
    $stats = StatsDetailCalculator::set($printings, TRUE, 1.0);

    $this->assertSame(['2', '3', '10'], array_column($stats['cards'], 'collectorNumber'));
    $this->assertSame(3, $stats['totals']['printings']);
    $this->assertSame(1, $stats['totals']['ownedPrintings']);
    $this->assertSame(14.0, $stats['totals']['value']);
    $this->assertSame(0.2, $stats['totals']['costToComplete']);
    $this->assertSame(1, $stats['totals']['unpricedMissing']);
    $this->assertSame(['mythic', 'rare', 'common'], array_column($stats['rarities'], 'rarity'));
    $this->assertSame(1, $stats['rarities'][1]['owned']);
  }

}
