/**
 * Copies a plain card list ("4 Card Name" lines) to the clipboard, e.g. for
 * Cardmarket's wants list. By default only copies still missing are listed;
 * a checkbox includes owned cards too (other arts, or extra copies so other
 * decks stay intact).
 */

import React, { useState } from 'react';

interface CopyCardListButtonProps {
  /** Builds the text and its card count for the chosen option. */
  build: (includeOwned: boolean) => { text: string; count: number };
  label?: string;
}

/** Writes text to the clipboard, falling back to a hidden textarea. */
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok;
  }
}

const CopyCardListButton: React.FC<CopyCardListButtonProps> = ({ build, label = 'Copy for Cardmarket' }) => {
  const [includeOwned, setIncludeOwned] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function onCopy(): Promise<void> {
    const { text, count } = build(includeOwned);
    if (count === 0) {
      setStatus(includeOwned ? 'Nothing to copy.' : 'Nothing missing: you own every card.');
      return;
    }
    const ok = await copyText(text);
    setStatus(ok ? `Copied ${count} card${count === 1 ? '' : 's'}.` : 'Could not copy to the clipboard.');
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13 }}>
      <button type="button" onClick={() => void onCopy()}>
        {label}
      </button>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <input
          type="checkbox"
          checked={includeOwned}
          onChange={e => {
            setIncludeOwned(e.target.checked);
            setStatus(null);
          }}
        />
        Include cards I own
      </label>
      {status != null && (
        <span role="status" style={{ opacity: 0.8 }}>
          {status}
        </span>
      )}
    </span>
  );
};

export default CopyCardListButton;
