import React, { useRef, useState } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import * as XLSX from 'xlsx';
import { importCollection } from '../services/drupalApi';
import { invalidateInventoryQueries } from '../services/queryCache';
import { slugify } from '../utils/slugify';
import type { CollectionImportResult, CollectionImportRow } from '../types/drupal';

/** Header aliases, lower-cased. First match wins. */
const COLUMNS: Record<string, string[]> = {
  quantity: ['quantity', 'qty', 'count', 'amount'],
  name: ['name', 'card name', 'card'],
  setCode: ['set code', 'set', 'edition', 'edition code'],
  collectorNumber: ['collector number', 'card number', 'number', 'cn'],
  foil: ['foil', 'finish', 'printing finish'],
  scryfallId: ['scryfall id', 'scryfall_id', 'scryfallid'],
  quantityTrade: ['quantity trade', 'trade quantity', 'tradelist count', 'for trade', 'trade'],
  binderLocation: ['binder location', 'binder'],
  location: ['location'],
  sheet: ['sheet', 'page'],
  pocket: ['pocket', 'slot'],
};

type Column = keyof typeof COLUMNS;

interface ParsedCsv {
  rows: CollectionImportRow[];
  /** Columns that were recognised, for the summary line. */
  found: Column[];
}

function isFoilValue(value: string): boolean {
  const v = value.trim().toLowerCase();
  return v !== '' && !['0', 'no', 'false', 'normal', 'nonfoil', 'non-foil', 'regular'].includes(v);
}

/**
 * Parses a collection CSV into import rows.
 *
 * Location, Sheet and Pocket columns are joined into the binder location
 * ("Album 1, sheet 3, pocket 7") when no Binder Location column exists.
 */
function parseCollectionCsv(text: string): ParsedCsv {
  const wb = XLSX.read(text, { type: 'string', raw: true });
  const sheet = wb.Sheets[wb.SheetNames[0] ?? ''];
  if (sheet == null) {
    return { rows: [], found: [] };
  }
  const table = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false, defval: '' }) as string[][];
  const header = (table[0] ?? []).map(h => String(h).trim().toLowerCase());
  const index = {} as Record<Column, number>;
  const found: Column[] = [];
  for (const key of Object.keys(COLUMNS) as Column[]) {
    index[key] = -1;
    for (const alias of COLUMNS[key]!) {
      const i = header.indexOf(alias);
      if (i >= 0) {
        index[key] = i;
        found.push(key);
        break;
      }
    }
  }

  const cell = (row: string[], key: Column): string =>
    index[key] >= 0 ? String(row[index[key]] ?? '').trim() : '';

  const rows: CollectionImportRow[] = [];
  for (const raw of table.slice(1)) {
    const name = cell(raw, 'name');
    const scryfallId = cell(raw, 'scryfallId');
    if (name === '' && scryfallId === '') {
      continue;
    }
    const qtyRaw = cell(raw, 'quantity');
    const quantity = qtyRaw === '' ? 1 : Number.parseInt(qtyRaw, 10);
    if (!Number.isFinite(quantity) || quantity < 1) {
      continue;
    }
    let binderLocation = cell(raw, 'binderLocation');
    if (binderLocation === '' && cell(raw, 'location') !== '') {
      binderLocation = [
        cell(raw, 'location'),
        cell(raw, 'sheet') !== '' ? `sheet ${cell(raw, 'sheet')}` : '',
        cell(raw, 'pocket') !== '' ? `pocket ${cell(raw, 'pocket')}` : '',
      ]
        .filter(Boolean)
        .join(', ');
    }
    const tradeRaw = cell(raw, 'quantityTrade');
    rows.push({
      name: name || null,
      quantity,
      foil: isFoilValue(cell(raw, 'foil')),
      scryfallId: scryfallId || null,
      setCode: cell(raw, 'setCode') || null,
      collectorNumber: cell(raw, 'collectorNumber') || null,
      quantityTrade: tradeRaw === '' ? null : Math.max(0, Number.parseInt(tradeRaw, 10) || 0),
      binderLocation: binderLocation || null,
    });
  }
  return { rows, found };
}

const STATUS_LABEL: Record<CollectionImportResult['status'], string> = {
  matched: 'Will add',
  added: 'Added',
  skipped: 'Skipped',
  not_found: 'Not found',
};

/**
 * Collection import from CSV: dry run first, then apply.
 *
 * Rows are matched by Scryfall ID, then set + collector number, then set
 * name, then card name. Quantities are added to what is already owned.
 */
