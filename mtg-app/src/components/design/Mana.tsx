import React from 'react';

export type ManaSymbolStyle = 'letter' | 'dot' | 'wedge' | 'sq';

const COLOR_LABEL: Record<string, string> = {
  W: 'White',
  U: 'Blue',
  B: 'Black',
  R: 'Red',
  G: 'Green',
  C: 'Colorless',
};

export function parseManaCost(cost: string | null | undefined): string[] {
  if (!cost) {
    return [];
  }
  const out: string[] = [];
  const re = /\{([^}]+)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(cost)) !== null) {
    out.push(m[1]);
  }
  return out;
}

function HybridPip({
  a,
  b,
  style,
  size,
}: {
  a: string;
  b: string;
  style: ManaSymbolStyle;
  size: number;
}) {
  const r = style === 'sq' ? 0 : style === 'wedge' ? 3 : '50%';
  const half = size / 2;
  return (
    <span
      style={{
        display: 'inline-block',
        position: 'relative',
        width: size,
        height: size,
        borderRadius: r,
        overflow: 'hidden',
        flexShrink: 0,
        verticalAlign: 'middle',
      }}
      title={`${COLOR_LABEL[a]}/${COLOR_LABEL[b]}`}
    >
      <span
        className={`pip ${a}`}
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: half,
          height: size,
          borderRadius: 0,
          fontSize: 9,
        }}
      >
        {style === 'dot' ? '' : a}
      </span>
      <span
        className={`pip ${b}`}
        style={{
          position: 'absolute',
          right: 0,
          top: 0,
          width: half,
          height: size,
          borderRadius: 0,
          fontSize: 9,
        }}
      >
        {style === 'dot' ? '' : b}
      </span>
    </span>
  );
}

export function Pip({
  token,
  style = 'letter',
  size = 16,
}: {
  token: string;
  style?: ManaSymbolStyle;
  size?: number;
}) {
  const t = token.trim();
  let kind = 'N';
  let label = t;

  if (/^[WUBRG]$/.test(t)) {
    kind = t;
    label = t;
  } else if (/^[0-9]+$/.test(t)) {
    kind = 'C';
    label = t;
  } else if (t === 'X' || t === 'Y' || t === 'Z') {
    kind = 'X';
    label = t;
  } else if (/^[WUBRG]\/[WUBRG]$/.test(t)) {
    const [a, b] = t.split('/');
    return <HybridPip a={a} b={b} style={style} size={size} />;
  } else if (/^[WUBRG]\/P$/.test(t)) {
    kind = t[0];
    label = t[0];
  } else if (/^2\/[WUBRG]$/.test(t)) {
    kind = t[2];
    label = '2';
  }

  const cls = ['pip', kind];
  if (style === 'dot') cls.push('pip-dot');
  if (style === 'wedge') cls.push('pip-wedge');
  if (style === 'sq') cls.push('pip-sq');

  const s: React.CSSProperties = {
    width: size,
    height: size,
    fontSize: Math.max(8, Math.round(size * 0.62)),
  };
  if (style === 'dot') {
    s.width = Math.round(size * 0.55);
    s.height = Math.round(size * 0.55);
  }

  return (
    <span className={cls.join(' ')} style={s} title={COLOR_LABEL[kind] || label}>
      {style === 'dot' ? '' : label}
    </span>
  );
}

export function ManaCost({
  cost,
  style = 'letter',
  size = 14,
  gap = 1,
}: {
  cost: string | null | undefined;
  style?: ManaSymbolStyle;
  size?: number;
  gap?: number;
}) {
  if (!cost) return null;
  const tokens = parseManaCost(cost);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap, verticalAlign: 'middle' }}>
      {tokens.map((t, i) => (
        <Pip key={`${t}-${i}`} token={t} style={style} size={size} />
      ))}
    </span>
  );
}

export function ColorIdentity({
  colors,
  style = 'letter',
  size = 16,
}: {
  colors: string[] | null | undefined;
  style?: ManaSymbolStyle;
  size?: number;
}) {
  if (!colors || colors.length === 0) {
    return <span className="dim">--</span>;
  }
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {colors.map((c, i) => (
        <Pip key={`${c}-${i}`} token={c} style={style} size={size} />
      ))}
    </span>
  );
}

export function ColorIdStrip({
  colors,
  manaSymbolStyle = 'letter',
}: {
  colors: string[] | null | undefined;
  manaSymbolStyle?: ManaSymbolStyle;
}) {
  const ALL = ['W', 'U', 'B', 'R', 'G'] as const;
  const set = new Set(colors ?? []);
  return (
    <span style={{ display: 'inline-flex', gap: 1 }}>
      {ALL.map(c =>
        set.has(c) ? (
          <Pip key={c} token={c} style={manaSymbolStyle} size={12} />
        ) : (
          <span
            key={c}
            style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius:
                manaSymbolStyle === 'sq' ? 0 : manaSymbolStyle === 'wedge' ? 2 : '50%',
              background: 'transparent',
              border: '1px dashed var(--ink-4)',
            }}
          />
        ),
      )}
    </span>
  );
}
