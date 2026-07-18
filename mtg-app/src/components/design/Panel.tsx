import React from 'react';

export function Panel({
  title,
  right,
  children,
  style,
  scroll = false,
  pad = true,
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
  scroll?: boolean;
  pad?: boolean;
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid var(--line)',
        background: 'var(--bg-1)',
        minHeight: 0,
        minWidth: 0,
        ...style,
      }}
    >
      {title && (
        <div
          style={{
            height: 26,
            padding: '0 10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--line)',
            background: 'var(--bg-2)',
            fontFamily: 'var(--mono)',
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.1em',
            color: 'var(--ink-2)',
            textTransform: 'uppercase',
          }}
        >
          <span>{title}</span>
          {right}
        </div>
      )}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          minWidth: 0,
          overflow: scroll ? 'auto' : 'visible',
          padding: pad ? 10 : 0,
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  delta,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  delta?: number | null;
  accent?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div className="uc dim" style={{ fontSize: 9 }}>
        {label}
      </div>
      <div
        className="mono tnum"
        style={{
          fontSize: 22,
          fontWeight: 600,
          color: accent ? 'var(--accent)' : 'var(--ink)',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      {(sub || delta != null) && (
        <div
          className="mono tnum"
          style={{ fontSize: 10, color: 'var(--ink-3)', display: 'flex', gap: 6 }}
        >
          {sub && <span>{sub}</span>}
          {delta != null && (
            <span style={{ color: delta >= 0 ? 'var(--pos)' : 'var(--neg)' }}>
              {delta >= 0 ? '+' : ''}
              {delta}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
