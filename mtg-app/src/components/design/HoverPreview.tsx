import React from 'react';
import { cardImageSrc } from '../../utils/cardImage';

export function HoverPreview({
  name,
  imageUri,
  x,
  y,
}: {
  name: string;
  imageUri?: string | null;
  x: number;
  y: number;
}) {
  const W = 240;
  const H = 336;
  const right = x + 16 + W > window.innerWidth ? x - W - 16 : x + 16;
  const top = Math.min(window.innerHeight - H - 8, Math.max(8, y - H / 2));
  const src = cardImageSrc({ field_image_uri: imageUri });

  return (
    <div
      style={{
        position: 'fixed',
        left: right,
        top,
        width: W,
        height: H,
        pointerEvents: 'none',
        zIndex: 1000,
        borderRadius: 12,
        overflow: 'hidden',
        background: 'var(--bg-2)',
        border: '1px solid var(--line-2)',
        boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
      }}
    >
      <img
        src={src}
        alt={name}
        loading="lazy"
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        onError={e => {
          e.currentTarget.style.opacity = '0.2';
        }}
      />
    </div>
  );
}
