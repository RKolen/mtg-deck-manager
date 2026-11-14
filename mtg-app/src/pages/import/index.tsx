/**
 * Deck import page.
 *
 * Parses a Magic Deck Spreadsheet v2 Excel file client-side using xlsx.js,
 * or a plain-text list (.txt) like the deck page's "Copy for Cardmarket"
 * export or an Arena / Moxfield export. Card names are matched against the
 * Drupal card library, unmatched cards are resolved by hand, then the deck
 * and slots are created via GraphQL. In commander formats one line becomes
 * the commander: a "Commander" section, else the first line, as the export
 * writes it.
 *
 * The "Collection (CSV)" mode adds cards to the collection instead.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useQuery } from '@tanstack/react-query';
import * as XLSX from 'xlsx';
import {
  findCardsByName,
  fetchFormats,
  createDeck,
  importCardToDeck,
} from '../../services/drupalApi';
import { slugify } from '../../utils/slugify';
import { parseCardList } from '../../utils/cardList';
import { usesCommanderCard } from '../../utils/deckAnalysis';
import { bestPrice, formatPrice } from '../../utils/prices';
import { useTheme } from '../../context/ThemeContext';
import CollectionCsvImport from '../../components/CollectionCsvImport';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ParsedRow {
  name: string;
  quantity: number;
  isSideboard: boolean;
  isFoil: boolean;
  /** Listed under a "Commander" header in a text list. */
  isCommander?: boolean;
  /** Printing named in a text list, e.g. "(BOT) 17". */
  setCode?: string | null;
  collectorNumber?: string | null;
}

