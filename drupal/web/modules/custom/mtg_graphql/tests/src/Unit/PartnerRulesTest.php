<?php

declare(strict_types=1);

namespace Drupal\Tests\mtg_graphql\Unit;

use Drupal\mtg_graphql\PartnerRules;
use Drupal\Tests\UnitTestCase;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\Group;

/**
 * Tests the two-commander pairing rules.
 */
#[CoversClass(PartnerRules::class)]
#[Group('mtg_graphql')]
final class PartnerRulesTest extends UnitTestCase {

  /**
   * Builds a card array.
   *
   * @return array{name: string, typeLine: string, oracle: string}
   *   Card data.
   */
  private static function card(string $name, string $typeLine, string $oracle): array {
    return ['name' => $name, 'typeLine' => $typeLine, 'oracle' => $oracle];
  }

  /**
   * Plain Partner pairs with plain Partner only.
   */
  public function testPlainPartner(): void {
    $thrasios = self::card('Thrasios, Triton Hero', 'Legendary Creature — Merfolk Wizard',
      "{4}: Scry 1, then reveal the top card of your library.\nPartner (You can have two commanders if both have partner.)");
    $kraum = self::card("Kraum, Ludevic's Opus", 'Legendary Creature — Zombie Horror',
      "Flying, haste\nWhenever an opponent casts their second spell each turn, draw a card.\nPartner (You can have two commanders if both have partner.)");
    $plain = self::card('Najeela, the Blade-Blossom', 'Legendary Creature — Human Warrior', 'Whenever a Warrior attacks, ...');
    $this->assertTrue(PartnerRules::allowsPartner($thrasios['name'], $thrasios['typeLine'], $thrasios['oracle']));
    $this->assertTrue(PartnerRules::canPair($thrasios, $kraum));
    $this->assertFalse(PartnerRules::canPair($thrasios, $plain));
    $this->assertFalse(PartnerRules::allowsPartner($plain['name'], $plain['typeLine'], $plain['oracle']));
  }

  /**
   * Partner with names one card; variants and Friends forever match each other.
   */
  public function testNamedVariantAndFriends(): void {
    $pir = self::card("Pir, Imaginative Rascal", 'Legendary Creature — Human', "Partner with Toothy, Imaginary Friend (When this creature enters...)\nIf one or more counters...");
    $toothy = self::card('Toothy, Imaginary Friend', 'Legendary Creature — Illusion', "Partner with Pir, Imaginative Rascal (When this creature enters...)\nWhenever you draw a card...");
    $other = self::card('Thrasios, Triton Hero', 'Legendary Creature — Merfolk Wizard', 'Partner (You can have two commanders if both have partner.)');
    $this->assertTrue(PartnerRules::canPair($pir, $toothy));
    $this->assertFalse(PartnerRules::canPair($pir, $other));

    $v1 = self::card('A', 'Legendary Creature', "Partner—Survivors (You can have two commanders if both have this ability.)");
    $v2 = self::card('B', 'Legendary Creature', "Partner—Survivors (You can have two commanders if both have this ability.)");
    $v3 = self::card('C', 'Legendary Creature', "Partner—Father & son (You can have two commanders if both have this ability.)");
    $this->assertTrue(PartnerRules::canPair($v1, $v2));
    $this->assertFalse(PartnerRules::canPair($v1, $v3));

    $f1 = self::card('Will', 'Legendary Creature', 'Friends forever (You can have two commanders if both have friends forever.)');
    $f2 = self::card('Eleven', 'Legendary Creature', 'Friends forever (You can have two commanders if both have friends forever.)');
    $this->assertTrue(PartnerRules::canPair($f1, $f2));
  }

  /**
   * Backgrounds and Doctors pair with their counterpart, in either order.
   */
  public function testBackgroundAndDoctor(): void {
    $wilson = self::card('Wilson, Refined Grizzly', 'Legendary Creature — Bear Warrior', "Reach, trample\nChoose a Background (You can have a Background as a second commander.)");
    $bg = self::card('Raised by Giants', 'Legendary Enchantment — Background', 'Commander creatures you own have base power and toughness 10/10.');
    $this->assertTrue(PartnerRules::canPair($wilson, $bg));
    $this->assertTrue(PartnerRules::canPair($bg, $wilson));

    $doctor = self::card('The Tenth Doctor', 'Legendary Creature — Time Lord Doctor', 'Allons-y! — Whenever you cast a spell...');
    $rose = self::card('Rose Tyler', 'Legendary Creature — Human', "Doctor's companion (You can have two commanders if the other is the Doctor.)");
    $this->assertTrue(PartnerRules::allowsPartner($doctor['name'], $doctor['typeLine'], $doctor['oracle']));
    $this->assertTrue(PartnerRules::canPair($doctor, $rose));
    $this->assertFalse(PartnerRules::canPair($rose, $wilson));
  }

}
