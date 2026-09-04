import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useTheme } from '../../context/ThemeContext';
import { formatPrice, type Currency } from '../../utils/prices';

export type NavId =
  | 'home'
  | 'decks'
  | 'builder'
  | 'collection'
  | 'sim'
  | 'import'
  | 'meta';

const TABS: Array<{ id: NavId; label: string; href: string; hotkey: string }> = [
  { id: 'home', label: 'HOME', href: '/', hotkey: 'H' },
  { id: 'decks', label: 'DECKS', href: '/decks', hotkey: 'D' },
  { id: 'builder', label: 'BUILDER', href: '/decks', hotkey: 'B' },
  { id: 'collection', label: 'COLLECTION', href: '/collection', hotkey: 'C' },
  { id: 'import', label: 'IMPORT', href: '/import', hotkey: 'I' },
  { id: 'meta', label: 'META', href: '/meta-decks', hotkey: 'M' },
];

function routeToNav(pathname: string): NavId {
  if (pathname === '/') return 'home';
  if (pathname.startsWith('/decks/') && pathname !== '/decks') return 'builder';
  if (pathname.startsWith('/decks')) return 'decks';
  if (pathname.startsWith('/collection')) return 'collection';
  if (pathname.startsWith('/import')) return 'import';
  if (pathname.startsWith('/meta')) return 'meta';
  return 'home';
}

export function TopBar({
  uniqueCards,
  collectionValue,
  currency,
}: {
  uniqueCards?: number | null;
  collectionValue?: number | null;
  currency: Currency;
}) {
  const router = useRouter();
  const { dark, toggleDark } = useTheme();
  const active = routeToNav(router.pathname);
  // null until mount — avoids SSR/client clock mismatch hydration errors
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const ts = now ? now.toISOString().slice(11, 19) + 'Z' : '--:--:--Z';

  return (
    <div
      style={{
        position: 'relative',
        borderBottom: '1px solid var(--line)',
        background: 'var(--bg-1)',
        height: 30,
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px',
      }}
    >
      <Link
        href="/"
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.1em',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          flexShrink: 0,
          whiteSpace: 'nowrap',
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        <span
          style={{
            background: 'var(--accent)',
            color: 'var(--bg)',
            padding: '2px 6px',
            borderRadius: 2,
          }}
        >
          MTG
        </span>
        <span className="dim">//</span>
        <span>DECK MANAGER</span>
      </Link>

      <div style={{ width: 16 }} />
      <div className="vr" style={{ height: 16 }} />

      {TABS.map(t => {
        const isActive = active === t.id;
        return (
          <Link
            key={t.id}
            href={t.href}
            style={{
              padding: '0 12px',
              height: 28,
              flexShrink: 0,
              whiteSpace: 'nowrap',
              fontFamily: 'var(--mono)',
              fontSize: 11,
              fontWeight: isActive ? 700 : 400,
              color: isActive ? 'var(--accent)' : 'var(--ink)',
              borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
              letterSpacing: '0.08em',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: -1,
              textDecoration: 'none',
            }}
          >
            <span>{t.label}</span>
            <kbd>{t.hotkey}</kbd>
          </Link>
        );
      })}

      <div style={{ flex: 1 }} />

      <div
        className="mono tnum"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          fontSize: 11,
          color: 'var(--ink)',
          flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
      >
        <span>
          UNIQ{' '}
          <span style={{ color: 'var(--ink)' }}>
            {uniqueCards != null ? uniqueCards.toLocaleString('en-US') : '--'}
          </span>
        </span>
        <span>
          VAL{' '}
          <span style={{ color: 'var(--ink)' }}>
            {formatPrice(collectionValue ?? null, currency)}
          </span>
        </span>
        <span style={{ color: 'var(--ink)' }}>{ts}</span>
        <button
          type="button"
          onClick={toggleDark}
          title="Toggle theme"
          style={{
            border: '1px solid var(--line-2)',
            padding: '2px 6px',
            borderRadius: 3,
            fontSize: 10,
            color: 'var(--ink)',
          }}
        >
          {dark ? 'DARK' : 'LIGHT'}
        </button>
      </div>
    </div>
  );
}
