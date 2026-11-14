// Builds the faces list of multi-faced cards (transform and modal back
// faces, adventures, split and flip halves) from the Scryfall bulk file, on
// the host instead of in the container. Same rules as CardFaces::fromCard().
//
// Writes one JSON object per line, because oracle text contains newlines.
//
// Usage, from the drupal/ directory:
//   node web/modules/custom/mtg_scryfall_sync/scripts/card-faces.mjs \
//     web/modules/custom/mtg_scryfall_sync/data/default_cards.json tmp/card_faces.jsonl
//   ddev drush mtg:card-faces --file=/var/www/html/tmp/card_faces.jsonl

import { createReadStream, createWriteStream } from 'node:fs';
import { createInterface } from 'node:readline';

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('Usage: node card-faces.mjs <default_cards.json> <out.jsonl>');
  process.exit(1);
}

const SKIP_LAYOUTS = new Set(['token', 'emblem', 'double_faced_token', 'art_series', 'reversible_card']);
const text = value => (value === undefined || value === null || typeof value === 'object' ? '' : String(value));

const out = createWriteStream(output);
const seen = new Set();
let cards = 0;
let faces = 0;

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
  if (SKIP_LAYOUTS.has(card.layout) || !Array.isArray(card.card_faces) || card.card_faces.length < 2) continue;
  const name = text(card.name);
  if (name === '' || seen.has(name)) continue;
  seen.add(name);
  card.card_faces.forEach((face, index) => {
    if (face === null || typeof face !== 'object') return;
    out.write(JSON.stringify({
      card_name: name,
      face_index: index,
      name: text(face.name),
      mana_cost: text(face.mana_cost),
      type_line: text(face.type_line),
      oracle_text: text(face.oracle_text),
      power: text(face.power),
      toughness: text(face.toughness),
      loyalty: text(face.loyalty),
      layout: text(card.layout),
    }) + '\n');
    faces++;
  });
}
out.end();
console.log(`Read ${cards} cards, wrote ${faces} faces of ${seen.size} cards to ${output}`);
