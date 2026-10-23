// Builds the card parts list (tokens, emblems and game pieces each card
// makes) from the Scryfall bulk file, on the host instead of in the
// container. Same rules as CardParts::fromCard().
//
// Usage, from the drupal/ directory:
//   node web/modules/custom/mtg_scryfall_sync/scripts/card-parts.mjs \
//     web/modules/custom/mtg_scryfall_sync/data/default_cards.json card_parts.tsv
//   ddev drush mtg:card-parts --file=/var/www/html/card_parts.tsv

import { createReadStream, createWriteStream } from 'node:fs';
import { createInterface } from 'node:readline';

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('Usage: node card-parts.mjs <default_cards.json> <out.tsv>');
  process.exit(1);
}

const TOKEN_LAYOUTS = new Set(['token', 'emblem', 'double_faced_token']);
const GAME_PIECE_TYPES = /^(Emblem|Dungeon|Card)\b/;
const REFERENCE_CARDS = /^(On an Adventure|Foretell|Plot)$|Checklist/;
const clean = s => String(s ?? '').replace(/[\t\r\n]/g, ' ');

const out = createWriteStream(output);
const seen = new Set();
let cards = 0;
let links = 0;

const lines = createInterface({ input: createReadStream(input), crlfDelay: Infinity });
for await (const raw of lines) {
  const line = raw.trim().replace(/,$/, '');
  if (!line.startsWith('{')) continue;
  let card;
  try {
    card = JSON.parse(line);
  } catch {
    continue;
  }
  cards++;
  if (TOKEN_LAYOUTS.has(card.layout) || !Array.isArray(card.all_parts)) continue;
  for (const part of card.all_parts) {
    const id = part?.id ?? '';
    const name = part?.name ?? '';
    const type = part?.type_line ?? '';
    const component = part?.component ?? '';
    if (!id || !name || name === card.name) continue;
    const isToken = component === 'token';
    const isGamePiece = component === 'combo_piece' && GAME_PIECE_TYPES.test(type) && !REFERENCE_CARDS.test(name);
    if (!isToken && !isGamePiece) continue;
    const key = `${card.name}\u0000${id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.write([card.name, id, name, type, component].map(clean).join('\t') + '\n');
    links++;
  }
}
out.end();
console.log(`Read ${cards} cards, wrote ${links} links to ${output}`);
