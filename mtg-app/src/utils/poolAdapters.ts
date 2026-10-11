/**
 * Maps deck build pool cards (GraphQL) to the inputs of the land base
 * planner and the deck generator.
 */

import { poolCardAvailable } from '../services/drupalApi';
import type { MtgCardAttributes, PoolCard } from '../types/drupal';
import { getOracleText } from './deckAnalysis';
import type { GenCard } from './deckGenerator';
import type { LandInfo, LandOption } from './landBase';

export function toLandInfo(a: MtgCardAttributes): LandInfo {
  return {
    title: a.title,
    typeLine: a.field_type_line ?? '',
    oracleText: getOracleText(a),
    producedMana: a.field_produced_mana ?? [],
  };
}

/**
 * A pool land as a planner option.
 *
 * @param unlimited - True for the cardbase: any number may be suggested;
 *   copies beyond the free ones are reported as missing.
 */
export function toLandOption(
  p: PoolCard,
  includeUsed: boolean,
  unlimited: boolean,
  price: number | null,
): LandOption {
  const free = poolCardAvailable(p, includeUsed);
  return {
    land: toLandInfo(p.card.attributes),
    cardId: p.card.id,
    available: unlimited ? Infinity : free,
    free,
    owned: Math.max(0, p.owned - p.trade),
    usedIn: p.usedIn.map(u => u.deckTitle),
    price,
  };
}

export function toGenCard(p: PoolCard, includeUsed: boolean): GenCard {
  const a = p.card.attributes;
  return {
    id: p.card.id,
    title: a.title,
    typeLine: a.field_type_line ?? '',
    oracleText: getOracleText(a),
    cmc: a.field_cmc ?? 0,
    isManaProducer: a.field_is_mana_producer === true,
    power: a.field_power ?? null,
    manaCost: a.field_mana_cost ?? '',
    colorIdentity: a.field_color_identity ?? [],
    available: poolCardAvailable(p, includeUsed),
    producedMana: a.field_produced_mana ?? [],
    playedIn: p.usedIn.length,
  };
}
