/**
 * XLSX deck import page — Phase 6.
 *
 * Parses a Magic Deck Spreadsheet v2 Excel file client-side using xlsx.js,
 * matches card names against the Drupal card library, presents unmatched
 * cards for manual resolution, then POSTs deck + deck_card nodes via JSON:API.
 */

import React, { useState, useCallback, useRef } from 'react';
import { Link, navigate } from 'gatsby';
import * as XLSX from 'xlsx';
import {
  findCardsByName,
  createDeck,
  addCardToDeck,
} from '../../services/drupalApi';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ParsedRow {
  name: string;
  quantity: number;
  isSideboard: boolean;
}

interface MatchedRow extends ParsedRow {
  matchId: string | null;
  matchTitle: string | null;
  candidates: { id: string; title: string }[];
}

// ---------------------------------------------------------------------------
// XLSX parsing helpers
// ---------------------------------------------------------------------------

/**
 * Reads spreadsheet rows and tries to extract (quantity, name) pairs.
 *
 * Strategy:
 *  1. Look for a column header containing "name" and another containing "qty"
 *     or "quantity". Use those columns.
 *  2. Fall back to scanning each row for a numeric cell followed by a string
 *     cell (format: "4 Lightning Bolt" is also handled by splitting on space).
 */
function parseSheet(sheet: XLSX.WorkSheet): ParsedRow[] {
  const rows: XLSX.CellObject[][] = XLSX.utils.sheet_to_json(sheet, {
    header: 1,
    raw: false,
    blankrows: false,
  }) as XLSX.CellObject[][];

  if (rows.length === 0) return [];

  const results: ParsedRow[] = [];

  // Try header detection first.
  const headerRow = rows[0];
  if (headerRow != null) {
    const headers = headerRow.map(c =>
      String(c ?? '').toLowerCase().trim(),
    );
    const nameIdx = headers.findIndex(h => h.includes('name'));
    const qtyIdx = headers.findIndex(
      h => h.includes('qty') || h.includes('quantity'),
    );
    const sbIdx = headers.findIndex(
      h => h.includes('side') || h.includes('sb'),
    );

    if (nameIdx >= 0 && qtyIdx >= 0) {
      for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        if (row == null) continue;
        const name = String(row[nameIdx] ?? '').trim();
        const qty = parseInt(String(row[qtyIdx] ?? ''), 10);
        const isSideboard =
          sbIdx >= 0 ? Boolean(row[sbIdx]) : false;
        if (name !== '' && qty > 0) {
          results.push({ name, quantity: qty, isSideboard });
        }
      }
      if (results.length > 0) return results;
    }
  }

  // Fall back: scan all rows for qty + name pattern.
  let inSideboard = false;
  for (const row of rows) {
    if (row == null) continue;

    // Detect section headers like "Sideboard" or "Side"
    const firstCell = String(row[0] ?? '').trim().toLowerCase();
    if (/^side(board)?$/.test(firstCell)) {
      inSideboard = true;
      continue;
    }
    if (/^main(deck)?$/.test(firstCell)) {
      inSideboard = false;
      continue;
    }

    // Look for a numeric column followed by a string column.
    for (let ci = 0; ci < row.length - 1; ci++) {
      const maybeQty = parseInt(String(row[ci] ?? ''), 10);
      const maybeName = String(row[ci + 1] ?? '').trim();
      if (
        !isNaN(maybeQty) &&
        maybeQty > 0 &&
        maybeQty <= 99 &&
        maybeName.length > 0 &&
        /^[A-Za-z]/.test(maybeName)
      ) {
        results.push({
          name: maybeName,
          quantity: maybeQty,
          isSideboard: inSideboard,
        });
        break;
      }
    }

    // Also handle single-cell "4 Lightning Bolt" format.
    if (row.length === 1) {
      const cell = String(row[0] ?? '').trim();
      const m = /^(\d+)\s+(.+)/.exec(cell);
      if (m != null) {
        results.push({
          name: m[2]!.trim(),
          quantity: parseInt(m[1]!, 10),
          isSideboard: inSideboard,
        });
      }
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Step = 'upload' | 'matching' | 'confirm' | 'importing' | 'done';

const ImportPage: React.FC = () => {
  const [step, setStep] = useState<Step>('upload');
  const [deckTitle, setDeckTitle] = useState('Imported Deck');
  const [deckFormat, setDeckFormat] = useState('Other');
  const [rows, setRows] = useState<MatchedRow[]>([]);
  const [progress, setProgress] = useState('');
  const [createdDeckId, setCreatedDeckId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const FORMATS = [
    'Standard', 'Modern', 'Legacy', 'Vintage', 'Pioneer', 'Pauper', 'EDH', 'Other',
  ];

  // ----- Step 1: File parsing + name matching -----

  const handleFile = useCallback(
    async (file: File): Promise<void> => {
      setError(null);
      setProgress('Parsing spreadsheet...');
      setStep('matching');

      try {
        const buffer = await file.arrayBuffer();
        const wb = XLSX.read(buffer, { type: 'buffer' });

        // Use the first sheet.
        const sheetName = wb.SheetNames[0];
        if (sheetName == null) throw new Error('No sheets found in workbook.');
        const sheet = wb.Sheets[sheetName];
        if (sheet == null) throw new Error('Could not read sheet.');

        const parsed = parseSheet(sheet);
        if (parsed.length === 0) {
          throw new Error(
            'Could not detect any cards in this spreadsheet. ' +
              'Expected rows with a quantity column and a card-name column.',
          );
        }

        setProgress(
          `Found ${parsed.length} rows. Matching card names against library...`,
        );

        const matched: MatchedRow[] = [];
        for (const row of parsed) {
          const results = await findCardsByName(row.name);
          const exact = results.find(
            r => r.attributes.title.toLowerCase() === row.name.toLowerCase(),
          );
          matched.push({
            ...row,
            matchId: exact?.id ?? results[0]?.id ?? null,
            matchTitle:
              exact?.attributes.title ??
              results[0]?.attributes.title ??
              null,
            candidates: results.map(r => ({
              id: r.id,
              title: r.attributes.title,
            })),
          });
        }

        setRows(matched);
        setProgress('');
        setStep('confirm');
        setDeckTitle(file.name.replace(/\.[^.]+$/, ''));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setStep('upload');
        setProgress('');
      }
    },
    [],
  );

  function handleDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file != null) void handleFile(file);
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    if (file != null) void handleFile(file);
  }

  // ----- Step 2: Confirm / fix unmatched -----

  function updateMatch(index: number, candidateId: string): void {
    setRows(prev =>
      prev.map((r, i) => {
        if (i !== index) return r;
        const cand = r.candidates.find(c => c.id === candidateId);
        return {
          ...r,
          matchId: candidateId,
          matchTitle: cand?.title ?? null,
        };
      }),
    );
  }

  function removeRow(index: number): void {
    setRows(prev => prev.filter((_, i) => i !== index));
  }

  // ----- Step 3: Import -----

  async function handleImport(): Promise<void> {
    setError(null);
    setStep('importing');

    const toImport = rows.filter(r => r.matchId != null);
    if (toImport.length === 0) {
      setError('No matched cards to import.');
      setStep('confirm');
      return;
    }

    try {
      setProgress('Creating deck...');
      const deck = await createDeck({
        title: deckTitle,
        field_format: deckFormat,
        field_notes: null,
      });

      setProgress(`Adding ${toImport.length} cards...`);
      let i = 0;
      for (const row of toImport) {
        i++;
        setProgress(`Adding card ${i} / ${toImport.length}: ${row.name}`);
        // Add one copy at a time to match the direct-reference model.
        for (let copy = 0; copy < row.quantity; copy++) {
          // eslint-disable-next-line no-await-in-loop
          await addCardToDeck(
            deck.id,
            row.matchId!,
            row.isSideboard,
          );
        }
      }

      setCreatedDeckId(deck.id);
      setStep('done');
      setProgress('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStep('confirm');
      setProgress('');
    }
  }

  // ----- Render -----

  const unmatched = rows.filter(r => r.matchId == null);

  return (
    <main style={{ padding: '1.5rem', maxWidth: 800 }}>
      <p style={{ margin: '0 0 1rem' }}>
        <Link to="/">Home</Link>
      </p>
      <h1 style={{ marginTop: 0 }}>Import XLSX deck</h1>

      {error != null && (
        <p style={{ color: '#c00', background: '#fff0f0', padding: '0.75rem', borderRadius: 4 }}>
          {error}
        </p>
      )}

      {progress !== '' && (
        <p style={{ color: '#555', fontStyle: 'italic' }}>{progress}</p>
      )}

      {/* Upload step */}
      {step === 'upload' && (
        <div>
          <div
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            style={{
              border: '2px dashed #aaa',
              borderRadius: 8,
              padding: '3rem',
              textAlign: 'center',
              cursor: 'pointer',
              marginBottom: '1rem',
            }}
            onClick={() => fileRef.current?.click()}
          >
            <p style={{ margin: 0, fontSize: '1.1rem' }}>
              Drag and drop a{' '}
              <strong>Magic Deck Spreadsheet v2.xlsx</strong> file here
            </p>
            <p style={{ margin: '0.5rem 0 0', color: '#888' }}>
              or click to browse
            </p>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.ods,.csv"
            style={{ display: 'none' }}
            onChange={handleFileInput}
          />
          <p style={{ fontSize: '0.85rem', color: '#666' }}>
            The parser looks for columns named <em>Name</em> and{' '}
            <em>Quantity</em>, or rows with a numeric quantity in the first
            column followed by the card name. A row or cell containing
            &ldquo;Sideboard&rdquo; marks the sideboard section.
          </p>
        </div>
      )}

      {/* Matching spinner */}
      {step === 'matching' && (
        <p>Working&hellip;</p>
      )}

      {/* Confirm step */}
      {step === 'confirm' && (
        <div>
          {unmatched.length > 0 && (
            <div
              style={{
                background: '#fff3cd',
                border: '1px solid #ffc107',
                borderRadius: 4,
                padding: '0.75rem',
                marginBottom: '1rem',
              }}
            >
              <strong>{unmatched.length} card(s) could not be matched</strong>
              {' '}— assign them manually below or remove them to proceed.
            </div>
          )}

          <div style={{ marginBottom: '1rem', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <label>
              Deck title
              <input
                type="text"
                value={deckTitle}
                onChange={e => setDeckTitle(e.target.value)}
                style={{ display: 'block', marginTop: 4 }}
              />
            </label>
            <label>
              Format
              <select
                value={deckFormat}
                onChange={e => setDeckFormat(e.target.value)}
                style={{ display: 'block', marginTop: 4 }}
              >
                {FORMATS.map(f => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.85rem',
            }}
          >
            <thead>
              <tr style={{ background: '#f5f5f0' }}>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Qty</th>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Parsed name</th>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Matched card</th>
                <th style={{ padding: '0.4rem' }}>SB</th>
                <th style={{ padding: '0.4rem' }}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  style={{
                    borderTop: '1px solid #eee',
                    background: row.matchId == null ? '#fff0f0' : undefined,
                  }}
                >
                  <td style={{ padding: '0.3rem 0.4rem' }}>{row.quantity}</td>
                  <td style={{ padding: '0.3rem 0.4rem' }}>{row.name}</td>
                  <td style={{ padding: '0.3rem 0.4rem' }}>
                    {row.candidates.length > 0 ? (
                      <select
                        value={row.matchId ?? ''}
                        onChange={e => updateMatch(i, e.target.value)}
                        style={{ maxWidth: 260 }}
                      >
                        <option value="">-- unmatched --</option>
                        {row.candidates.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span style={{ color: '#c00' }}>No candidates found</span>
                    )}
                  </td>
                  <td style={{ padding: '0.3rem 0.4rem', textAlign: 'center' }}>
                    {row.isSideboard ? 'SB' : ''}
                  </td>
                  <td style={{ padding: '0.3rem 0.4rem', textAlign: 'center' }}>
                    <button
                      type="button"
                      onClick={() => removeRow(i)}
                      aria-label="Remove row"
                      style={{ fontSize: '0.75rem' }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: '1.25rem', display: 'flex', gap: 12 }}>
            <button
              type="button"
              onClick={() => void handleImport()}
              disabled={
                rows.filter(r => r.matchId != null).length === 0 ||
                deckTitle.trim() === ''
              }
            >
              Import {rows.filter(r => r.matchId != null).length} cards
            </button>
            <button
              type="button"
              onClick={() => {
                setRows([]);
                setStep('upload');
              }}
            >
              Start over
            </button>
          </div>
        </div>
      )}

      {/* Importing spinner */}
      {step === 'importing' && <p>Importing&hellip;</p>}

      {/* Done */}
      {step === 'done' && createdDeckId != null && (
        <div>
          <p style={{ color: 'green', fontWeight: 'bold' }}>
            Deck imported successfully.
          </p>
          <button
            type="button"
            onClick={() => void navigate(`/decks/${createdDeckId}`)}
          >
            Open deck
          </button>
          {' '}
          <button
            type="button"
            onClick={() => {
              setRows([]);
              setCreatedDeckId(null);
              setStep('upload');
            }}
          >
            Import another
          </button>
        </div>
      )}
    </main>
  );
};

export default ImportPage;
