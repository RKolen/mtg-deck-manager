import React from 'react';
import { useIsFetching, useIsMutating } from '@tanstack/react-query';

/**
 * Thin animated bar along the top of the window while anything is saving
 * or loading, so a slow add is visibly in progress.
 */
export function BusyBar() {
  const saving = useIsMutating();
  const loading = useIsFetching();
  const busy = saving > 0 || loading > 0;
  if (!busy) {
    return null;
  }
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        overflow: 'hidden',
        zIndex: 2000,
        background: 'transparent',
      }}
    >
      <style>{`
        @keyframes busy-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }
        @media (prefers-reduced-motion: reduce) { .busy-bar-fill { animation: none !important; width: 100% !important; opacity: 0.6; } }
      `}</style>
      <div
        className="busy-bar-fill"
        style={{
          width: '25%',
          height: '100%',
          background: 'var(--accent)',
          animation: 'busy-slide 1s ease-in-out infinite',
        }}
      />
    </div>
  );
}
