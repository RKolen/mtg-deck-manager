<?php

declare(strict_types=1);

namespace Drupal\Tests\mtg_scryfall_sync\Unit;

use Drupal\mtg_scryfall_sync\Service\CardFaces;
use Drupal\Tests\UnitTestCase;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\Group;

/**
 * Tests which Scryfall cards yield face rows.
 */
#[CoversClass(CardFaces::class)]
#[Group('mtg_scryfall_sync')]
final class CardFacesTest extends UnitTestCase {

  /**
   * A transform card keeps both faces, front first, with stats and layout.
   */
  public function testTransformCardKeepsBothFaces(): void {
    $faces = CardFaces::fromCard([
      'name' => 'Ratchet, Field Medic // Ratchet, Rescue Racer',
      'layout' => 'transform',
      'card_faces' => [
        [
          'name' => 'Ratchet, Field Medic',
          'mana_cost' => '{2}{W}',
          'type_line' => 'Legendary Artifact Creature — Robot',
          'oracle_text' => "Lifelink\nWhenever you gain life, you may convert Ratchet.",
          'power' => '2',
          'toughness' => '4',
        ],
        [
          'name' => 'Ratchet, Rescue Racer',
          'mana_cost' => '',
          'type_line' => 'Legendary Artifact — Vehicle',
          'oracle_text' => 'Living metal',
          'power' => '1',
          'toughness' => '4',
        ],
      ],
    ]);

    $this->assertCount(2, $faces);
    $this->assertSame(0, $faces[0]['face_index']);
    $this->assertSame('Ratchet, Field Medic', $faces[0]['name']);
    $this->assertSame(1, $faces[1]['face_index']);
    $this->assertSame('Legendary Artifact — Vehicle', $faces[1]['type_line']);
    $this->assertSame('1', $faces[1]['power']);
    $this->assertSame('', $faces[1]['loyalty']);
    $this->assertSame('transform', $faces[1]['layout']);
  }

  /**
   * Single-faced, token, reversible and art series cards yield no faces.
   */
  public function testCardsWithoutRulesFacesAreSkipped(): void {
    $twoFaces = [['name' => 'A', 'oracle_text' => 'x'], ['name' => 'B', 'oracle_text' => 'y']];

    $this->assertSame([], CardFaces::fromCard(['name' => 'Sol Ring', 'layout' => 'normal']));
    foreach (['double_faced_token', 'reversible_card', 'art_series'] as $layout) {
      $this->assertSame([], CardFaces::fromCard([
        'name' => 'A // B',
        'layout' => $layout,
        'card_faces' => $twoFaces,
      ]), $layout);
    }
    $this->assertSame([], CardFaces::fromCard([
      'name' => 'A',
      'layout' => 'transform',
      'card_faces' => [['name' => 'A']],
    ]));
  }

}