const CollectionCsvImport: React.FC = () => {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState('');
  const [rows, setRows] = useState<CollectionImportRow[]>([]);
  const [found, setFound] = useState<Column[]>([]);
  const [results, setResults] = useState<CollectionImportResult[] | null>(null);
  const [allForTrade, setAllForTrade] = useState(false);
  const [busy, setBusy] = useState(false);
  const [applied, setApplied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function payload(): CollectionImportRow[] {
    return allForTrade ? rows.map(r => ({ ...r, quantityTrade: r.quantity })) : rows;
  }

  async function handleFile(file: File): Promise<void> {
    setError(null);
    setResults(null);
    setApplied(false);
    setFileName(file.name);
    const parsed = parseCollectionCsv(await file.text());
    setRows(parsed.rows);
    setFound(parsed.found);
    if (parsed.rows.length === 0) {
      setError('No card rows found. The CSV needs a Name or Scryfall ID column.');
      return;
    }
    await run(parsed.rows, false);
  }

  async function run(list: CollectionImportRow[], apply: boolean): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      setResults(await importCollection(list, apply));
      if (apply) {
        setApplied(true);
        await invalidateInventoryQueries(qc);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed.');
    } finally {
      setBusy(false);
    }
  }

  const counts = (results ?? []).reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});
  const matchedCopies = (results ?? [])
    .filter(r => r.status === 'matched' || r.status === 'added')
    .reduce((sum, r) => sum + (rows[r.row]?.quantity ?? 0), 0);

  return (
    <section>
      <p style={{ fontSize: '0.85rem', opacity: 0.85, marginTop: 0 }}>
        Adds the cards in a CSV to your collection. Recognised columns: Quantity/Count, Name, Set Code,
        Collector Number, Foil, Scryfall ID, Quantity Trade, Binder Location (or Location + Sheet + Pocket).
        A dry run shows what will match before anything is saved.
      </p>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
          Choose CSV...
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: 'none' }}
          onChange={e => {
            const file = e.target.files?.[0];
            e.target.value = '';
            if (file != null) void handleFile(file);
          }}
        />
        {fileName !== '' && (
          <span style={{ fontSize: '0.85rem' }}>
            {fileName}: {rows.length} rows{found.length > 0 ? ` (columns: ${found.join(', ')})` : ''}
          </span>
        )}
      </div>

      {rows.length > 0 && !applied && (
        <label style={{ display: 'block', marginBottom: '0.75rem', fontSize: '0.9rem' }}>
          <input type="checkbox" checked={allForTrade} onChange={e => setAllForTrade(e.target.checked)} /> Mark
          every imported copy as for trade (trade binder import)
        </label>
      )}

      {error != null && (
        <p role="alert" style={{ color: 'var(--neg)', margin: '0 0 0.75rem' }}>
          {error}
        </p>
      )}
      {busy && <p>Working&hellip;</p>}

      {results != null && (
        <>
          <p style={{ fontWeight: 'bold', margin: '0 0 0.5rem' }}>
            {applied ? 'Imported' : 'Dry run'}: {(counts.matched ?? 0) + (counts.added ?? 0)} rows ({matchedCopies}{' '}
            copies) {applied ? 'added' : 'will be added'}
            {counts.not_found ? `, ${counts.not_found} not found` : ''}
            {counts.skipped ? `, ${counts.skipped} skipped` : ''}.
          </p>
          {!applied && (
            <div style={{ display: 'flex', gap: 8, marginBottom: '0.75rem' }}>
              <button type="button" disabled={busy || matchedCopies === 0} onClick={() => void run(payload(), true)}>
                Add {matchedCopies} copies to collection
              </button>
              <button type="button" disabled={busy} onClick={() => void run(payload(), false)}>
                Re-run dry run
              </button>
            </div>
          )}
          {applied && (
            <p>
              <Link href="/collection" style={{ color: 'var(--accent)' }}>
                Open collection
              </Link>
            </p>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--line)', textAlign: 'left' }}>
                <th style={{ padding: '0.3rem' }}>Qty</th>
                <th style={{ padding: '0.3rem' }}>CSV row</th>
                <th style={{ padding: '0.3rem' }}>Matched printing</th>
                <th style={{ padding: '0.3rem' }}>By</th>
                <th style={{ padding: '0.3rem' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => {
                const src = rows[r.row];
                const bad = r.status === 'not_found' || r.status === 'skipped';
                return (
                  <tr
                    key={r.row}
                    style={{ borderBottom: '1px solid var(--line)', color: bad ? 'var(--neg)' : undefined }}
                  >
                    <td style={{ padding: '0.25rem 0.3rem' }}>
                      {src?.quantity}
                      {src?.foil ? ' F' : ''}
                    </td>
                    <td style={{ padding: '0.25rem 0.3rem' }}>
                      {src?.name ?? src?.scryfallId}
                      {src?.setCode ? ` [${src.setCode.toUpperCase()}${src.collectorNumber ? ` #${src.collectorNumber}` : ''}]` : ''}
                      {src?.binderLocation ? (
                        <span style={{ opacity: 0.7 }}> · {src.binderLocation}</span>
                      ) : null}
                    </td>
                    <td style={{ padding: '0.25rem 0.3rem' }}>
                      {r.card != null ? (
                        <Link
                          href={`/collection/card/${slugify(r.card.title)}`}
                          style={{ color: 'inherit' }}
                        >
                          {r.card.title} [{(r.card.setCode ?? '').toUpperCase()} #{r.card.collectorNumber}]
                        </Link>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td style={{ padding: '0.25rem 0.3rem' }}>{r.matchedBy}</td>
                    <td style={{ padding: '0.25rem 0.3rem' }}>{STATUS_LABEL[r.status]}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
};

export default CollectionCsvImport;
