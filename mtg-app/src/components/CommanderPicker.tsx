/**
 * Commander / Tiny Leaders commander card picker.
 */

import React, { useMemo, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { findCardsByName, updateDeck } from '../services/drupalApi';
import type { DeckCommander } from '../types/drupal';
import { cardImageSrc } from '../utils/cardImage';
import { isLegalCommanderCard, isTinyLeadersFormat } from '../utils/deckAnalysis';
import PrintingFilter, {
  EMPTY_PRINTING_FILTER,
  matchesPrintingFilter,
} from './PrintingFilter';

interface CommanderPickerProps {
  deckId: string;
  format: string;
  commander: DeckCommander | null | undefined;
}

const CommanderPicker: React.FC<CommanderPickerProps> = ({
  deckId,
  format,
  commander,
}) => {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [searching, setSearching] = useState(false);
  const [changing, setChanging] = useState(commander == null);
  const [results, setResults] = useState<
    {
      id: string;
      title: string;
      typeLine: string;
      cmc: number;
      oracleText: string;
      setCode: string;
      setName: string;
      collectorNumber: string;
      imageUri: string;
      fullArt: boolean;
      borderColor: string;
    }[]
  >([]);
  const [printingFilter, setPrintingFilter] = useState(EMPTY_PRINTING_FILTER);
  const lastSearchName = useRef('');

  const save = useMutation({
    mutationFn: (commanderId: string) => updateDeck(deckId, { commanderId }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['deck'] });
      setChanging(false);
      setResults([]);
      setSearch('');
    },
  });

  async function handleSearch(): Promise<void> {
    if (search.trim() === '') {
      return;
    }
    const q = search.trim();
    const qLower = q.toLowerCase();
    if (qLower !== lastSearchName.current) {
      lastSearchName.current = qLower;
      setPrintingFilter(EMPTY_PRINTING_FILTER);
    }
    setSearching(true);
    try {
      const cards = await findCardsByName(q, { contains: true });
      setResults(
        cards.map(c => ({
          id: c.id,
          title: c.attributes.title,
          typeLine: c.attributes.field_type_line ?? '',
          cmc: c.attributes.field_cmc ?? 0,
          oracleText:
            typeof c.attributes.field_oracle_text === 'string'
              ? c.attributes.field_oracle_text
              : c.attributes.field_oracle_text?.value ?? '',
          setCode: c.attributes.field_set_code ?? '',
          setName: c.attributes.field_set_name ?? '',
          collectorNumber: c.attributes.field_collector_number ?? '',
          imageUri: c.attributes.field_image_uri ?? '',
          fullArt: Boolean(c.attributes.field_full_art),
          borderColor: c.attributes.field_border_color ?? '',
        })),
      );
    } finally {
      setSearching(false);
    }
  }

  const filteredResults = useMemo(
    () =>
      results.filter(r =>
        matchesPrintingFilter(
          {
            field_set_code: r.setCode,
            field_set_name: r.setName,
            field_collector_number: r.collectorNumber,
            field_full_art: r.fullArt,
            field_border_color: r.borderColor,
          },
          printingFilter,
        ),
      ),
    [results, printingFilter],
  );

  const label = isTinyLeadersFormat(format) ? 'Tiny Leader' : 'Commander';

  return (
    <div>
      {commander != null && !changing && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={() => setChanging(true)}
            style={{ fontSize: 10 }}
          >
            Change {label.toLowerCase()}
          </button>
          <button
            type="button"
            onClick={() => save.mutate('')}
            disabled={save.isPending}
            style={{ fontSize: 10 }}
          >
            Clear
          </button>
        </div>
      )}

      {(commander == null || changing) && (
        <div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  void handleSearch();
                }
              }}
              placeholder={`Search ${label.toLowerCase()} name...`}
              style={{ flex: 1 }}
              autoFocus={changing}
            />
            <button
              type="button"
              onClick={() => void handleSearch()}
              disabled={searching}
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
            {commander != null && (
              <button
                type="button"
                onClick={() => {
                  setChanging(false);
                  setResults([]);
                  setSearch('');
                }}
              >
                Cancel
              </button>
            )}
          </div>
          {results.length > 0 && (
            <PrintingFilter value={printingFilter} onChange={setPrintingFilter} />
          )}
          {filteredResults.length > 0 && (
            <ul style={{ listStyle: 'none', margin: '8px 0 0', padding: 0 }}>
              {filteredResults.map(r => {
                const legal = isLegalCommanderCard(
                  r.typeLine,
                  r.cmc,
                  r.oracleText,
                  format,
                );
                const meta = [r.setName || r.setCode.toUpperCase(), r.collectorNumber]
                  .filter(Boolean)
                  .join(' · ');
                return (
                  <li
                    key={r.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '0.35rem 0',
                      borderBottom: '1px solid var(--line)',
                    }}
                  >
                    <img
                      src={cardImageSrc({ field_image_uri: r.imageUri })}
                      alt=""
                      width={32}
                      height={44}
                      style={{ objectFit: 'cover', borderRadius: 2 }}
                    />
                    <span style={{ flex: 1, color: legal ? 'var(--ink)' : 'var(--neg)' }}>
                      <strong>{r.title}</strong>
                      <span className="mono dim" style={{ marginLeft: 8, fontSize: 11 }}>
                        {r.typeLine}
                        {meta !== '' ? ` · ${meta}` : ''}
                      </span>
                    </span>
                    <button
                      type="button"
                      disabled={!legal || save.isPending}
                      title={
                        legal
                          ? `Set as ${label.toLowerCase()}`
                          : `Not a legal ${label.toLowerCase()} for ${format}`
                      }
                      onClick={() => save.mutate(r.id)}
                    >
                      Use
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {results.length > 0 && filteredResults.length === 0 && (
            <p style={{ margin: '8px 0 0', fontSize: 13, opacity: 0.8 }}>
              No printings match this filter.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default CommanderPicker;
