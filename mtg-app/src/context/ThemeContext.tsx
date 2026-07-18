import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { Currency } from '../utils/prices';
import type { ManaSymbolStyle } from '../components/design/Mana';

export type ThemePrefs = {
  dark: boolean;
  accentColor: string;
  currency: Currency;
  manaSymbolStyle: ManaSymbolStyle;
};

type ThemeContextValue = ThemePrefs & {
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
    return { ...DEFAULTS, ...parsed };
  } catch {
    return DEFAULTS;
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [prefs, setPrefs] = useState<ThemePrefs>(DEFAULTS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setPrefs(loadPrefs());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    document.documentElement.setAttribute('data-theme', prefs.dark ? 'dark' : 'light');
    document.documentElement.style.setProperty('--accent-color', prefs.accentColor);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  }, [prefs, hydrated]);

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

  const value = useMemo(
    () => ({
      ...prefs,
      setDark,
      toggleDark,
      setAccentColor,
      setCurrency,
      setManaSymbolStyle,
    }),
    [prefs, setDark, toggleDark, setAccentColor, setCurrency, setManaSymbolStyle],
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
