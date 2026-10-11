/**
 * Collection binder page — Phase 7.
 *
 * Card catalogue is fetched at runtime via Solr-backed search endpoint with
 * debounced filters. Collection quantities (owned/foil) are fetched at
 * runtime via GraphQL and managed through @tanstack/react-query.
 */

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { slugify } from '../../utils/slugify';

import CardFilter, { EMPTY_FILTER, type FilterState } from '../../components/CardFilter';
import CardModal, { type CardData } from '../../components/CardModal';
import CollectionSidebar from '../../components/CollectionSidebar';
import TradeList from '../../components/TradeList';
import PriceTicker from '../../components/PriceTicker';
import TopCollectionCards from '../../components/TopCollectionCards';
import { searchCards } from '../../services/cardSearch';
import {
  fetchCollectionCards,
  fetchCollectionValue,
  upsertCollectionCard,
} from '../../services/drupalApi';
import { invalidateInventoryQueries, patchCollectionRow } from '../../services/queryCache';
import { useTheme } from '../../context/ThemeContext';
import { tradeValue } from '../../utils/prices';
import type { CollectionCard, JsonApiResource, MtgCardAttributes } from '../../types/drupal';

type CardResource = JsonApiResource<MtgCardAttributes>;

/** all: every card; tokens: the token box; trade: the trade binder. */
type CollectionView = 'all' | 'tokens' | 'trade';

