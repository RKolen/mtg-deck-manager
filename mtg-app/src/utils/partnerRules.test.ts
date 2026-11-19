import { describe, expect, it } from 'vitest';
import { allowsPartner, canPair, partnerLabel, type PairCard } from './partnerRules';

const card = (title: string, typeLine: string, oracleText: string): PairCard => ({ title, typeLine, oracleText });

const PARTNER = 'Partner (You can have two commanders if both have partner.)';
const thrasios = card('Thrasios, Triton Hero', 'Legendary Creature — Merfolk Wizard', `{4}: Scry 1.\n${PARTNER}`);
const kraum = card("Kraum, Ludevic's Opus", 'Legendary Creature — Zombie Horror', `Flying, haste\n${PARTNER}`);
const najeela = card('Najeela, the Blade-Blossom', 'Legendary Creature — Human Warrior', 'Whenever a Warrior attacks...');

describe('partner rules', () => {
  it('pairs plain partners and nothing else', () => {
    expect(allowsPartner(thrasios)).toBe(true);
    expect(canPair(thrasios, kraum)).toBe(true);
    expect(canPair(thrasios, najeela)).toBe(false);
    expect(canPair(thrasios, thrasios)).toBe(false);
    expect(allowsPartner(najeela)).toBe(false);
  });

  it('pairs Partner with only with the named card', () => {
    const pir = card('Pir, Imaginative Rascal', 'Legendary Creature — Human', 'Partner with Toothy, Imaginary Friend (When this...)');
    const toothy = card('Toothy, Imaginary Friend', 'Legendary Creature — Illusion', 'Partner with Pir, Imaginative Rascal (When this...)');
    expect(canPair(pir, toothy)).toBe(true);
    expect(canPair(pir, kraum)).toBe(false);
    expect(partnerLabel(pir)).toBe('Partner (Toothy, Imaginary Friend)');
  });

  it('pairs matching Partner variants and Friends forever', () => {
    const a = card('A', 'Legendary Creature', 'Partner—Survivors (You can have two commanders...)');
    const b = card('B', 'Legendary Creature', 'Partner—Survivors (You can have two commanders...)');
    const c = card('C', 'Legendary Creature', 'Partner—Father & son (You can have two commanders...)');
    expect(canPair(a, b)).toBe(true);
    expect(canPair(a, c)).toBe(false);
    const f = card('F', 'Legendary Creature', 'Friends forever (You can have two commanders...)');
    const g = card('G', 'Legendary Creature', 'Friends forever (You can have two commanders...)');
    expect(canPair(f, g)).toBe(true);
  });

  it('pairs Backgrounds and Doctors either way round', () => {
    const wilson = card('Wilson, Refined Grizzly', 'Legendary Creature — Bear Warrior', 'Reach\nChoose a Background (You can have...)');
    const bg = card('Raised by Giants', 'Legendary Enchantment — Background', 'Commander creatures you own have base power 10/10.');
    expect(canPair(wilson, bg)).toBe(true);
    expect(canPair(bg, wilson)).toBe(true);
    expect(partnerLabel(wilson)).toBe('Background');
    const doctor = card('The Tenth Doctor', 'Legendary Creature — Time Lord Doctor', 'Allons-y!');
    const rose = card('Rose Tyler', 'Legendary Creature — Human', "Doctor's companion (You can have two commanders...)");
    expect(allowsPartner(doctor)).toBe(true);
    expect(canPair(doctor, rose)).toBe(true);
    expect(canPair(rose, wilson)).toBe(false);
  });
});
