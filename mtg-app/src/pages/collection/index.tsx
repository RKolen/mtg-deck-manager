/**
 * Collection binder page — Phase 3.
 *
 * Card catalogue is fetched at build time via gatsby-source-drupal + GraphQL.
 * Collection quantities (owned/foil) are fetched at runtime via JSON:API and
 * managed through @tanstack/react-query.
 */

import React, { useState, useMemo } from 'react';
import { graphql, type PageProps } from 'gatsby';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import CardFilter, { type FilterState } from '../../components/CardFilter';
import CardModal, { type CardData } from '../../components/CardModal';
import CollectionSidebar from '../../components/CollectionSidebar';
import { fetchCollectionCards, upsertCollectionCard } from '../../services/drupalApi';
import { isLand, classifyType } from '../../utils/deckAnalysis';
import type { CollectionCard } from '../../types/drupal';

// ---------------------------------------------------------------------------
// GraphQL page query (build-time card catalogue)
// ---------------------------------------------------------------------------

export const query = graphql`
  query CollectionPageQuery {
    allNodeMtgCard {
      nodes {
        id
        drupalId
        title
        field_mana_cost
        field_cmc
        field_type_line
        field_colors
        field_color_identity
        field_oracle_text
        field_scryfall_id
        field_image_uri
        field_is_mana_producer
        field_produced_mana
        field_legal_formats
      }
    }
  }
`;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GatsbyCard {
  id: string;
  drupalId?: string | null;
  title?: string | null;
  field_mana_cost?: string | null;
  field_cmc?: number | null;
  field_type_line?: string | null;
  field_colors?: string[] | null;
  field_color_identity?: string[] | null;
  field_oracle_text?: string | null;
  field_scryfall_id?: string | null;
  field_image_uri?: string | null;
  field_is_mana_producer?: boolean | null;
  field_produced_mana?: string[] | null;
  field_legal_formats?: string[] | null;
}

interface QueryData {
  allNodeMtgCard: {
    nodes: GatsbyCard[];
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CollectionPage: React.FC<PageProps<QueryData>> = ({ data }) => {
  const cards = data.allNodeMtgCard.nodes;

  const [filter, setFilter] = useState<FilterState>({
    name: '',
    colors: new Set(),
    type: 'All',
    maxCmc: null,
  });
  const [modalCard, setModalCard] = useState<GatsbyCard | null>(null);

  const qc = useQueryClient();

  // Fetch all collection_card nodes at runtime.
  const { data: collectionCards = [], isLoading } = useQuery<CollectionCard[]>({
    queryKey: ['collectionCards'],
    queryFn: fetchCollectionCards,
  });

  // Build a map: drupalId (mtg_card UUID) → collection_card resource.
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
    card: GatsbyCard,
    delta: number,
    field: 'owned' | 'foil',
  ): void {
    const drupalId = card.drupalId;
    if (drupalId == null) return;

    const existing = collectionMap.get(drupalId);
    const owned = existing?.attributes.field_quantity_owned ?? 0;
    const foil = existing?.attributes.field_quantity_foil ?? 0;

    const nextOwned = field === 'owned' ? Math.max(0, owned + delta) : owned;
    const nextFoil = field === 'foil' ? Math.max(0, foil + delta) : foil;

    upsert.mutate({
      cardId: drupalId,
      owned: nextOwned,
      foil: nextFoil,
      existingId: existing?.id,
    });
  }

  // Client-side filtering.
  const filteredCards = useMemo(() => {
    return cards.filter(card => {
      if (
        filter.name !== '' &&
        !(card.title ?? '').toLowerCase().includes(filter.name.toLowerCase())
      ) {
        return false;
      }

      if (filter.colors.size > 0) {
        const cardColors = card.field_colors ?? [];
        const hasColor = [...filter.colors].some(c => cardColors.includes(c));
        if (!hasColor) return false;
      }

      if (filter.type !== 'All') {
        const type = classifyType(card.field_type_line ?? '');
        if (type !== filter.type) return false;
      }

      if (
        filter.maxCmc !== null &&
        !isLand(card.field_type_line ?? '') &&
        (card.field_cmc ?? 0) > filter.maxCmc
      ) {
        return false;
      }

      return true;
    });
  }, [cards, filter]);

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
        const cc = collectionMap.get(card.drupalId ?? '');
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
      ? collectionMap.get(modalCard.drupalId ?? '')
      : undefined;

  return (
    <main style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <CardFilter filter={filter} onChange={setFilter} />

      <div style={{ flex: 1, overflow: 'auto', padding: '1rem' }}>
        <h1 style={{ marginTop: 0 }}>
          Collection
          {isLoading && (
            <span style={{ fontSize: '0.75rem', marginLeft: 8, color: '#888' }}>
              loading quantities...
            </span>
          )}
        </h1>

        {cards.length === 0 && (
          <p>
            No cards imported yet. Run{' '}
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
            const cc = collectionMap.get(card.drupalId ?? '');
            const owned = cc?.attributes.field_quantity_owned ?? 0;
            const foil = cc?.attributes.field_quantity_foil ?? 0;

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
                {card.field_image_uri != null ? (
                  <img
                    src={card.field_image_uri}
                    alt={card.title ?? ''}
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
                    {card.title}
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
                    title={card.title ?? ''}
                  >
                    {card.title}
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
          card={modalCard as CardData}
          quantityOwned={modalEntry?.attributes.field_quantity_owned}
          quantityFoil={modalEntry?.attributes.field_quantity_foil}
          onClose={() => setModalCard(null)}
        />
      )}
    </main>
  );
};

export default CollectionPage;
