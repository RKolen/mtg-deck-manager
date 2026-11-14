/**
 * Front/back switcher for multi-faced cards (transform and modal back faces,
 * adventures, split, prepare and flip halves). Card fields only hold the
 * front face, so the faces come from the cardFaces query.
 */

import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCardFaces, type CardFace } from '../services/drupalApi';

/** Layouts with a printed back face, which has its own image. */
const TWO_SIDED_LAYOUTS = new Set(['transform', 'modal_dfc']);

/** Faces of a card by name; empty while loading and for single-faced cards. */
export function useCardFaces(cardTitle: string): CardFace[] {
  const { data = [] } = useQuery({
    queryKey: ['cardFaces', cardTitle],
    queryFn: () => fetchCardFaces(cardTitle),
    enabled: cardTitle.includes(' // '),
    staleTime: 60 * 60_000,
  });
  return data;
}

export interface CardFaceSwitch {
  faces: CardFace[];
  /** True when the card has two or more faces to switch between. */
  multiFaced: boolean;
  active: number;
  setActive: (index: number) => void;
}

/** Faces of a card plus the face being shown; goes back to the front when the card changes. */
export function useCardFaceSwitch(cardTitle: string): CardFaceSwitch {
  const faces = useCardFaces(cardTitle);
  const [active, setActive] = useState(0);
  useEffect(() => {
    setActive(0);
  }, [cardTitle]);
  return {
    faces,
    multiFaced: faces.length > 1,
    active: Math.min(active, Math.max(0, faces.length - 1)),
    setActive,
  };
}

/**
 * Image of a face, from the printing's stored (front) image.
 *
 * Scryfall serves the back of a double-faced printing at the same URL with
 * /front/ swapped for /back/; this holds for every transform and modal_dfc
 * printing in the bulk data. Other layouts print every face on one image.
 */
export function faceImageUri(frontUri: string, faces: CardFace[], index: number): string {
  const layout = faces[0]?.layout ?? '';
  if (index > 0 && TWO_SIDED_LAYOUTS.has(layout)) {
    return frontUri.replace('/front/', '/back/');
  }
  return frontUri;
}

/** Image rotation for a face: the flipped half of a flip card is printed upside down. */
export function faceImageRotation(faces: CardFace[], index: number): string | undefined {
  return index > 0 && faces[0]?.layout === 'flip' ? 'rotate(180deg)' : undefined;
}

export const CardFaceSwitcher: React.FC<{
  faces: CardFace[];
  active: number;
  onChange: (index: number) => void;
}> = ({ faces, active, onChange }) => (
  <div role="tablist" aria-label="Card faces" style={{ display: 'flex', gap: 4, flexWrap: 'wrap', margin: '0 0 0.5rem' }}>
    {faces.map((face, index) => {
      const selected = index === active;
      return (
        <button
          key={`${index}-${face.name}`}
          type="button"
          role="tab"
          aria-selected={selected}
          onClick={() => onChange(index)}
          style={{
            padding: '0.3rem 0.65rem',
            borderRadius: 4,
            border: selected ? '1px solid var(--accent)' : '1px solid var(--line)',
            background: selected ? 'var(--accent)' : 'var(--bg-2)',
            color: selected ? 'var(--bg)' : 'var(--ink)',
            fontSize: '0.85rem',
            fontWeight: selected ? 700 : 400,
            cursor: 'pointer',
          }}
        >
          {face.name}
        </button>
      );
    })}
  </div>
);

function stats(face: CardFace): string {
  if (face.power != null || face.toughness != null) {
    return `${face.power ?? '?'} / ${face.toughness ?? '?'}`;
  }
  return face.loyalty != null ? `Loyalty: ${face.loyalty}` : '';
}

/** Name, cost, type line, rules text and stats of one face. */
export const CardFaceText: React.FC<{ face: CardFace }> = ({ face }) => {
  const faceStats = stats(face);
  return (
    <section
      style={{
        background: 'var(--bg-2)',
        color: 'var(--ink)',
        border: '1px solid var(--line)',
        borderRadius: 4,
        padding: '0.6rem 0.75rem',
        fontSize: '0.95rem',
        lineHeight: 1.5,
        margin: '0 0 0.75rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong>{face.name}</strong>
        {face.manaCost !== '' && <span>{face.manaCost}</span>}
      </div>
      {face.typeLine !== '' && (
        <div style={{ fontStyle: 'italic', margin: '0.15rem 0 0.35rem' }}>{face.typeLine}</div>
      )}
      {face.oracleText !== '' && <div style={{ whiteSpace: 'pre-wrap' }}>{face.oracleText}</div>}
      {faceStats !== '' && <div style={{ fontWeight: 700, marginTop: '0.35rem' }}>{faceStats}</div>}
    </section>
  );
};
