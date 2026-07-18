import React from 'react';
import { useRouter } from 'next/router';
import type { NavId } from './TopBar';

const HINTS: Record<NavId, Array<[string, string]>> = {
  home: [
    ['D', 'DECKS'],
    ['C', 'COLLECTION'],
    ['/', 'CMD'],
    ['H', 'HOME'],
  ],
  decks: [
    ['UP/DN', 'NAV'],
    ['ENTER', 'OPEN'],
    ['N', 'NEW'],
    ['/', 'FILTER'],
  ],
  builder: [
    ['UP/DN', 'NAV'],
    ['+/-', 'QTY'],
    ['S', 'SIDEBOARD'],
    ['ESC', 'BACK'],
  ],
  collection: [
    ['UP/DN', 'NAV'],
    ['F', 'FOIL'],
    ['/', 'FILTER'],
  ],
  play: [
    ['L', 'LAND'],
    ['C', 'CAST'],
    ['A', 'ATTACK'],
    ['SPC', 'PASS'],
  ],
  sim: [
    ['R', 'RUN'],
    ['G', 'GAMES'],
    ['UP/DN', 'HISTORY'],
  ],
  import: [
    ['DROP', 'FILE'],
    ['UP/DN', 'ROWS'],
    ['ENTER', 'RESOLVE'],
  ],
  meta: [
    ['R', 'SCRAPE'],
    ['UP/DN', 'DECKS'],
  ],
};

function routeToNav(pathname: string): NavId {
  if (pathname === '/') return 'home';
  if (pathname.startsWith('/decks/') && pathname !== '/decks') return 'builder';
  if (pathname.startsWith('/decks')) return 'decks';
  if (pathname.startsWith('/collection')) return 'collection';
  if (pathname.startsWith('/play')) return 'play';
  if (pathname.startsWith('/import')) return 'import';
  if (pathname.startsWith('/meta')) return 'meta';
  return 'home';
}

export function StatusBar({
  deckTitle,
  onCmdOpen,
}: {
  deckTitle?: string | null;
  onCmdOpen?: () => void;
}) {
  const router = useRouter();
  const route = routeToNav(router.pathname);
  const list = HINTS[route] ?? HINTS.decks;

  return (
    <div
      style={{
        height: 22,
        borderTop: '1px solid var(--line)',
        background: 'var(--bg-1)',
        display: 'flex',
        alignItems: 'center',
        fontFamily: 'var(--mono)',
        fontSize: 10.5,
        padding: '0 10px',
        gap: 16,
        color: 'var(--ink-3)',
      }}
    >
      <button
        type="button"
        onClick={onCmdOpen}
        style={{
          background: 'var(--accent)',
          color: 'var(--bg)',
          padding: '1px 6px',
          borderRadius: 2,
          fontWeight: 700,
          letterSpacing: '0.08em',
          fontSize: 10,
        }}
      >
        :
      </button>
      <span>READY</span>
      {deckTitle && (
        <span>
          · DECK <span style={{ color: 'var(--ink)' }}>{deckTitle.toUpperCase()}</span>
        </span>
      )}
      <div style={{ flex: 1 }} />
      {list.map(([k, l]) => (
        <span key={`${k}-${l}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <kbd>{k}</kbd>
          <span>{l}</span>
        </span>
      ))}
    </div>
  );
}
