/**
 * Small shared pieces of the collection, deck and set statistics pages.
 */

import React from 'react';

export const cell: React.CSSProperties = { padding: '3px 6px', whiteSpace: 'nowrap' };
export const num: React.CSSProperties = { ...cell, textAlign: 'right' };
export const link: React.CSSProperties = { color: 'var(--accent)', textDecoration: 'none' };
export const statTable: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: 12 };
export const headRow: React.CSSProperties = { textAlign: 'left', borderBottom: '1px solid var(--line)' };
export const bodyRow: React.CSSProperties = { borderBottom: '1px solid var(--line)' };

/** Horizontal bar showing a share of the whole. */
export function Bar({ share }: { share: number }) {
  return (
    <div style={{ height: 8, background: 'var(--bg-2)', width: '100%' }}>
      <div
        style={{
          height: '100%',
          width: `${Math.max(0, Math.min(1, share)) * 100}%`,
          background: 'var(--accent)',
        }}
      />
    </div>
  );
}

/** Page header with a breadcrumb trail, title and optional controls. */
export function StatsHeader({
  crumbs,
  title,
  loading,
  children,
}: {
  crumbs: React.ReactNode;
  title: React.ReactNode;
  loading?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div
      style={{
        padding: '20px 28px',
        borderBottom: '1px solid var(--line)',
        background: 'var(--bg-1)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-end',
        gap: 24,
      }}
    >
      <div style={{ flex: 1, minWidth: 240 }}>
        <div className="mono uc dim" style={{ fontSize: 10, marginBottom: 6 }}>
          {crumbs}
        </div>
        <h1 className="sans" style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>
          {title}
          {loading === true && (
            <span className="mono dim" style={{ fontSize: 11, marginLeft: 10 }}>
              loading...
            </span>
          )}
        </h1>
      </div>
      {children}
    </div>
  );
}

/** Row of headline numbers under the header. */
export function StatRow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 16,
        padding: 20,
        borderBottom: '1px solid var(--line)',
      }}
    >
      {children}
    </div>
  );
}

/** Segmented filter buttons, e.g. all / owned / missing. */
export function FilterButtons<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ id: T; label: string }>;
  onChange: (id: T) => void;
}) {
  return (
    <span style={{ display: 'flex', gap: 4 }}>
      {options.map(o => (
        <button
          key={o.id}
          type="button"
          onClick={() => onChange(o.id)}
          aria-pressed={value === o.id}
          style={{
            fontSize: 10,
            padding: '1px 8px',
            fontWeight: value === o.id ? 700 : 400,
            borderBottom: value === o.id ? '2px solid var(--accent)' : '2px solid transparent',
          }}
        >
          {o.label}
        </button>
      ))}
    </span>
  );
}
