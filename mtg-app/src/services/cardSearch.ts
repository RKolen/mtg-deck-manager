/**
 * Solr-backed card search via GraphQL Compose extension (cardSearch query).
 */

import { gql } from 'graphql-request';
import type { JsonApiResource, MtgCardAttributes } from '../types/drupal';
import { gqlCardToResource } from './drupalApi';
import { getGraphQLClient } from './graphqlClient';

export interface CardSearchParams {
  q?: string;
  type?: string;
  oracleText?: string;
  legalIn?: string;
  cmcMin?: number;
  cmcMax?: number;
  colors?: string[];
  colorIdentity?: string[];
  manaProducer?: boolean;
  rarity?: string;
  page?: number;
  limit?: number;
}

export interface CardSearchResult {
  data: JsonApiResource<MtgCardAttributes>[];
  meta: {
    count: number;
    pages: number;
  };
}

interface GqlSearchCard {
  id: string;
  title: string;
  manaCost: string | null;
  cmc: number | null;
  typeLine: string | null;
  colors: string[];
  colorIdentity: string[];
  oracleText: string | null;
  imageUri: string | null;
  isManaProducer: boolean;
  producedMana: string[];
  legalFormats: string[];
  priceUsd: string | null;
  priceUsdFoil: string | null;
  setCode: string | null;
  setName: string | null;
  rarity: string | null;
  collectorNumber: string | null;
  power: string | null;
  toughness: string | null;
  loyalty: string | null;
}

const SEARCH_CARD_FIELDS = gql`
  fragment SearchCardFields on MtgCard {
    id title manaCost cmc typeLine colors colorIdentity
    oracleText imageUri isManaProducer producedMana legalFormats
    priceUsd priceUsdFoil setCode setName rarity collectorNumber
    power toughness loyalty
  }
`;

export async function searchCards(params: CardSearchParams): Promise<CardSearchResult> {
  const query = gql`
    ${SEARCH_CARD_FIELDS}
    query CardSearch(
      $q: String, $type: String, $oracleText: String, $legalIn: String,
      $cmcMin: Float, $cmcMax: Float, $colors: [String!], $colorIdentity: [String!],
      $manaProducer: Boolean, $rarity: String, $page: Int, $limit: Int
    ) {
      cardSearch(
        q: $q, type: $type, oracleText: $oracleText, legalIn: $legalIn,
        cmcMin: $cmcMin, cmcMax: $cmcMax, colors: $colors, colorIdentity: $colorIdentity,
        manaProducer: $manaProducer, rarity: $rarity, page: $page, limit: $limit
      ) {
        count
        pages
        cards { ...SearchCardFields }
      }
    }
  `;

  const data = await getGraphQLClient().request<{
    cardSearch: { cards: GqlSearchCard[]; count: number; pages: number };
  }>(query, {
    q: params.q || null,
    type: params.type || null,
    oracleText: params.oracleText || null,
    legalIn: params.legalIn || null,
    cmcMin: params.cmcMin ?? null,
    cmcMax: params.cmcMax ?? null,
    colors: params.colors?.length ? params.colors : null,
    colorIdentity: params.colorIdentity?.length ? params.colorIdentity : null,
    manaProducer: params.manaProducer ?? null,
    rarity: params.rarity || null,
    page: params.page ?? 0,
    limit: params.limit ?? 20,
  });

  return {
    data: data.cardSearch.cards.map(gqlCardToResource),
    meta: {
      count: data.cardSearch.count,
      pages: data.cardSearch.pages,
    },
  };
}
