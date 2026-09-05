/**
 * Card detail + all printings.
 *
 * Route: /cards/:slug
 * Resolves one printing by slug, then lists every printing with the same title.
 * When opened from a deck (?deck=&slot=), choosing another printing updates
 * that deck slot. Collection changes only if you pick Replace or Add.
 */

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCardBySlug,
  findCardsByName,
  replaceCommanderPrinting,
  replaceDeckCardPrinting,
} from '../../services/drupalApi';
import { invalidateInventoryQueries } from '../../services/queryCache';
import PrintingSwapDialog, {
  type CollectionSwapMode,
  type PrintingSwapTarget,
} from '../../components/PrintingSwapDialog';
import { getOracleText } from '../../utils/deckAnalysis';
import { COMMANDER_SLOT, cardPrintingsPath } from '../../utils/slugify';
import { useTheme } from '../../context/ThemeContext';
import PrintingFilter, {
  EMPTY_PRINTING_FILTER,
  matchesPrintingFilter,
} from '../../components/PrintingFilter';
import { formatPrice, priceFor } from '../../utils/prices';
import type { MtgCard } from '../../types/drupal';

const CardPage: React.FC = () => {
  const router = useRouter();
  const qc = useQueryClient();
  const { currency } = useTheme();
  const slug = typeof router.query.slug === 'string' ? router.query.slug : '';
  const highlightId =
    typeof router.query.printing === 'string' ? router.query.printing : '';
  const deckId = typeof router.query.deck === 'string' ? router.query.deck : '';
  const slotId = typeof router.query.slot === 'string' ? router.query.slot : '';
  const fromSlug = typeof router.query.from === 'string' ? router.query.from : '';
  const deckIsFoil = router.query.foil === '1' || router.query.foil === 'true';
  const isCommanderSlot = slotId === COMMANDER_SLOT;
  const fromDeck = deckId !== '' && slotId !== '';

  const [pending, setPending] = useState<PrintingSwapTarget | null>(null);
  const [swapError, setSwapError] = useState<string | null>(null);
  const [printingFilter, setPrintingFilter] = useState(EMPTY_PRINTING_FILTER);

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ['card', slug],
    queryFn: () => fetchCardBySlug(slug),
    enabled: router.isReady && slug !== '',
    staleTime: 5 * 60_000,
  });

  const title = card?.attributes.title ?? '';

  const { data: printings = [], isLoading: printingsLoading } = useQuery({
    queryKey: ['printings', title],
    queryFn: () => findCardsByName(title),
    enabled: title !== '',
    staleTime: 60_000,
  });

  const sortedPrintings = useMemo(() => {
    return [...printings].sort((a, b) => {
      const sa = a.attributes.field_set_name ?? a.attributes.field_set_code ?? '';
      const sb = b.attributes.field_set_name ?? b.attributes.field_set_code ?? '';
      if (sa !== sb) return sa.localeCompare(sb);
      const pa = priceFor(a.attributes, currency) ?? 0;
      const pb = priceFor(b.attributes, currency) ?? 0;
      return pb - pa;
    });
  }, [printings, currency]);

  const filteredPrintings = useMemo(
    () => sortedPrintings.filter(p => matchesPrintingFilter(p.attributes, printingFilter)),
    [sortedPrintings, printingFilter],
  );

  const displayed: MtgCard | undefined = useMemo(() => {
    if (highlightId !== '') {
      const match = printings.find(p => p.id === highlightId);
      if (match != null) {
        return match;
      }
    }
    return card ?? undefined;
  }, [card, printings, highlightId]);

  const currentPrinting: PrintingSwapTarget | null = displayed != null
    ? { id: displayed.id, attributes: displayed.attributes }
    : null;

  const swap = useMutation({
    mutationFn: ({
      nextId,
      mode,
      foil,
    }: {
      nextId: string;
      mode: CollectionSwapMode;
      foil: boolean;
    }) =>
      isCommanderSlot
        ? replaceCommanderPrinting(
            deckId,
            nextId,
            pending?.attributes.title ?? title,
            mode,
            foil,
            currentPrinting?.id,
            currentPrinting?.attributes.title,
          )
        : replaceDeckCardPrinting(deckId, slotId, nextId, mode, foil),
    onSuccess: async (_data, vars) => {
      await invalidateInventoryQueries(qc, { deckId });
      await qc.invalidateQueries({ queryKey: ['deck'] });
      setPending(null);
      setSwapError(null);
      const nextTitle = pending?.attributes.title ?? title;
      await router.replace(
        cardPrintingsPath(nextTitle, {
          printing: vars.nextId,
          deckId,
          slotId,
          from: fromSlug,
          foil: deckIsFoil,
        }),
        undefined,
        { shallow: true },
      );
    },
    onError: (err: unknown) => {
      setSwapError(err instanceof Error ? err.message : 'Could not update the deck.');
    },
  });

  function keepDeckContext(printingId: string): string {
    return cardPrintingsPath(title !== '' ? title : slug, {
      printing: printingId,
      deckId: fromDeck ? deckId : undefined,
      slotId: fromDeck ? slotId : undefined,
      from: fromDeck ? fromSlug : undefined,
      foil: fromDeck ? deckIsFoil : undefined,
    });
  }

  function handlePrintingClick(
    event: React.MouseEvent<HTMLAnchorElement>,
    printing: MtgCard,
  ): void {
    if (!fromDeck || currentPrinting == null || printing.id === currentPrinting.id) {
      return;
    }
    event.preventDefault();
    setSwapError(null);
    setPending({ id: printing.id, attributes: printing.attributes });
  }

  if (isLoading) {
    return (
      <main style={{ padding: '1.5rem' }}>
        <p>Loading card...</p>
      </main>
    );
  }

  if (isError || card == null || displayed == null) {
    return (
      <main style={{ padding: '1.5rem' }}>
        <p style={{ color: '#c00' }}>Card not found.</p>
        <p>
          <Link href="/collection">Back to collection</Link>
        </p>
      </main>
    );
  }

  const attrs = displayed.attributes;
  const oracleText = getOracleText(attrs);
  const isCreature =
    attrs.field_type_line != null && attrs.field_type_line.includes('Creature');
  const isPlaneswalker =
    attrs.field_type_line != null && attrs.field_type_line.includes('Planeswalker');
  const backHref = fromSlug !== '' ? `/decks/${fromSlug}` : '/collection';
  const backLabel = fromSlug !== '' ? 'Back to deck' : 'Back to collection';

  return (
    <main
      style={{
        padding: '1.5rem',
        maxWidth: 1100,
        color: 'var(--ink)',
        background: 'var(--bg)',
      }}
    >
      <p style={{ margin: '0 0 1.25rem' }}>
        <Link href={backHref} style={{ color: 'var(--accent)' }}>
          {backLabel}
        </Link>
      </p>

      {fromDeck && (
        <p style={{ margin: '0 0 1rem', fontSize: 13, opacity: 0.9 }}>
          Choosing another printing updates this deck
          {fromSlug !== '' ? ` (${fromSlug.replace(/-/g, ' ')})` : ''}
          . Collection changes only if you pick Replace or Add.
        </p>
      )}

      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        {attrs.field_image_uri != null && attrs.field_image_uri !== '' && (
          <img
            src={attrs.field_image_uri}
            alt={attrs.title}
            style={{
              width: 265,
              borderRadius: 12,
              alignSelf: 'flex-start',
              flexShrink: 0,
            }}
          />
        )}

        <div style={{ flex: 1, minWidth: 220, color: 'var(--ink)' }}>
          <h1 style={{ margin: '0 0 0.25rem', color: 'var(--ink)' }}>{attrs.title}</h1>

          {attrs.field_mana_cost != null && attrs.field_mana_cost !== '' && (
            <p style={{ margin: '0 0 0.25rem', fontSize: '1.05rem', color: 'var(--ink)' }}>
              {attrs.field_mana_cost}
              {attrs.field_cmc != null && (
                <span style={{ marginLeft: 8, color: 'var(--ink)', fontSize: '0.9rem' }}>
                  (CMC {attrs.field_cmc})
                </span>
              )}
            </p>
          )}

          {attrs.field_type_line != null && (
            <p style={{ margin: '0 0 0.75rem', fontStyle: 'italic', color: 'var(--ink)' }}>
              {attrs.field_type_line}
            </p>
          )}

          {oracleText !== '' && (
            <p
              style={{
                whiteSpace: 'pre-wrap',
                background: 'var(--bg-2)',
                color: 'var(--ink)',
                border: '1px solid var(--line)',
                padding: '0.6rem 0.75rem',
                borderRadius: 4,
                fontSize: '0.95rem',
                margin: '0 0 0.75rem',
                lineHeight: 1.5,
              }}
            >
              {oracleText}
            </p>
          )}

          {isCreature && (attrs.field_power != null || attrs.field_toughness != null) && (
            <p style={{ margin: '0 0 0.5rem', fontWeight: 'bold', color: 'var(--ink)' }}>
              {attrs.field_power ?? '?'} / {attrs.field_toughness ?? '?'}
            </p>
          )}

          {isPlaneswalker && attrs.field_loyalty != null && (
            <p style={{ margin: '0 0 0.5rem', fontWeight: 'bold', color: 'var(--ink)' }}>
              Loyalty: {attrs.field_loyalty}
            </p>
          )}

          {(attrs.field_set_name || attrs.field_set_code) && (
            <p style={{ margin: '0 0 0.25rem', fontSize: '0.875rem' }}>
              <strong>This printing:</strong>{' '}
              {attrs.field_set_name ?? attrs.field_set_code}
              {attrs.field_collector_number ? ` #${attrs.field_collector_number}` : ''}
              {attrs.field_rarity ? ` · ${attrs.field_rarity}` : ''}
            </p>
          )}

          {attrs.field_legal_formats != null && attrs.field_legal_formats.length > 0 && (
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: 'var(--ink)' }}>
              <strong>Legal in:</strong> {attrs.field_legal_formats.join(', ')}
            </p>
          )}
        </div>
      </div>

      <section>
        <h2 style={{ margin: '0 0 0.75rem', fontSize: '1.1rem' }}>
          All printings
          {!printingsLoading && (
            <span style={{ fontWeight: 400, fontSize: '0.9rem', marginLeft: 8, opacity: 0.85 }}>
              ({filteredPrintings.length}
              {filteredPrintings.length !== sortedPrintings.length
                ? ` of ${sortedPrintings.length}`
                : ''}
              )
            </span>
          )}
        </h2>

        <PrintingFilter value={printingFilter} onChange={setPrintingFilter} />

        {printingsLoading && <p>Loading printings...</p>}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
            gap: '0.75rem',
          }}
        >
          {filteredPrintings.map(p => {
            const a = p.attributes;
            const active = p.id === displayed.id || p.id === highlightId;
            const price = priceFor(a, currency);
            const foil = priceFor(a, currency, true);
            return (
              <Link
                key={p.id}
                href={keepDeckContext(p.id)}
                onClick={e => handlePrintingClick(e, p)}
                style={{
                  textDecoration: 'none',
                  color: 'var(--ink)',
                  border: active ? '2px solid var(--accent)' : '1px solid var(--line)',
                  borderRadius: 6,
                  overflow: 'hidden',
                  background: 'var(--bg-2)',
                  cursor: fromDeck && !active ? 'pointer' : undefined,
                }}
              >
                {a.field_image_uri ? (
                  <img
                    src={a.field_image_uri}
                    alt={`${a.title} (${a.field_set_code ?? ''})`}
                    style={{ width: '100%', display: 'block' }}
                  />
                ) : (
                  <div
                    style={{
                      height: 200,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'var(--bg-3)',
                      fontSize: 12,
                      padding: 8,
                      textAlign: 'center',
                    }}
                  >
                    {a.field_set_name ?? a.title}
                  </div>
                )}
                <div style={{ padding: '0.45rem 0.5rem', fontSize: 11 }}>
                  <div style={{ fontWeight: 700, marginBottom: 2 }}>
                    {a.field_set_name ?? a.field_set_code?.toUpperCase() ?? 'Unknown set'}
                  </div>
                  <div style={{ opacity: 0.85 }}>
                    {(a.field_set_code ?? '').toUpperCase()}
                    {a.field_collector_number ? ` #${a.field_collector_number}` : ''}
                    {a.field_rarity ? ` · ${a.field_rarity}` : ''}
                  </div>
                  <div style={{ marginTop: 2 }}>
                    {formatPrice(price, currency)}
                    {foil != null && foil !== price && (
                      <span style={{ opacity: 0.85 }}> · foil {formatPrice(foil, currency)}</span>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {pending != null && currentPrinting != null && (
        <PrintingSwapDialog
          current={currentPrinting}
          next={pending}
          currency={currency}
          deckIsFoil={deckIsFoil}
          isSaving={swap.isPending}
          error={swapError}
          onCancel={() => {
            if (!swap.isPending) {
              setPending(null);
              setSwapError(null);
            }
          }}
          onConfirm={(mode, foil) => {
            swap.mutate({ nextId: pending.id, mode, foil });
          }}
        />
      )}
    </main>
  );
};

export const getServerSideProps = async () => ({ props: {} });

export default CardPage;
