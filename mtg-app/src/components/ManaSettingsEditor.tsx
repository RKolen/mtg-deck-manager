import React, { useState } from 'react';
import { COLOR_LABEL, type MtgColor } from '../utils/deckAnalysis';
import {
  DEFAULT_MANA_SETTINGS,
  resolveManaSettings,
  type CardOverride,
  type ManaSettings,
  type ProducerRatio,
} from '../utils/landBase';

/** A card that can get an override: its title and printed cost. */
export interface OverridableCard {
  title: string;
  manaCost: string;
  /** Has an alternate cost, so it can wait unless told otherwise. */
  alternateCost: boolean;
}

interface ManaSettingsEditorProps {
  /** The deck's unsaved settings (differences from the defaults). */
  draft: Partial<ManaSettings>;
  onChange: (draft: Partial<ManaSettings>) => void;
  deckColors: MtgColor[];
  /** Non-land cards of the deck (main deck, sideboard and commander). */
  cards: OverridableCard[];
  /** Cards that may cost less than their mana value, without an override. */
  alternateCosts: { title: string; reason: string }[];
  /** Non-basic lands in the deck, for the always-keep list. */
  deckLands: string[];
  /** True when the draft or land count differs from what is saved. */
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

type RatioKey = 'dork' | 'rock' | 'ramp2' | 'ramp3' | 'treasure' | 'mdfc' | 'mdfcMythic';

const RATIO_ROWS: { key: RatioKey; label: string }[] = [
  { key: 'dork', label: 'Mana dork' },
  { key: 'rock', label: 'Mana rock' },
  { key: 'ramp2', label: 'Ramp spell, 2 mana or less' },
  { key: 'ramp3', label: 'Ramp spell, 3 mana' },
  { key: 'treasure', label: 'Treasure maker' },
  { key: 'mdfc', label: 'Spell // land card' },
  { key: 'mdfcMythic', label: 'Mythic spell // land card' },
];

const CELL: React.CSSProperties = { padding: '0.25rem 0.5rem', color: 'var(--ink)' };
const HEAD: React.CSSProperties = { ...CELL, background: 'var(--bg-2)', textAlign: 'left' };
const ROW: React.CSSProperties = { borderTop: '1px solid var(--line)' };
const NUMBER: React.CSSProperties = { width: '4.5rem' };

/** Parses a number input; empty or invalid gives null. */
function parseNumber(value: string): number | null {
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Per-deck land base settings: Karsten's ratios, fetch values, minimum
 * basics, the sideboard switch and per-card overrides. Edits change the
 * suggestion straight away; Save stores them on the deck.
 */
const ManaSettingsEditor: React.FC<ManaSettingsEditorProps> = ({
  draft,
  onChange,
  deckColors,
  cards,
  alternateCosts,
  deckLands,
  dirty,
  saving,
  onSave,
  onDiscard,
}) => {
  const [addTitle, setAddTitle] = useState('');
  const full = resolveManaSettings(draft);
  const overrides = draft.cards ?? {};

  function setRatio(key: RatioKey, field: keyof ProducerRatio, value: string): void {
    const n = parseNumber(value);
    onChange({ ...draft, [key]: { ...full[key], [field]: n ?? DEFAULT_MANA_SETTINGS[key][field] } });
  }

  function resetRatios(): void {
    const next = { ...draft };
    for (const { key } of RATIO_ROWS) {
      delete next[key];
    }
    delete next.fetchPartial;
    delete next.fetchesPerTarget;
    onChange(next);
  }

  function setMinBasics(color: MtgColor, value: string): void {
    const n = Math.max(0, Math.round(parseNumber(value) ?? 0));
    onChange({ ...draft, minBasics: { ...full.minBasics, [color]: n } });
  }

  function setOverride(title: string, change: Partial<CardOverride>): void {
    onChange({ ...draft, cards: { ...overrides, [title]: { ...(overrides[title] ?? {}), ...change } } });
  }

  function removeOverride(title: string): void {
    const next = { ...overrides };
    delete next[title];
    onChange({ ...draft, cards: next });
  }

  const costOf = new Map(cards.map(c => [c.title, c.manaCost]));
  const hasAlternateCost = new Set(cards.filter(c => c.alternateCost).map(c => c.title));
  /** Can-wait as the planner reads it: the setting, else the alternate-cost default. */
  const waits = (title: string, o: CardOverride): boolean => o.canWait ?? (
    hasAlternateCost.has(title)
    && (o.cost == null || o.cost.trim() === '')
    && (o.turn == null || o.turn <= 0)
    && o.ignore !== true
  );
  const overrideTitles = Object.keys(overrides).sort((a, b) => a.localeCompare(b));
  const addable = [...new Set(cards.map(c => c.title))]
    .filter(t => overrides[t] == null)
    .sort((a, b) => a.localeCompare(b));
  const ratiosChanged = RATIO_ROWS.some(({ key }) => draft[key] != null)
    || draft.fetchPartial != null || draft.fetchesPerTarget != null;

  return (
    <details style={{ margin: '0 0 1rem', fontSize: '0.85rem' }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
        Settings for this deck{dirty ? ' (unsaved changes)' : ''}
      </summary>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', margin: '0.5rem 0' }}>
        <button type="button" className="btn-accent" onClick={onSave} disabled={!dirty || saving}>
          {saving ? 'Saving...' : 'Save settings'}
        </button>
        <button type="button" onClick={onDiscard} disabled={!dirty || saving}>Discard changes</button>
        <span className="dim">Changes show in the suggestion straight away; Save keeps them for this deck.</span>
      </div>

      <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Non-land mana</h4>
      <p className="dim" style={{ margin: '0 0 0.25rem' }}>
        Karsten&apos;s values. Land share counts towards the land count formula (cheap cards only);
        source counts towards each colour it makes, for spells of at least the given mana value.
      </p>
      <table style={{ borderCollapse: 'collapse', marginBottom: '0.5rem' }}>
        <thead>
          <tr>
            <th style={HEAD}>Card</th>
            <th style={HEAD}>Land share</th>
            <th style={HEAD}>Source</th>
            <th style={HEAD}>For mana value</th>
          </tr>
        </thead>
        <tbody>
          {RATIO_ROWS.map(({ key, label }) => (
            <tr key={key} style={ROW}>
              <td style={CELL}>{label}</td>
              {(['land', 'source', 'minMv'] as const).map(field => (
                <td key={field} style={CELL}>
                  <input
                    type="number"
                    min={0}
                    step={field === 'minMv' ? 1 : 0.05}
                    value={full[key][field]}
                    onChange={e => setRatio(key, field, e.target.value)}
                    style={NUMBER}
                    aria-label={`${label} ${field}`}
                  />
                  {field === 'minMv' && <span className="dim"> +</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Fetches</h4>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
        <label title="A fetch with fewer lands of a colour to find than the spell has pips of it.">
          Value with too few targets:{' '}
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={full.fetchPartial}
            onChange={e => onChange({ ...draft, fetchPartial: parseNumber(e.target.value) ?? DEFAULT_MANA_SETTINGS.fetchPartial })}
            style={NUMBER}
          />
        </label>
        <label title="Fetches give at most this many sources of a colour per fetchable land of that colour.">
          Fetches per land they can find:{' '}
          <input
            type="number"
            min={0.5}
            step={0.5}
            value={full.fetchesPerTarget}
            onChange={e => onChange({
              ...draft,
              fetchesPerTarget: Math.max(0.5, parseNumber(e.target.value) ?? DEFAULT_MANA_SETTINGS.fetchesPerTarget),
            })}
            style={NUMBER}
          />
        </label>
        <button type="button" onClick={resetRatios} disabled={!ratiosChanged}>Reset ratios to Karsten</button>
      </div>

      <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Minimum basics</h4>
      <p className="dim" style={{ margin: '0 0 0.25rem' }}>
        Keeps each colour castable under Blood Moon or Back to Basics, or after a Wasteland.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
        {deckColors.map(color => (
          <label key={color}>
            {COLOR_LABEL[color]}:{' '}
            <input
              type="number"
              min={0}
              step={1}
              value={full.minBasics[color]}
              onChange={e => setMinBasics(color, e.target.value)}
              style={{ width: '3.5rem' }}
            />
          </label>
        ))}
      </div>

      {deckLands.length > 0 && (
        <>
          <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Lands to always keep</h4>
          <p className="dim" style={{ margin: '0 0 0.25rem' }}>
            For lands worth more than their mana, which the suggestion cannot see (Karakas in a
            control deck).
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem' }}>
            {deckLands.map(title => (
              <label key={title}>
                <input
                  type="checkbox"
                  checked={full.keepLands.includes(title)}
                  onChange={e => onChange({
                    ...draft,
                    keepLands: e.target.checked
                      ? [...full.keepLands, title]
                      : full.keepLands.filter(t => t !== title),
                  })}
                />{' '}
                {title}
              </label>
            ))}
          </div>
        </>
      )}

      <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Sideboard</h4>
      <label>
        <input
          type="checkbox"
          checked={full.includeSideboard}
          onChange={e => onChange({ ...draft, includeSideboard: e.target.checked })}
        />{' '}
        Count the sideboard&apos;s colour needs too
      </label>

      <h4 style={{ margin: '0.75rem 0 0.25rem' }}>Cards</h4>
      <p className="dim" style={{ margin: '0 0 0.25rem' }}>
        How a card is really cast in this deck. Cost replaces the printed cost (a delve spell for{' '}
        {'{G}'}); turn moves it later without changing the cost; can wait means it does not have to be
        cast on curve and sets no colour target; ignore is for cards never cast from hand. Cards that
        may cost less count as can wait until you say how they are cast.
      </p>
      {alternateCosts.length > 0 && (
        <div style={{ margin: '0 0 0.5rem' }}>
          May cost less:{' '}
          {alternateCosts.map(a => (
            <button
              key={a.title}
              type="button"
              onClick={() => setOverride(a.title, {})}
              style={{ margin: '0 0.25rem 0.25rem 0' }}
              title={a.reason}
            >
              {a.title}
            </button>
          ))}
        </div>
      )}
      {overrideTitles.length > 0 && (
        <table style={{ borderCollapse: 'collapse', marginBottom: '0.5rem' }}>
          <thead>
            <tr>
              <th style={HEAD}>Card</th>
              <th style={HEAD}>Cost</th>
              <th style={HEAD}>Turn</th>
              <th style={HEAD}>Can wait</th>
              <th style={HEAD}>Ignore</th>
              <th style={HEAD} />
            </tr>
          </thead>
          <tbody>
            {overrideTitles.map(title => {
              const o = overrides[title]!;
              return (
                <tr key={title} style={ROW}>
                  <td style={CELL}>{title}</td>
                  <td style={CELL}>
                    <input
                      type="text"
                      value={o.cost ?? ''}
                      placeholder={costOf.get(title) ?? ''}
                      onChange={e => setOverride(title, { cost: e.target.value === '' ? null : e.target.value })}
                      style={{ width: '7rem' }}
                      aria-label={`${title} cost`}
                    />
                  </td>
                  <td style={CELL}>
                    <input
                      type="number"
                      min={1}
                      max={7}
                      value={o.turn ?? ''}
                      placeholder="auto"
                      onChange={e => setOverride(title, { turn: parseNumber(e.target.value) })}
                      style={{ width: '3.5rem' }}
                      aria-label={`${title} turn`}
                    />
                  </td>
                  <td style={CELL}>
                    <input
                      type="checkbox"
                      checked={waits(title, o)}
                      onChange={e => setOverride(title, { canWait: e.target.checked })}
                      aria-label={`${title} can wait`}
                    />
                  </td>
                  <td style={CELL}>
                    <input
                      type="checkbox"
                      checked={o.ignore === true}
                      onChange={e => setOverride(title, { ignore: e.target.checked })}
                      aria-label={`${title} ignore`}
                    />
                  </td>
                  <td style={CELL}>
                    <button type="button" onClick={() => removeOverride(title)}>Remove</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <select value={addTitle} onChange={e => setAddTitle(e.target.value)} aria-label="Card to add">
          <option value="">Choose a card...</option>
          {addable.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button
          type="button"
          disabled={addTitle === ''}
          onClick={() => { setOverride(addTitle, {}); setAddTitle(''); }}
        >
          Add card
        </button>
      </div>
    </details>
  );
};

export default ManaSettingsEditor;
