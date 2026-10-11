/**
 * Random deck generator page.
 *
 * Builds a deck from the collection around a random (or chosen) commander:
 * role quotas and curve from a template, synergy from a FitScorer, lands from
 * the land base planner. Nothing is saved until "Save as new deck".
 */

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createDeck,
  fetchDeckBuildPool,
  findCardsByName,
  importCardToDeck,
} from '../../services/drupalApi';
import { invalidateInventoryQueries } from '../../services/queryCache';
import { CARD_ROLE_LABEL, type CardRole } from '../../utils/cardRoles';
import { isLegalCommanderCard } from '../../utils/deckAnalysis';
import {
  eligibleCommanders,
  fitsIdentity,
  generateDeck,
  identityColors,
  newSeed,
  seededRandom,
  weightedPick,
  type GeneratedDeck,
} from '../../utils/deckGenerator';
import { CURVE_BUCKETS, DECK_TEMPLATES, templateById } from '../../utils/deckTemplates';
import { RuleBasedFitScorer, seedThemes } from '../../utils/fitScore';
import { planLandBase, type LandBasePlan } from '../../utils/landBase';
import { toGenCard, toLandOption } from '../../utils/poolAdapters';
import { slugify } from '../../utils/slugify';

const scorer = new RuleBasedFitScorer();

const CELL: React.CSSProperties = { padding: '0.25rem 0.6rem', color: 'var(--ink)' };
const HEAD: React.CSSProperties = { ...CELL, background: 'var(--bg-2)', textAlign: 'left' };
const ROW: React.CSSProperties = { borderTop: '1px solid var(--line)' };

const REASON_LABEL: Record<CardRole | 'synergy', string> = {
  ...CARD_ROLE_LABEL,
  synergy: 'Synergy and curve',
};

interface Result {
  deck: GeneratedDeck;
  lands: LandBasePlan;
  seed: number;
  themes: string[];
}

