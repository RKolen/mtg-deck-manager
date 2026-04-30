/**
 * Collection binder page — Phase 3.
 *
 * Card catalogue is fetched at runtime via JSON:API with debounced filters.
 * Switched from build-time gatsby-source-drupal (too slow for 108k cards —
 * will be replaced by Solr search in Phase 7).
 * Collection quantities (owned/foil) are fetched at runtime via JSON:API and
 * managed through @tanstack/react-query.
 */

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import CardFilter, { type FilterState } from '../../components/CardFilter';
import CardModal, { type CardData } from '../../components/CardModal';
import CollectionSidebar from '../../components/CollectionSidebar';
import {
  fetchCardsPage,
  fetchCollectionCards,
  upsertCollectionCard,
} from '../../services/drupalApi';
import { classifyType } from '../../utils/deckAnalysis';
import type { CollectionCard, JsonApiResource, MtgCardAttributes } from '../../types/drupal';

type CardResource = JsonApiResource<MtgCardAttributes>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CollectionPage: React.FC = () => {

  const [filter, setFilter] = useState<FilterState>({
    name: '',
    colors: new Set(),
    type: 'All',
    maxCmc: null,
  });
  const [modalCard, setModalCard] = useState<CardResource | null>(null);

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
  const filterKey = JSON.stringify({
    name: debouncedFilter.name,
    colors: [...debouncedFilter.colors].sort(),
    type: debouncedFilter.type,
    maxCmc: debouncedFilter.maxCmc,
  });
  const {
    data: cardPage,
    isLoading: cardsLoading,
  } = useQuery({
    queryKey: ['cards', filterKey],
    queryFn: () =>
      fetchCardsPage(null, {
        name: debouncedFilter.name || undefined,
        colors: debouncedFilter.colors.size > 0 ? [...debouncedFilter.colors] : undefined,
        type: debouncedFilter.type !== 'All' ? debouncedFilter.type : undefined,
        maxCmc: debouncedFilter.maxCmc,
      }),
  });

  const [extraCards, setExtraCards] = useState<CardResource[]>([]);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // Reset extra pages when filter changes.
  useEffect(() => {
    setExtraCards([]);
    setNextUrl(cardPage?.nextUrl ?? null);
  }, [cardPage]);

  const loadMore = useCallback(async () => {
    const url = nextUrl ?? cardPage?.nextUrl;
    if (url == null) return;
    setLoadingMore(true);
    try {
      const page = await fetchCardsPage(url);
      setExtraCards(prev => [...prev, ...page.cards]);
      setNextUrl(page.nextUrl);
    } finally {
      setLoadingMore(false);
    }
  }, [nextUrl, cardPage]);

  const cards = useMemo(
    () => [...(cardPage?.cards ?? []), ...extraCards],
    [cardPage, extraCards],
  );

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
      owned,
      foil,
      existingId,
    }: {
      cardId: string;
      owned: number;
      foil: number;
      existingId?: string;
    }) => upsertCollectionCard(cardId, owned, foil, existingId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collectionCards'] }),
  });

  function handleQuantityChange(
    card: CardResource,
    delta: number,
    field: 'owned' | 'foil',
  ): void {
    const cardId = card.id;
    if (cardId == null) return;

    const existing = collectionMap.get(cardId);
    const owned = existing?.attributes.field_quantity_owned ?? 0;
    const foil = existing?.attributes.field_quantity_foil ?? 0;

    const nextOwned = field === 'owned' ? Math.max(0, owned + delta) : owned;
    const nextFoil = field === 'foil' ? Math.max(0, foil + delta) : foil;

    upsert.mutate({
      cardId,
      owned: nextOwned,
      foil: nextFoil,
      existingId: existing?.id,
    });
  }

  // Client-side type filter on already-fetched cards (server filters name/cmc/color).
  const filteredCards = useMemo(() => {
    if (filter.type === 'All') return cards;
    return cards.filter(card => {
      const type = classifyType(card.attributes.field_type_line ?? '');
      return type === filter.type;
    });
  }, [cards, filter.type]);

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
    <main style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <CardFilter filter={filter} onChange={handleFilterChange} />

      <div style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
        <h1 style={{ marginTop: 0 }}>
          Collection
          {isLoading && (
            <span style={{ fontSize: '0.75rem', marginLeft: 8, color: '#888' }}>
              loading...
            </span>
          )}
        </h1>

        {!cardsLoading && cards.length === 0 && (
          <p>
            No cards found. Try adjusting your filters or run{' '}
            <code>ddev drush mtg-scryfall:sync</code> to import cards from
            Scryfall.
          </p>
        )}

        <div
          style={{
            display: 'grid',
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

            return (
              <div
                key={card.id}
                style={{
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  overflow: 'hidden',
                  background: owned > 0 || foil > 0 ? '#fffef0' : '#fff',
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
                      background: '#e8e8e8',
                      cursor: 'pointer',
                      padding: '0.5rem',
                      textAlign: 'center',
                      fontSize: '0.8rem',
                    }}
                  >
                    {title}
                  </div>
                )}

                <div style={{ padding: '0.5rem', fontSize: '0.75rem' }}>
                  <div
                    style={{
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginBottom: 4,
                      fontWeight: owned > 0 ? 'bold' : 'normal',
                    }}
                    title={title}
                  >
                    {title}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button
                      type="button"
                      onClick={() => handleQuantityChange(card, -1, 'owned')}
                      disabled={owned === 0}
                      style={{ width: 24, padding: 0 }}
                    >
                      -
                    </button>
                    <span title="Owned">{owned}</span>
                    <button
                      type="button"
                      onClick={() => handleQuantityChange(card, 1, 'owned')}
                      style={{ width: 24, padding: 0 }}
                    >
                      +
                    </button>
                    {foil > 0 && (
                      <span style={{ marginLeft: 4, color: '#888' }} title={`Foil: ${foil}`}>
                        foil:{foil}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {(nextUrl != null || (cardPage?.nextUrl != null && extraCards.length === 0)) && (
          <div style={{ textAlign: 'center', padding: '1rem' }}>
            <button
              type="button"
              onClick={() => { void loadMore(); }}
              disabled={loadingMore}
              style={{ padding: '0.5rem 1.5rem' }}
            >
              {loadingMore ? 'Loading...' : 'Load more cards'}
            </button>
          </div>
        )}
      </div>

      <div style={{ padding: '1rem', borderLeft: '1px solid #eee' }}>
        <CollectionSidebar
          totalCards={totalCards}
          totalUnique={totalUnique}
          totalFoil={totalFoil}
          filtered={filteredCopies}
          filteredUnique={filteredCards.length}
        />
      </div>

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
          } as CardData}
          quantityOwned={modalEntry?.attributes.field_quantity_owned}
          quantityFoil={modalEntry?.attributes.field_quantity_foil}
          onClose={() => setModalCard(null)}
        />
      )}
    </main>
  );
};

export default CollectionPage;
