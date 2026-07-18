import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useQuery } from '@tanstack/react-query';
import { fetchCollectionCards, fetchCollectionValue } from '../../services/drupalApi';
import { useTheme } from '../../context/ThemeContext';
import { TopBar } from './TopBar';
import { StatusBar } from './StatusBar';

export function AppShell({
  children,
  deckTitle,
}: {
  children: React.ReactNode;
  deckTitle?: string | null;
}) {
  const router = useRouter();
  const { currency } = useTheme();

  const { data: collectionValue = null } = useQuery({
    queryKey: ['collectionValue', currency],
    queryFn: () => fetchCollectionValue(currency),
    staleTime: 60_000,
  });

  const { data: collectionCards = [] } = useQuery({
    queryKey: ['collectionCards'],
    queryFn: fetchCollectionCards,
    staleTime: 60_000,
  });

  const uniqueCards = collectionCards.filter(
    c =>
      (c.attributes.field_quantity_owned ?? 0) + (c.attributes.field_quantity_foil ?? 0) > 0,
  ).length;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      const key = e.key.toLowerCase();
      if (key === 'h') router.push('/');
      else if (key === 'd') router.push('/decks');
      else if (key === 'c') router.push('/collection');
      else if (key === 'p') router.push('/play');
      else if (key === 'i') router.push('/import');
      else if (key === 'm') router.push('/meta-decks');
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [router]);

  return (
    <div className="app-shell">
      <TopBar
        uniqueCards={uniqueCards}
        collectionValue={collectionValue}
        currency={currency}
      />
      <div className="app-shell-main">{children}</div>
      <StatusBar deckTitle={deckTitle} />
    </div>
  );
}