const GeneratePage: React.FC = () => {
  const router = useRouter();
  const qc = useQueryClient();
  const [templateId, setTemplateId] = useState(DECK_TEMPLATES[0]!.id);
  const template = templateById(templateId);
  const [commanderTitle, setCommanderTitle] = useState('');
  const [includeUsed, setIncludeUsed] = useState(false);
  const [chaos, setChaos] = useState(0.3);
  const [landCount, setLandCount] = useState(template.defaultLands);
  const [seed, setSeed] = useState(() => newSeed());
  const [result, setResult] = useState<Result | null>(null);

  const spells = useQuery({
    queryKey: ['deckBuildPool', 'spells', 'COLLECTION', template.legalIn],
    queryFn: () => fetchDeckBuildPool({ source: 'COLLECTION', lands: false, legalIn: template.legalIn }),
    staleTime: 10 * 60 * 1000,
  });
  const lands = useQuery({
    queryKey: ['deckBuildPool', 'lands', 'COLLECTION', template.legalIn],
    queryFn: () => fetchDeckBuildPool({ source: 'COLLECTION', lands: true, legalIn: template.legalIn }),
    staleTime: 10 * 60 * 1000,
  });

  const pool = useMemo(
    () => (spells.data ?? []).map(p => toGenCard(p, includeUsed)),
    [spells.data, includeUsed],
  );
  const commanders = useMemo(() => {
    const candidates = pool.filter(c => isLegalCommanderCard(c.typeLine, c.cmc, c.oracleText, template.format));
    return eligibleCommanders(candidates, pool, template.minPool)
      .sort((a, b) => a.commander.title.localeCompare(b.commander.title));
  }, [pool, template]);

  function generate(useSeed: number): void {
    const rand = seededRandom(useSeed);
    const picked = commanderTitle === ''
      ? weightedPick(commanders, () => 1, rand)
      : commanders.find(c => c.commander.title === commanderTitle) ?? null;
    if (picked == null) {
      setResult(null);
      return;
    }
    const commander = picked.commander;
    const fit = scorer.scoreSync(commander, pool);
    const spellCount = Math.max(1, template.deckSize - landCount);
    const deck = generateDeck({
      template,
      commander,
      pool,
      fit,
      spellCount,
      chaos,
      seed: useSeed,
    });

    const colors = identityColors(commander);
    const landOptions = (lands.data ?? [])
      .filter(p => fitsIdentity(p.card.attributes.field_color_identity ?? [], commander.colorIdentity))
      .map(p => toLandOption(p, includeUsed, false, null));
    const landPlan = planLandBase({
      spells: deck.cards.map(c => ({ ...c.card, producedMana: c.card.producedMana ?? [], quantity: 1 })),
      commander: { ...commander, producedMana: [], quantity: 1 },
      currentLands: [],
      options: landOptions,
      deckColors: colors,
      deckSize: template.deckSize,
      maxCopies: template.maxCopies,
      commanderFormat: true,
      landCountOverride: template.deckSize - deck.cards.length,
    });

    setResult({ deck, lands: landPlan, seed: useSeed, themes: seedThemes(commander).map(t => t.label) });
  }

  const save = useMutation({
    mutationFn: async (r: Result) => {
      const title = `${r.deck.commander.title} (random ${r.seed})`;
      const notes = [
        `Random deck from the collection (template: ${template.label}, seed ${r.seed}, chaos ${chaos}).`,
        r.themes.length > 0 ? `Themes: ${r.themes.join(', ')}.` : '',
        `Roles: ${Object.entries(r.deck.roleCounts).map(([k, v]) => `${k} ${v}`).join(', ')}.`,
      ].filter(s => s !== '').join('\n');
      const deck = await createDeck({
        title,
        field_format: template.format,
        field_notes: notes,
        commanderId: r.deck.commander.id,
      });
      await importCardToDeck(deck.id, r.deck.cards.map(c => ({
        cardId: c.card.id,
        quantity: 1,
        isSideboard: false,
        cardName: c.card.title,
      })));
      for (const pick of r.lands.picks) {
        let cardId = pick.option.cardId;
        if (cardId == null) {
          const found = await findCardsByName(pick.option.land.title);
          cardId = (found.find(c => c.attributes.title === pick.option.land.title) ?? found[0])?.id ?? null;
        }
        if (cardId != null) {
          await importCardToDeck(deck.id, [{
            cardId,
            quantity: pick.quantity,
            isSideboard: false,
            cardName: pick.option.land.title,
          }]);
        }
      }
      return title;
    },
    onSuccess: async (title: string) => {
      await invalidateInventoryQueries(qc);
      await qc.invalidateQueries({ queryKey: ['decks'] });
      void router.push(`/decks/${slugify(title)}`);
    },
  });

  const loading = spells.isLoading || lands.isLoading;
  const loadError = spells.error ?? lands.error;
  const totalCards = result != null
    ? result.deck.cards.length + result.lands.picks.reduce((s, p) => s + p.quantity, 0)
    : 0;

  return (
    <main style={{ padding: '1.5rem', maxWidth: 1200, color: 'var(--ink)' }}>
      <p style={{ margin: '0 0 1rem' }}>
        <Link href="/decks" style={{ color: 'var(--accent)' }}>Back to decks</Link>
      </p>
      <h1 style={{ marginTop: 0 }}>Random deck from your collection</h1>
      <p style={{ fontSize: '0.9rem', maxWidth: 760 }}>
        Picks a commander you own, then fills the deck with owned cards: a set number of ramp, card draw,
        removal and board wipes, the rest chosen for synergy with the commander and a sensible mana curve.
        Lands come from the land base suggester. The same seed always gives the same deck.
      </p>

      {loading && <p>Loading your collection (this can take a few seconds)...</p>}
      {loadError != null && (
        <p style={{ color: '#c00' }}>
          Could not load the collection: {loadError instanceof Error ? loadError.message : 'unknown error'}
        </p>
      )}

      {!loading && loadError == null && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem 1.5rem', marginBottom: '1rem' }}>
          <label>
            Template
            <select
              value={templateId}
              onChange={e => {
                setTemplateId(e.target.value);
                setLandCount(templateById(e.target.value).defaultLands);
              }}
              style={{ display: 'block', width: '100%' }}
            >
              {DECK_TEMPLATES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          </label>
          <label>
            Commander ({commanders.length} with enough cards)
            <select
              value={commanderTitle}
              onChange={e => setCommanderTitle(e.target.value)}
              style={{ display: 'block', width: '100%' }}
            >
              <option value="">Random</option>
              {commanders.map(c => (
                <option key={c.commander.title} value={c.commander.title}>
                  {c.commander.title} ({c.poolSize} cards)
                </option>
              ))}
            </select>
          </label>
          <label>
            Randomness: {chaos.toFixed(2)}
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={chaos}
              onChange={e => setChaos(Number(e.target.value))}
              style={{ display: 'block', width: '100%' }}
            />
            <span className="dim" style={{ fontSize: '0.8rem' }}>Low: best synergy. High: anything goes.</span>
          </label>
          <label>
            Lands
            <input
              type="number"
              min={20}
              max={50}
              value={landCount}
              onChange={e => setLandCount(Number(e.target.value) || template.defaultLands)}
              style={{ display: 'block', width: '6rem' }}
            />
          </label>
          <label>
            Seed
            <input
              type="number"
              value={seed}
              onChange={e => setSeed(Number(e.target.value) || 0)}
              style={{ display: 'block', width: '9rem' }}
            />
          </label>
          <label style={{ alignSelf: 'end' }}>
            <input type="checkbox" checked={includeUsed} onChange={e => setIncludeUsed(e.target.checked)} />{' '}
            Include cards used in other decks
          </label>
        </div>
      )}

      {!loading && loadError == null && (
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <button
            type="button"
            className="btn-accent"
            disabled={commanders.length === 0}
            onClick={() => generate(seed)}
          >
            Generate
          </button>
          <button
            type="button"
            disabled={commanders.length === 0}
            onClick={() => {
              const next = newSeed();
              setSeed(next);
              generate(next);
            }}
          >
            New random deck
          </button>
          {commanders.length === 0 && (
            <span>No commander has enough cards in its colours. Try including cards used in other decks.</span>
          )}
        </div>
      )}

      {result != null && (
        <section>
          <h2 style={{ marginBottom: '0.25rem' }}>{result.deck.commander.title}</h2>
          <p style={{ marginTop: 0, fontSize: '0.9rem' }}>
            Seed {result.seed}. {totalCards} cards plus the commander.
            {result.themes.length > 0 && <> Themes: {result.themes.join(', ')}.</>}
            {' '}Coloured spells castable on curve: {Math.round(result.lands.castableProposed * 100)}%.
          </p>
          {result.deck.warnings.map(w => <p key={w} style={{ color: '#c00', margin: '0.25rem 0' }}>{w}</p>)}

          <table style={{ borderCollapse: 'collapse', fontSize: '0.85rem', marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th style={HEAD}>Role</th>
                <th style={HEAD}>Cards</th>
                <th style={HEAD}>Target</th>
              </tr>
            </thead>
            <tbody>
              {(Object.keys(result.deck.roleCounts) as CardRole[]).map(role => (
                <tr key={role} style={ROW}>
                  <td style={CELL}>{CARD_ROLE_LABEL[role]}</td>
                  <td style={CELL} className="tnum">{result.deck.roleCounts[role]}</td>
                  <td style={CELL} className="tnum">
                    {template.roles[role] != null ? `${template.roles[role]!.min}-${template.roles[role]!.max}` : ''}
                  </td>
                </tr>
              ))}
              <tr style={ROW}>
                <td style={CELL}>Curve (1 to 6+)</td>
                <td style={CELL} colSpan={2} className="tnum">
                  {CURVE_BUCKETS.map(b => result.deck.curve[b]).join(' / ')}
                </td>
              </tr>
            </tbody>
          </table>

          {(['ramp', 'draw', 'removal', 'wipe', 'finisher', 'threat', 'synergy'] as const).map(reason => {
            const group = result.deck.cards.filter(c => c.reason === reason);
            if (group.length === 0) {
              return null;
            }
            return (
              <div key={reason} style={{ marginBottom: '0.75rem' }}>
                <h3 style={{ margin: '0 0 0.25rem', fontSize: '1rem' }}>
                  {REASON_LABEL[reason]} ({group.length})
                </h3>
                <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.6 }}>
                  {group.map((c, i) => (
                    <span key={c.card.title} title={c.roles.map(r => CARD_ROLE_LABEL[r]).join(', ')}>
                      {i > 0 ? ', ' : ''}
                      {c.card.title}
                      {c.fit >= 0.5 && <span className="dim"> *</span>}
                    </span>
                  ))}
                </p>
              </div>
            );
          })}
          <p className="dim" style={{ fontSize: '0.8rem' }}>* strong synergy with the commander</p>

          <h3 style={{ margin: '1rem 0 0.25rem', fontSize: '1rem' }}>
            Lands ({result.lands.picks.reduce((s, p) => s + p.quantity, 0)})
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.6 }}>
            {result.lands.picks.map(p => `${p.quantity > 1 ? `${p.quantity} ` : ''}${p.option.land.title}`).join(', ')}
          </p>

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
            <button
              type="button"
              className="btn-accent"
              disabled={save.isPending}
              onClick={() => save.mutate(result)}
            >
              {save.isPending ? 'Saving...' : 'Save as new deck'}
            </button>
            {save.isError && (
              <span style={{ color: '#c00' }}>
                {save.error instanceof Error ? save.error.message : 'Saving failed.'}
              </span>
            )}
          </div>
        </section>
      )}
    </main>
  );
};

export const getServerSideProps = async () => ({ props: {} });

export default GeneratePage;
