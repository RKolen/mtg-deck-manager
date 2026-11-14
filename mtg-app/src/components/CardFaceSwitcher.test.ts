import { describe, expect, it } from 'vitest';
import type { CardFace } from '../services/drupalApi';
import { faceImageRotation, faceImageUri } from './CardFaceSwitcher';

const face = (name: string, layout: string): CardFace => ({
  name,
  manaCost: '',
  typeLine: '',
  oracleText: '',
  power: null,
  toughness: null,
  loyalty: null,
  layout,
});

const FRONT = 'https://cards.scryfall.io/normal/front/6/1/619e0c3a.jpg?1664414000';

describe('faceImageUri', () => {
  it('uses the back image for the back face of a double-faced card', () => {
    const faces = [face('Ratchet, Field Medic', 'transform'), face('Ratchet, Rescue Racer', 'transform')];
    expect(faceImageUri(FRONT, faces, 0)).toBe(FRONT);
    expect(faceImageUri(FRONT, faces, 1)).toBe('https://cards.scryfall.io/normal/back/6/1/619e0c3a.jpg?1664414000');
  });

  it('keeps the single image for adventure, split and flip cards', () => {
    for (const layout of ['adventure', 'split', 'flip', 'prepare']) {
      expect(faceImageUri(FRONT, [face('A', layout), face('B', layout)], 1)).toBe(FRONT);
    }
  });

  it('keeps the image when there are no faces', () => {
    expect(faceImageUri(FRONT, [], 0)).toBe(FRONT);
  });
});

describe('faceImageRotation', () => {
  it('turns the image upside down only for the flipped half of a flip card', () => {
    const flip = [face('Akki Lavarunner', 'flip'), face('Tok-Tok, Volcano Born', 'flip')];
    expect(faceImageRotation(flip, 0)).toBeUndefined();
    expect(faceImageRotation(flip, 1)).toBe('rotate(180deg)');
    expect(faceImageRotation([face('A', 'transform'), face('B', 'transform')], 1)).toBeUndefined();
  });
});