interface MatchedRow extends ParsedRow {
  /** Stable row key; indexes shift when rows are removed. */
  uid: number;
  matchId: string | null;
  matchTitle: string | null;
  /** Printings to choose from, cheapest first; label adds set, number and price. */
  candidates: { id: string; title: string; label: string }[];
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
 *  2. Detect Magic Deck Spreadsheet v2 three-section horizontal layout
 *     (Lands | Spells | Creatures in parallel columns). A blank row after
 *     the main deck signals the sideboard section.
 *  3. Fall back to scanning each row for a numeric cell followed by a string
 *     cell (format: "4 Lightning Bolt" is also handled by splitting on space).
 */
function parseSheet(sheet: XLSX.WorkSheet): ParsedRow[] {
  // Keep blank rows so we can detect the sideboard blank-row separator.
  const rows = XLSX.utils.sheet_to_json(sheet, {
    header: 1,
    raw: false,
    blankrows: true,
  }) as (string | null)[][];

  if (rows.length === 0) return [];

  // --- Strategy 1: simple name/qty header row ---
  const firstNonBlank = rows.find(r => r.some(c => c != null && String(c).trim() !== ''));
  if (firstNonBlank != null) {
    const headers = Array.from(firstNonBlank, c => String(c ?? '').toLowerCase().trim());
    const nameIdx = headers.findIndex(h => h.includes('name'));
    const qtyIdx = headers.findIndex(h => h.includes('qty') || h.includes('quantity'));
    const sbIdx = headers.findIndex(h => h.includes('side') || h.includes('sb'));

    if (nameIdx >= 0 && qtyIdx >= 0) {
      const results: ParsedRow[] = [];
      const startIdx = rows.indexOf(firstNonBlank) + 1;
      for (let i = startIdx; i < rows.length; i++) {
        const row = rows[i];
        if (row == null) continue;
        const name = String(row[nameIdx] ?? '').trim();
        const qty = parseInt(String(row[qtyIdx] ?? ''), 10);
        const isSideboard = sbIdx >= 0 ? String(row[sbIdx] ?? '').trim() !== '' : false;
        if (name !== '' && qty > 0) results.push({ name, quantity: qty, isSideboard, isFoil: false });
      }
      if (results.length > 0) return results;
    }
  }

  // --- Strategy 2: Magic Deck Spreadsheet v2 three-section horizontal layout ---
  // Row format: ["Lands", null*7, "Spells", null*8, "Creatures"]
  // Followed by a column-header row, then data rows.
  // A blank row after the last data row introduces a sideboard section.
  const sectionHeaderIdx = rows.findIndex(
    row =>
      row.some(c => String(c ?? '').trim() === 'Lands') &&
      row.some(c => String(c ?? '').trim() === 'Spells') &&
      row.some(c => String(c ?? '').trim() === 'Creatures'),
  );

  if (sectionHeaderIdx >= 0) {
    const sectionRow = rows[sectionHeaderIdx]!;
    const landsCol = sectionRow.findIndex(c => String(c ?? '').trim() === 'Lands');
    const spellsCol = sectionRow.findIndex(c => String(c ?? '').trim() === 'Spells');
    const creaturesCol = sectionRow.findIndex(c => String(c ?? '').trim() === 'Creatures');

    // Each section: qty at sectionCol, name at sectionCol+1.
    const sections = [landsCol, spellsCol, creaturesCol]
      .filter(col => col >= 0)
      .map(col => ({ qtyCol: col, nameCol: col + 1 }));

    // Data starts two rows after the section header (skip column-name row).
    const dataStartIdx = sectionHeaderIdx + 2;
    const results: ParsedRow[] = [];
    let inSideboard = false;
    let seenCards = false;

    for (let i = dataStartIdx; i < rows.length; i++) {
      const row = rows[i]!;
      // A row is blank when none of the card-name columns have a value.
      // ODS templates leave "0" totals in non-name columns, so we check
      // name columns only rather than testing every cell.
      const isBlank = sections.every(
        ({ nameCol }) => String(row[nameCol] ?? '').trim() === '',
      );

      if (isBlank) {
        if (seenCards) inSideboard = true;
        continue;
      }

      for (const { qtyCol, nameCol } of sections) {
        const qty = parseInt(String(row[qtyCol] ?? ''), 10);
        // Strip trailing foil marker " F" added by some spreadsheet templates.
        const rawName = String(row[nameCol] ?? '').trim();
        const isFoil = / F$/.test(rawName);
        const name = rawName.replace(/ F$/, '').trim();
        if (!isNaN(qty) && qty > 0 && name.length > 0 && /^[A-Za-z]/.test(name)) {
          results.push({ name, quantity: qty, isSideboard: inSideboard, isFoil });
          seenCards = true;
        }
      }
    }

    if (results.length > 0) return results;
  }

  // --- Strategy 3: fallback qty+name scan ---
  const results: ParsedRow[] = [];
  let inSideboard = false;
  for (const row of rows) {
    if (row == null) continue;

    const firstCell = String(row[0] ?? '').trim().toLowerCase();
    if (/^side(board)?$/.test(firstCell)) { inSideboard = true; continue; }
    if (/^main(deck)?$/.test(firstCell)) { inSideboard = false; continue; }

    for (let ci = 0; ci < row.length - 1; ci++) {
      const maybeQty = parseInt(String(row[ci] ?? ''), 10);
      const maybeName = String(row[ci + 1] ?? '').trim();
      if (
        !isNaN(maybeQty) && maybeQty > 0 && maybeQty <= 99 &&
        maybeName.length > 0 && /^[A-Za-z]/.test(maybeName)
      ) {
        results.push({ name: maybeName, quantity: maybeQty, isSideboard: inSideboard, isFoil: false });
        break;
      }
    }

    if (row.length === 1) {
      const cell = String(row[0] ?? '').trim();
      const m = /^(\d+)\s+(.+)/.exec(cell);
      if (m != null) {
        results.push({ name: m[2]!.trim(), quantity: parseInt(m[1]!, 10), isSideboard: inSideboard, isFoil: false });
      }
    }
  }

  return results;
}

/** Whether a dropped or chosen file is a plain-text card list. */
function isTextList(file: File): boolean {
  return /\.txt$/i.test(file.name) || file.type === 'text/plain';
}

/** Rows from a plain-text card list (see parseCardList). */
function parseTextList(text: string): ParsedRow[] {
  return parseCardList(text).map(line => ({
    name: line.name,
    quantity: line.quantity,
    isSideboard: line.section === 'side',
    isFoil: line.isFoil,
    isCommander: line.section === 'commander',
    setCode: line.setCode,
    collectorNumber: line.collectorNumber,
  }));
}

/**
 * The row that becomes the commander: one listed under a Commander header,
 * else the first line when it is a single main deck copy, which is where
 * the deck page export writes it.
 */
function guessCommanderUid(rows: MatchedRow[]): number | null {
  const explicit = rows.find(r => r.isCommander === true);
  if (explicit != null) return explicit.uid;
  const first = rows[0];
  return first != null && first.quantity === 1 && !first.isSideboard ? first.uid : null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Step = 'upload' | 'matching' | 'confirm' | 'importing' | 'done';

const ImportPage: React.FC = () => {
  const router = useRouter();
  const { currency, usdToEur } = useTheme();
  const [mode, setMode] = useState<'deck' | 'collection'>('deck');
  const [step, setStep] = useState<Step>('upload');
  const [deckTitle, setDeckTitle] = useState('Imported Deck');
  const [deckFormat, setDeckFormat] = useState('Standard');
  const [rows, setRows] = useState<MatchedRow[]>([]);
  const [progress, setProgress] = useState('');
  const [createdDeckId, setCreatedDeckId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [commanderUid, setCommanderUid] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const hasCommander = usesCommanderCard(deckFormat);

  const { data: formats = [] } = useQuery({
    queryKey: ['formats'],
    queryFn: fetchFormats,
  });

  useEffect(() => {
    if (formats.length === 0) return;
    if (!formats.some(f => f.name === deckFormat)) {
      setDeckFormat(formats[0]?.name ?? 'Standard');
    }
  }, [formats, deckFormat]);

  // ----- Step 1: File parsing + name matching -----

  const handleFile = useCallback(
    async (file: File): Promise<void> => {
      setError(null);
      const textList = isTextList(file);
      setProgress(textList ? 'Reading card list...' : 'Parsing spreadsheet...');
      setStep('matching');

      try {
        let parsed: ParsedRow[];
        if (textList) {
          parsed = parseTextList(await file.text());
          if (parsed.length === 0) {
            throw new Error(
              'Could not detect any cards in this text file. ' +
                'Expected lines like "4 Lightning Bolt", with the sideboard after a blank line.',
            );
          }
        } else {
          const buffer = await file.arrayBuffer();
          const wb = XLSX.read(buffer, { type: 'buffer' });

          // Use the first sheet.
          const sheetName = wb.SheetNames[0];
          if (sheetName == null) throw new Error('No sheets found in workbook.');
          const sheet = wb.Sheets[sheetName];
          if (sheet == null) throw new Error('Could not read sheet.');

          parsed = parseSheet(sheet);
          if (parsed.length === 0) {
            throw new Error(
              'Could not detect any cards in this spreadsheet. ' +
                'Expected rows with a quantity column and a card-name column.',
            );
          }
        }

        setProgress(
          `Found ${parsed.length} rows. Matching card names against library...`,
        );

        const matched: MatchedRow[] = [];
        for (const [uid, row] of parsed.entries()) {
          // Normalize smart/curly quotes to straight apostrophes so names like
          // "Prey\u2019s Vengeance" match Drupal\u2019s stored straight-apostrophe titles.
          const normalizedName = row.name
            .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
            .replace(/[\u201C\u201D\u201E\u201F]/g, '"');
          const lowerName = normalizedName.toLowerCase();
          let results = await findCardsByName(normalizedName);
          if (results.length === 0 && !normalizedName.includes(' // ')) {
            // Arena exports write only the front face of double-faced cards.
            results = (await findCardsByName(normalizedName, { contains: true }))
              .filter(r => r.attributes.title.toLowerCase().startsWith(`${lowerName} // `));
          }
          const sameCard = results.filter(r => {
            const title = r.attributes.title.toLowerCase();
            return title === lowerName || title.startsWith(`${lowerName} // `);
          });
          const setCode = row.setCode?.toLowerCase() ?? null;
          const listedPrinting = setCode == null
            ? undefined
            : sameCard.find(r =>
              (r.attributes.field_set_code ?? '').toLowerCase() === setCode
              && (row.collectorNumber == null || r.attributes.field_collector_number === row.collectorNumber),
            );
          // Cheapest printing first, in the row's finish; unpriced ones last.
          const price = (r: (typeof results)[number]): number | null =>
            bestPrice(r.attributes, currency, row.isFoil, usdToEur);
          const byPrice = (a: (typeof results)[number], b: (typeof results)[number]): number =>
            (price(a) ?? Infinity) - (price(b) ?? Infinity);
          const sortedSame = [...sameCard].sort(byPrice);
          const sorted = [...sortedSame, ...results.filter(r => !sameCard.includes(r)).sort(byPrice)];
          // A printing named in the list wins; otherwise the cheapest one.
          const best = listedPrinting ?? sorted[0];
          matched.push({
            ...row,
            uid,
            name: normalizedName,
            matchId: best?.id ?? null,
            matchTitle: best?.attributes.title ?? null,
            candidates: sorted.map(r => {
              const set = (r.attributes.field_set_code ?? '').toUpperCase();
              const number = r.attributes.field_collector_number ?? '';
              const printing = set === '' ? '' : ` (${set}${number !== '' ? ` #${number}` : ''})`;
              const cost = price(r);
              return {
                id: r.id,
                title: r.attributes.title,
                label: `${r.attributes.title}${printing}${cost != null ? ` — ${formatPrice(cost, currency)}` : ''}`,
              };
            }),
          });
        }

        setRows(matched);
        setCommanderUid(guessCommanderUid(matched));
        // A Commander section, or exactly 100 cards, is a commander deck.
        const total = parsed.filter(r => !r.isSideboard).reduce((sum, r) => sum + r.quantity, 0);
        if (parsed.some(r => r.isCommander === true) || total === 100) {
          const commanderFormat = formats.find(f => f.name.toLowerCase() === 'commander');
          if (commanderFormat != null) setDeckFormat(commanderFormat.name);
        }
        setProgress('');
        setStep('confirm');
        setDeckTitle(file.name.replace(/\.[^.]+$/, ''));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setStep('upload');
        setProgress('');
      }
    },
    [formats, currency, usdToEur],
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

    const commanderRow = hasCommander
      ? rows.find(r => r.uid === commanderUid && r.matchId != null) ?? null
      : null;
    const toImport = rows.filter(r => r.matchId != null && r !== commanderRow);
    if (toImport.length === 0 && commanderRow == null) {
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
        commanderId: commanderRow?.matchId ?? null,
      });

      setProgress(`Adding ${toImport.length} cards...`);
      await importCardToDeck(
        deck.id,
        toImport.map(row => ({
          cardId: row.matchId!,
          cardName: row.matchTitle ?? row.name,
          quantity: row.quantity,
          isSideboard: row.isSideboard,
          isFoil: row.isFoil,
        })),
      );

      setCreatedDeckId(slugify(deckTitle));
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
    <main style={{ padding: '1.5rem', maxWidth: 1000 }}>
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/" style={{ color: 'var(--accent)' }}>Home</Link>
      </p>
      <h1 style={{ marginTop: 0 }}>{mode === 'deck' ? 'Import deck' : 'Import collection CSV'}</h1>

      <div role="tablist" style={{ display: 'flex', gap: 8, marginBottom: '1rem' }}>
        {(['deck', 'collection'] as const).map(m => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => setMode(m)}
            style={{ fontWeight: mode === m ? 'bold' : 'normal' }}
          >
            {m === 'deck' ? 'Deck (XLSX / TXT)' : 'Collection (CSV)'}
          </button>
        ))}
      </div>

      {mode === 'collection' ? (
        <CollectionCsvImport />
      ) : (
      <>

      {error != null && (
        <p
          style={{
            color: 'var(--ink)',
            background: 'color-mix(in srgb, var(--neg) 15%, transparent)',
            border: '1px solid var(--neg)',
            padding: '0.75rem',
            borderRadius: 4,
          }}
        >
          {error}
        </p>
      )}

      {progress !== '' && (
        <p style={{ color: 'var(--ink-2)', fontStyle: 'italic' }}>{progress}</p>
      )}

      {/* Upload step */}
      {step === 'upload' && (
        <div>
          <div
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            style={{
              border: '2px dashed var(--line-2)',
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
              <strong>Magic Deck Spreadsheet v2.xlsx</strong> or a{' '}
              <strong>.txt card list</strong> here
            </p>
            <p style={{ margin: '0.5rem 0 0', color: 'var(--ink-2)' }}>
              or click to browse
            </p>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.ods,.csv,.txt"
            style={{ display: 'none' }}
            onChange={handleFileInput}
          />
          <p style={{ fontSize: '0.85rem', color: 'var(--ink-2)' }}>
            Spreadsheets: the parser looks for columns named <em>Name</em> and{' '}
            <em>Quantity</em>, or rows with a numeric quantity in the first
            column followed by the card name. A row or cell containing
            &ldquo;Sideboard&rdquo; marks the sideboard section.
          </p>
          <p style={{ fontSize: '0.85rem', color: 'var(--ink-2)' }}>
            Text lists: one card per line as <em>4 Lightning Bolt</em>, with the
            sideboard after a blank line &mdash; the format the deck page&rsquo;s
            &ldquo;Copy for Cardmarket&rdquo; writes. Arena and Moxfield exports
            (Commander / Deck / Sideboard headers, set codes, *F* foils) work too.
            In commander formats the Commander section, or else the first line,
            becomes the commander.
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
                color: 'var(--ink)',
                background: 'color-mix(in srgb, var(--warn) 15%, transparent)',
                border: '1px solid var(--warn)',
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
                {formats.map(f => (
                  <option key={f.name} value={f.name}>
                    {f.name}
                  </option>
                ))}
              </select>
            </label>
            {hasCommander && (
              <label>
                Commander
                <select
                  value={commanderUid ?? ''}
                  onChange={e => setCommanderUid(e.target.value === '' ? null : Number(e.target.value))}
                  style={{ display: 'block', marginTop: 4, maxWidth: 320 }}
                >
                  <option value="">-- none --</option>
                  {rows
                    .filter(r => r.matchId != null && !r.isSideboard)
                    .map(r => (
                      <option key={r.uid} value={r.uid}>
                        {r.matchTitle ?? r.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
          </div>

          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.85rem',
            }}
          >
            <thead>
              <tr style={{ background: 'var(--bg-2)', color: 'var(--ink)', borderBottom: '1px solid var(--line-2)' }}>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Qty</th>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Parsed name</th>
                <th style={{ padding: '0.4rem', textAlign: 'left' }}>Matched card</th>
                <th style={{ padding: '0.4rem' }}>SB</th>
                <th style={{ padding: '0.4rem' }}>Foil</th>
                <th style={{ padding: '0.4rem' }}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.uid}
                  style={{
                    borderTop: '1px solid var(--line)',
                    background: row.matchId == null
                      ? 'color-mix(in srgb, var(--neg) 15%, transparent)'
                      : undefined,
                  }}
                >
                  <td style={{ padding: '0.3rem 0.4rem' }}>{row.quantity}</td>
                  <td style={{ padding: '0.3rem 0.4rem' }}>{row.name}</td>
                  <td style={{ padding: '0.3rem 0.4rem' }}>
                    {row.candidates.length > 0 ? (
                      <select
                        value={row.matchId ?? ''}
                        onChange={e => updateMatch(i, e.target.value)}
                        style={{ maxWidth: 440 }}
                      >
                        <option value="">-- unmatched --</option>
                        {row.candidates.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span style={{ color: 'var(--neg)' }}>No candidates found</span>
                    )}
                  </td>
                  <td style={{ padding: '0.3rem 0.4rem', textAlign: 'center' }}>
                    {hasCommander && row.uid === commanderUid ? 'CMD' : row.isSideboard ? 'SB' : ''}
                  </td>
                  <td style={{ padding: '0.3rem 0.4rem', textAlign: 'center' }}>
                    {row.isFoil ? 'F' : ''}
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
              {hasCommander && commanderUid != null ? ' (1 as commander)' : ''}
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
          <p style={{ color: 'var(--pos)', fontWeight: 'bold' }}>
            Deck imported successfully.
          </p>
          <button
            type="button"
            onClick={() => void router.push(`/decks/${createdDeckId}`)}
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
      </>
      )}
    </main>
  );
};

export default ImportPage;