const VIEWS: Array<{ id: CollectionView; label: string }> = [
  { id: 'all', label: 'All cards' },
  { id: 'tokens', label: 'Tokens' },
  { id: 'trade', label: 'For trade' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CollectionPage: React.FC = () => {
  const { currency, usdToEur } = useTheme();

  const [filter, setFilter] = useState<FilterState>({
    ...EMPTY_FILTER,
    colors: new Set(),
  });
  const [modalCard, setModalCard] = useState<CardResource | null>(null);
  const [view, setView] = useState<CollectionView>('all');

  // Debounced filter for API calls — avoids a request on every keystroke.
  const [debouncedFilter, setDebouncedFilter] = useState(filter);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleFilterChange = useCallback((f: FilterState) => {
    setFilter(f);
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedFilter(f), 400);
  }, []);

  const qc = useQueryClient();

  // Fetch card catalogue page — refetches when debounced filter changes.
  const [page, setPage] = useState(0);

  const setsKey = debouncedFilter.setCodes.slice().sort().join(',');
  const decksKey = debouncedFilter.deckIds.slice().sort().join(',');
  const filterKey = JSON.stringify({
    name: debouncedFilter.name,
    colors: [...debouncedFilter.colors].sort(),
    type: debouncedFilter.type,
    maxCmc: debouncedFilter.maxCmc,
    legalIn: debouncedFilter.legalIn,
    oracleText: debouncedFilter.oracleText,
    rarity: debouncedFilter.rarity,
    setCodes: debouncedFilter.setCodes.slice().sort(),
    setExclude: debouncedFilter.setExclude,
    deckIds: debouncedFilter.deckIds.slice().sort(),
    deckExclude: debouncedFilter.deckExclude,
    tokens: view === 'tokens',
    page,
  });
  const {
    data: searchResult,
    isLoading: cardsLoading,
  } = useQuery({
    queryKey: ['cards', filterKey],
    queryFn: () =>
      searchCards({
        q: debouncedFilter.name || undefined,
        colors: debouncedFilter.colors.size > 0 ? [...debouncedFilter.colors] : undefined,
        type: debouncedFilter.type !== 'All' ? debouncedFilter.type : undefined,
        cmcMax: debouncedFilter.maxCmc ?? undefined,
        legalIn: debouncedFilter.legalIn || undefined,
        oracleText: debouncedFilter.oracleText || undefined,
        rarity: debouncedFilter.rarity || undefined,
        setCodes: debouncedFilter.setCodes.length ? debouncedFilter.setCodes : undefined,
        setExclude: debouncedFilter.setExclude,
        deckIds: debouncedFilter.deckIds.length ? debouncedFilter.deckIds : undefined,
        deckExclude: debouncedFilter.deckExclude,
        tokensOnly: view === 'tokens',
        page,
        limit: 50,
      }),
    enabled: view !== 'trade',
  });

  const colorsKey = useMemo(
    () => [...debouncedFilter.colors].sort().join(','),
    [debouncedFilter.colors],
  );

  // Reset to first page when filters change.
  useEffect(() => {
    setPage(0);
  }, [
    debouncedFilter.name,
    debouncedFilter.type,
    debouncedFilter.maxCmc,
    debouncedFilter.legalIn,
    debouncedFilter.oracleText,
    debouncedFilter.rarity,
    debouncedFilter.setExclude,
    debouncedFilter.deckExclude,
    colorsKey,
    setsKey,
    decksKey,
    view,
  ]);

  const { data: estValue = null } = useQuery<number>({
    queryKey: ['collectionValue', currency],
    queryFn: () => fetchCollectionValue(currency),
    staleTime: 5 * 60 * 1000,
  });

  const cards = searchResult?.data ?? [];
  const totalPages = searchResult?.meta.pages ?? 1;

  // Fetch all collection_card nodes at runtime.
  const { data: collectionCards = [], isLoading: collectionLoading } = useQuery<CollectionCard[]>({
    queryKey: ['collectionCards'],
    queryFn: fetchCollectionCards,
  });

  const isLoading = cardsLoading || collectionLoading;

  // Build a map: mtg_card UUID → collection_card resource.
  const collectionMap = useMemo(() => {
    const map = new Map<string, CollectionCard>();
    for (const cc of collectionCards) {
      const ref = cc.relationships?.field_card?.data;
      if (ref != null && !Array.isArray(ref) && ref.id) {
        map.set(ref.id, cc);
      }
    }
    return map;
  }, [collectionCards]);

  // Upsert mutation: creates or updates a collection_card node.
  const upsert = useMutation({
    mutationFn: ({
      cardId,
      cardName,
      owned,
      foil,
      existingId,
      trade,
    }: {
      cardId: string;
      cardName: string;
      owned: number;
      foil: number;
      existingId?: string;
      trade?: { quantityTrade?: number; binderLocation?: string };
    }) => upsertCollectionCard(cardId, cardName, owned, foil, existingId, trade),
    // Show the new count at once; only this row changes in the cached list.
    onMutate: async ({ cardId, owned, foil, trade }) => {
      await qc.cancelQueries({ queryKey: ['collectionCards'] });
      const prev = qc.getQueryData<CollectionCard[]>(['collectionCards']);
      patchCollectionRow(qc, {
        cardId,
        quantityOwned: owned,
        quantityFoil: foil,
        quantityTrade: trade?.quantityTrade,
        binderLocation: trade?.binderLocation,
      });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev != null) {
        qc.setQueryData(['collectionCards'], ctx.prev);
      }
    },
    onSuccess: (saved, { cardId, owned, foil, trade }) => {
      // A first copy has no cached row yet, so the list refetches once.
      const patched = patchCollectionRow(qc, {
        cardId,
        id: saved.id,
        quantityOwned: owned,
        quantityFoil: foil,
        quantityTrade: trade?.quantityTrade,
        binderLocation: trade?.binderLocation,
      });
      void invalidateInventoryQueries(qc, { keepCollectionList: patched });
    },
  });

  function setQuantities(card: CardResource, owned: number, foil: number): void {
    const cardId = card.id;
    if (cardId == null) return;
    const existing = collectionMap.get(cardId);
    upsert.mutate({
      cardId,
      cardName: card.attributes.title,
      owned: Math.max(0, owned),
      foil: Math.max(0, foil),
      existingId: existing?.id,
    });
  }

  /** Sets the trade count (capped at copies owned) and binder location. */
  function setTrade(
    cardId: string,
    cardName: string,
    row: CollectionCard,
    quantityTrade: number,
    binderLocation?: string,
  ): void {
    const owned = row.attributes.field_quantity_owned ?? 0;
    const foil = row.attributes.field_quantity_foil ?? 0;
    upsert.mutate({
      cardId,
      cardName,
      owned,
      foil,
      existingId: row.id,
      trade: {
        quantityTrade: Math.max(0, Math.min(quantityTrade, owned + foil)),
        binderLocation,
      },
    });
  }

  function handleQuantityChange(
    card: CardResource,
    delta: number,
    field: 'owned' | 'foil',
  ): void {
    const existing = collectionMap.get(card.id ?? '');
    const owned = existing?.attributes.field_quantity_owned ?? 0;
    const foil = existing?.attributes.field_quantity_foil ?? 0;
    setQuantities(
      card,
      field === 'owned' ? owned + delta : owned,
      field === 'foil' ? foil + delta : foil,
    );
  }

  // All filtering is done server-side by Solr; cards is the current page result.
  const filteredCards = cards;

  // Collection summary stats.
  const { totalCards, totalUnique, totalFoil } = useMemo(() => {
    let tc = 0;
    let tu = 0;
    let tf = 0;
    for (const cc of collectionCards) {
      const owned = cc.attributes.field_quantity_owned ?? 0;
      const foil = cc.attributes.field_quantity_foil ?? 0;
      if (owned > 0 || foil > 0) {
        tc += owned + foil;
        tu += 1;
        tf += foil;
      }
    }
    return { totalCards: tc, totalUnique: tu, totalFoil: tf };
  }, [collectionCards]);

  const { tradeCopies, tradeTotal } = useMemo(() => {
    let copies = 0;
    let value = 0;
    for (const cc of collectionCards) {
      const trade = cc.attributes.field_quantity_trade ?? 0;
      if (trade > 0) {
        copies += trade;
        value += tradeValue(cc.attributes, currency, usdToEur);
      }
    }
    return { tradeCopies: copies, tradeTotal: value };
  }, [collectionCards, currency, usdToEur]);

  const filteredCopies = useMemo(
    () =>
      filteredCards.reduce((sum, card) => {
        const cc = collectionMap.get(card.id ?? '');
        return (
          sum +
          (cc?.attributes.field_quantity_owned ?? 0) +
          (cc?.attributes.field_quantity_foil ?? 0)
        );
      }, 0),
    [filteredCards, collectionMap],
  );

  const modalEntry =
    modalCard != null
      ? collectionMap.get(modalCard.id ?? '')
      : undefined;

  return (
    <main style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
      <CardFilter filter={filter} onChange={handleFilterChange} />

      <div style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
        <h1 style={{ marginTop: 0 }}>
          Collection
          {isLoading && (
            <span style={{ fontSize: '0.75rem', marginLeft: 8, color: 'var(--ink)' }}>
              loading...
            </span>
          )}
        </h1>

        <div role="tablist" aria-label="Collection view" style={{ display: 'flex', gap: 6, marginBottom: '0.75rem' }}>
          {VIEWS.map(v => (
            <button
              key={v.id}
              type="button"
              role="tab"
              aria-selected={view === v.id}
              onClick={() => setView(v.id)}
              style={{
                padding: '0.25rem 0.75rem',
                fontWeight: view === v.id ? 700 : 400,
                borderBottom: view === v.id ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              {v.label}
              {v.id === 'trade' && tradeCopies > 0 ? ` (${tradeCopies})` : ''}
            </button>
          ))}
        </div>

        {view === 'trade' && (
          <TradeList
            rows={collectionCards}
            currency={currency}
            onChange={(row, quantityTrade, binderLocation) => {
              const cardId = row.relationships?.field_card?.data;
              if (cardId == null || Array.isArray(cardId)) return;
              setTrade(cardId.id, row.attributes.field_card_title ?? '', row, quantityTrade, binderLocation);
            }}
          />
        )}

        {view !== 'trade' && !cardsLoading && cards.length === 0 && (
          <p>
            No cards found. Try adjusting your filters or run{' '}
            <code>ddev drush mtg-scryfall:sync</code> to import cards from
            Scryfall.
          </p>
        )}

        <div
          style={{
            display: view === 'trade' ? 'none' : 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: '0.75rem',
          }}
        >
          {filteredCards.map(card => {
            const cc = collectionMap.get(card.id ?? '');
            const owned = cc?.attributes.field_quantity_owned ?? 0;
            const foil = cc?.attributes.field_quantity_foil ?? 0;
            const title = card.attributes.title ?? '';
            const imageUri = card.attributes.field_image_uri;

            const inCollection = owned > 0 || foil > 0;
            return (
              <div
                key={card.id}
                style={{
                  border: `1px solid ${inCollection ? 'var(--accent)' : 'var(--line)'}`,
                  borderRadius: 4,
                  overflow: 'hidden',
                  background: 'var(--bg-2)',
                  color: 'var(--ink)',
                }}
              >
                {imageUri != null ? (
                  <img
                    src={imageUri}
                    alt={title}
                    style={{ width: '100%', display: 'block', cursor: 'pointer' }}
                    onClick={() => setModalCard(card)}
                  />
                ) : (
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => setModalCard(card)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') setModalCard(card);
                    }}
                    style={{
                      height: 220,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'var(--bg-3)',
                      color: 'var(--ink)',
                      cursor: 'pointer',
                      padding: '0.5rem',
                      textAlign: 'center',
                      fontSize: '0.8rem',
                    }}
                  >
                    {title}
                  </div>
                )}

                <div
                  style={{
                    padding: '0.5rem',
                    fontSize: '0.75rem',
                    color: 'var(--ink)',
                    background: 'var(--bg-2)',
                  }}
                >
                  <div
                    style={{
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginBottom: 4,
                      fontWeight: inCollection ? 700 : 400,
                    }}
                    title={title}
                  >
                    <Link
                      href={`/collection/card/${slugify(title)}`}
                      style={{ color: 'var(--ink)', textDecoration: 'none' }}
                    >
                      {title}
                    </Link>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--ink)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 36, fontSize: 10, opacity: 0.85 }}>Reg</span>
                      <button
                        type="button"
                        onClick={() => handleQuantityChange(card, -1, 'owned')}
                        disabled={owned === 0}
                        style={{ width: 24, padding: 0 }}
                      >
                        -
                      </button>
                      <input
                        type="number"
                        min={0}
                        value={owned}
                        title="Non-foil copies"
                        onChange={e => {
                          const n = Math.max(0, Number.parseInt(e.target.value, 10) || 0);
                          setQuantities(card, n, foil);
                        }}
                        style={{
                          width: 40,
                          textAlign: 'center',
                          padding: '2px 4px',
                          color: '#000',
                          background: '#fff',
                          border: '1px solid #000',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => handleQuantityChange(card, 1, 'owned')}
                        style={{ width: 24, padding: 0 }}
                      >
                        +
                      </button>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 36, fontSize: 10, opacity: 0.85 }}>Foil</span>
                      <button
                        type="button"
                        onClick={() => handleQuantityChange(card, -1, 'foil')}
                        disabled={foil === 0}
                        style={{ width: 24, padding: 0 }}
                      >
                        -
                      </button>
                      <input
                        type="number"
                        min={0}
                        value={foil}
                        title="Foil copies"
                        onChange={e => {
                          const n = Math.max(0, Number.parseInt(e.target.value, 10) || 0);
                          setQuantities(card, owned, n);
                        }}
                        style={{
                          width: 40,
                          textAlign: 'center',
                          padding: '2px 4px',
                          color: '#000',
                          background: '#fff',
                          border: '1px solid #000',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => handleQuantityChange(card, 1, 'foil')}
                        style={{ width: 24, padding: 0 }}
                      >
                        +
                      </button>
                    </div>
                    {cc != null && (owned > 0 || foil > 0) && (() => {
                      const trade = cc.attributes.field_quantity_trade ?? 0;
                      return (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ width: 36, fontSize: 10, opacity: 0.85 }}>Trade</span>
                          <button
                            type="button"
                            onClick={() => setTrade(card.id, title, cc, trade - 1)}
                            disabled={trade === 0}
                            style={{ width: 24, padding: 0 }}
                            title="Fewer copies for trade"
                          >
                            -
                          </button>
                          <span style={{ width: 40, textAlign: 'center' }}>{trade}</span>
                          <button
                            type="button"
                            onClick={() => setTrade(card.id, title, cc, trade + 1)}
                            disabled={trade >= owned + foil}
                            style={{ width: 24, padding: 0 }}
                            title="More copies for trade"
                          >
                            +
                          </button>
                        </div>
                      );
                    })()}
                    {(owned > 0 || foil > 0) && (
                      <div style={{ fontSize: 10, opacity: 0.85 }}>
                        Total {owned + foil}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {view !== 'trade' && totalPages > 1 && (
          <div style={{ textAlign: 'center', padding: '1rem', display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center' }}>
            <button
              type="button"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              style={{ padding: '0.5rem 1rem' }}
            >
              Previous
            </button>
            <span>Page {page + 1} of {totalPages}</span>
            <button
              type="button"
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              style={{ padding: '0.5rem 1rem' }}
            >
              Next
            </button>
          </div>
        )}
      </div>

      <div style={{ padding: '1rem', borderLeft: '1px solid var(--line)', overflowY: 'auto', maxWidth: 280 }}>
        <CollectionSidebar
          totalCards={totalCards}
          totalUnique={totalUnique}
          totalFoil={totalFoil}
          filtered={filteredCopies}
          filteredUnique={filteredCards.length}
          estValue={estValue}
          currency={currency}
          tradeCopies={tradeCopies}
          tradeValue={tradeTotal}
        />
        <TopCollectionCards rows={collectionCards} currency={currency} usdToEur={usdToEur} />
      </div>
      </div>

      <PriceTicker currency={currency} />

      {modalCard != null && (
        <CardModal
          card={{
            id: modalCard.id,
            title: modalCard.attributes.title ?? null,
            field_mana_cost: modalCard.attributes.field_mana_cost ?? null,
            field_cmc: modalCard.attributes.field_cmc ?? null,
            field_type_line: modalCard.attributes.field_type_line ?? null,
            field_colors: modalCard.attributes.field_colors ?? null,
            field_color_identity: modalCard.attributes.field_color_identity ?? null,
            field_oracle_text: modalCard.attributes.field_oracle_text ?? null,
            field_scryfall_id: modalCard.attributes.field_scryfall_id ?? null,
            field_image_uri: modalCard.attributes.field_image_uri ?? null,
            field_is_mana_producer: modalCard.attributes.field_is_mana_producer ?? null,
            field_produced_mana: modalCard.attributes.field_produced_mana ?? null,
            field_legal_formats: modalCard.attributes.field_legal_formats ?? null,
            field_price_usd: modalCard.attributes.field_price_usd ?? null,
            field_price_usd_foil: modalCard.attributes.field_price_usd_foil ?? null,
            field_price_eur: modalCard.attributes.field_price_eur ?? null,
            field_price_eur_foil: modalCard.attributes.field_price_eur_foil ?? null,
            field_set_name: modalCard.attributes.field_set_name ?? null,
            field_rarity: modalCard.attributes.field_rarity ?? null,
          } as CardData}
          quantityOwned={modalEntry?.attributes.field_quantity_owned}
          quantityFoil={modalEntry?.attributes.field_quantity_foil}
          onQuantityChange={(owned, foil) => setQuantities(modalCard, owned, foil)}
          onClose={() => setModalCard(null)}
        />
      )}
    </main>
  );
};

export default CollectionPage;
