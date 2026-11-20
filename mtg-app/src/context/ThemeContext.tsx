import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchUsdToEurRate } from '../services/drupalApi';
import type { Currency } from '../utils/prices';
import type { ManaSymbolStyle } from '../components/design/Mana';

export type ThemePrefs = {
  dark: boolean;
  accentColor: string;
  currency: Currency;
  manaSymbolStyle: ManaSymbolStyle;
};

type ThemeContextValue = ThemePrefs & {
  /** Euros per US dollar, or null until loaded (no conversion then). */
  usdToEur: number | null;
  setDark: (dark: boolean) => void;
  toggleDark: () => void;
  setAccentColor: (color: string) => void;
  setCurrency: (currency: Currency) => void;
  setManaSymbolStyle: (style: ManaSymbolStyle) => void;
};

const STORAGE_KEY = 'mtg-theme-prefs';

const DEFAULTS: ThemePrefs = {
  dark: true,
  accentColor: '#f5a623',
  currency: 'EUR',
  manaSymbolStyle: 'letter',
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function loadPrefs(): ThemePrefs {
  if (typeof window === 'undefined') {
    return DEFAULTS;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<ThemePrefs>;
    // Prices are always shown in EUR; ignore a stored USD preference.
    return { ...DEFAULTS, ...parsed, currency: 'EUR' };
  } catch {
    return DEFAULTS;
  }
}

// Preferences live in localStorage; this small store lets React read them
// with useSyncExternalStore (server render and hydration use DEFAULTS, the
// client then switches to the stored values without a mismatch).
const listeners = new Set<() => void>();
let current: ThemePrefs | null = null;

function getSnapshot(): ThemePrefs {
  if (current === null) {
    current = loadPrefs();
  }
  return current;
}

function getServerSnapshot(): ThemePrefs {
  return DEFAULTS;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function setPrefs(update: (prefs: ThemePrefs) => ThemePrefs): void {
  current = update(getSnapshot());
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Storage blocked: keep the preference for this page view only.
  }
  listeners.forEach(l => l());
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', prefs.dark ? 'dark' : 'light');
    document.documentElement.style.setProperty('--accent-color', prefs.accentColor);
  }, [prefs]);

  const setDark = useCallback((dark: boolean) => {
    setPrefs(p => ({ ...p, dark }));
  }, []);
  const toggleDark = useCallback(() => {
    setPrefs(p => ({ ...p, dark: !p.dark }));
  }, []);
  const setAccentColor = useCallback((accentColor: string) => {
    setPrefs(p => ({ ...p, accentColor }));
  }, []);
  const setCurrency = useCallback((currency: Currency) => {
    setPrefs(p => ({ ...p, currency }));
  }, []);
  const setManaSymbolStyle = useCallback((manaSymbolStyle: ManaSymbolStyle) => {
    setPrefs(p => ({ ...p, manaSymbolStyle }));
  }, []);

  const { data: usdToEur = null } = useQuery({
    queryKey: ['usdToEurRate'],
    queryFn: fetchUsdToEurRate,
    staleTime: 60 * 60 * 1000,
  });

  const value = useMemo(
    () => ({
      ...prefs,
      usdToEur,
      setDark,
      toggleDark,
      setAccentColor,
      setCurrency,
      setManaSymbolStyle,
    }),
    [prefs, usdToEur, setDark, toggleDark, setAccentColor, setCurrency, setManaSymbolStyle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
