/**
 * Deck list page — Phase 4.
 *
 * All data is fetched and mutated at runtime via JSON:API.
 */

import React, { useState } from 'react';
import { Link } from 'gatsby';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchDecks,
  createDeck,
  deleteDeck,
} from '../../services/drupalApi';
import type { Deck } from '../../types/drupal';
import { slugify } from '../../utils/slugify';

const FORMATS = [
  'Standard',
  'Modern',
  'Legacy',
  'Vintage',
  'Pioneer',
  'Pauper',
  'EDH',
  'Other',
];

const DecksPage: React.FC = () => {
  const qc = useQueryClient();

  const { data: decks = [], isLoading } = useQuery<Deck[]>({
    queryKey: ['decks'],
    queryFn: fetchDecks,
  });

  const [title, setTitle] = useState('');
  const [format, setFormat] = useState(FORMATS[0] ?? 'Standard');
  const [creating, setCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createDeck({ title, field_format: format, field_notes: null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decks'] });
      setTitle('');
      setCreating(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDeck(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decks'] });
      setDeleteConfirm(null);
    },
  });

  return (
    <main style={{ padding: '1.5rem', maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Decks</h1>

      {isLoading && <p>Loading decks...</p>}

      <ul style={{ listStyle: 'none', padding: 0 }}>
        {decks.map(deck => (
          <li
            key={deck.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.5rem 0',
              borderBottom: '1px solid #eee',
            }}
          >
            <Link
              to={`/decks/${slugify(deck.attributes.title)}`}
              style={{ flex: 1, fontWeight: 'bold' }}
            >
              {deck.attributes.title}
            </Link>
            <span style={{ color: '#666', fontSize: '0.85rem' }}>
              {deck.attributes.field_format}
            </span>

            {deleteConfirm === deck.id ? (
              <>
                <span style={{ fontSize: '0.85rem', color: '#c00' }}>
                  Delete?
                </span>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deck.id)}
                  disabled={deleteMutation.isPending}
                  style={{ color: '#c00' }}
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={() => setDeleteConfirm(null)}
                >
                  No
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setDeleteConfirm(deck.id)}
                aria-label={`Delete ${deck.attributes.title}`}
              >
                Delete
              </button>
            )}
          </li>
        ))}
      </ul>

      {decks.length === 0 && !isLoading && (
        <p style={{ color: '#888' }}>No decks yet. Create your first deck below.</p>
      )}

      <hr />

      {creating ? (
        <form
          onSubmit={e => {
            e.preventDefault();
            if (title.trim() !== '') createMutation.mutate();
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: 400 }}
        >
          <h2 style={{ margin: 0 }}>New deck</h2>
          <label>
            Title
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              autoFocus
              style={{ display: 'block', width: '100%', marginTop: 4 }}
            />
          </label>
          <label>
            Format
            <select
              value={format}
              onChange={e => setFormat(e.target.value)}
              style={{ display: 'block', width: '100%', marginTop: 4 }}
            >
              {FORMATS.map(f => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="submit"
              disabled={createMutation.isPending || title.trim() === ''}
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => {
                setCreating(false);
                setTitle('');
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" onClick={() => setCreating(true)}>
          + New deck
        </button>
      )}

      <p style={{ marginTop: '2rem' }}>
        <Link to="/">Back to home</Link>
      </p>
    </main>
  );
};

export default DecksPage;
