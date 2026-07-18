import { useEffect, useState } from 'react';

export type ChartTheme = {
  ink: string;
  line: string;
  line2: string;
  bg2: string;
  accent: string;
  pos: string;
  neg: string;
};

const FALLBACK_DARK: ChartTheme = {
  ink: '#d8dde4',
  line: '#1f2731',
  line2: '#2a3340',
  bg2: '#131820',
  accent: '#f5a623',
  pos: '#5fb37d',
  neg: '#d96b5f',
};

function readCssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Resolve theme tokens to concrete colors (Recharts rejects CSS vars on SVG attrs). */
export function readChartTheme(): ChartTheme {
  return {
    ink: readCssVar('--ink', FALLBACK_DARK.ink),
    line: readCssVar('--line', FALLBACK_DARK.line),
    line2: readCssVar('--line-2', FALLBACK_DARK.line2),
    bg2: readCssVar('--bg-2', FALLBACK_DARK.bg2),
    accent: readCssVar('--accent', FALLBACK_DARK.accent),
    pos: readCssVar('--pos', FALLBACK_DARK.pos),
    neg: readCssVar('--neg', FALLBACK_DARK.neg),
  };
}

export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(FALLBACK_DARK);

  useEffect(() => {
    const update = () => setTheme(readChartTheme());
    update();
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'style'],
    });
    return () => obs.disconnect();
  }, []);

  return theme;
}

export function chartAxisProps(theme: ChartTheme) {
  return {
    tick: { fill: theme.ink, fontSize: 11 },
    stroke: theme.line2,
  };
}

export function chartTooltipProps(theme: ChartTheme) {
  return {
    contentStyle: {
      background: theme.bg2,
      border: `1px solid ${theme.line}`,
      borderRadius: 4,
      color: theme.ink,
    },
    labelStyle: { color: theme.ink },
    itemStyle: { color: theme.ink },
  };
}
