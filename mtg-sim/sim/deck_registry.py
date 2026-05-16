"""
Fetches deck lists from Drupal JSON:API for use in game simulations.

Returns CardInfo objects with CMC, type, power and toughness so the mock
engine can make realistic gameplay decisions based on the actual cards.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from dataclasses import dataclass, field
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

DRUPAL_URL: str = os.environ.get("DRUPAL_URL", "")
DRUPAL_USER: str = os.environ.get("DRUPAL_USER", "")
DRUPAL_PASS: str = os.environ.get("DRUPAL_PASS", "")

_CARD_FIELDS = (
    "title,field_cmc,field_type_line,field_power,field_toughness,"
    "field_oracle_text,field_mana_cost,field_produced_mana"
)


def _parse_list_field(value: object) -> list[str]:
    """Parse a JSON:API multi-value field into a list of strings."""
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def _get_auth() -> tuple[str, str]:
    """Return Basic Auth credentials from environment variables."""
    return (DRUPAL_USER, DRUPAL_PASS)


@dataclass
class CardInfo:
    """Enriched card data used by the simulation engine.

    Power and toughness are stored as a combined 'pt' string (e.g. '2/2')
    matching the canonical MTG notation, keeping attribute count within bounds.
    """

    name: str
    quantity: int
    sideboard: bool
    cmc: float = 0.0
    type_line: str = ""
    pt: str = "0/0"
    oracle_text: str = ""
    mana_cost: str = ""
    produced_mana: list[str] = field(default_factory=list)

    @property
    def is_land(self) -> bool:
        """True when the card's type line contains 'Land'."""
        return "Land" in self.type_line

    @property
    def is_creature(self) -> bool:
        """True when the card's type line contains 'Creature'."""
        return "Creature" in self.type_line

    @property
    def is_instant_or_sorcery(self) -> bool:
        """True for instants and sorceries."""
        return "Instant" in self.type_line or "Sorcery" in self.type_line

    @property
    def numeric_power(self) -> int:
        """Integer power parsed from pt; defaults to 1 for variable-power cards."""
        try:
            return max(0, int(self.pt.split("/", maxsplit=1)[0]))
        except (ValueError, TypeError, IndexError):
            return 1

    @property
    def numeric_toughness(self) -> int:
        """Integer toughness parsed from pt; minimum 1."""
        try:
            return max(1, int(self.pt.split("/", maxsplit=1)[1]))
        except (ValueError, TypeError, IndexError):
            return 1

    def short_type(self) -> str:
        """Return a single-word type for display (Creature, Instant, Land…)."""
        for t in (
            "Creature", "Instant", "Sorcery",
            "Enchantment", "Artifact", "Planeswalker", "Land",
        ):
            if t in self.type_line:
                return t
        return "Spell"


def _parse_card_attrs(attrs: dict) -> dict:
    """Extract card fields from a JSON:API attributes dict.

    Power and toughness are combined into a 'pt' string (e.g. '2/2')
    matching CardInfo's field layout.
    """
    power = str(attrs.get("field_power") or "0")
    toughness = str(attrs.get("field_toughness") or "0")
    return {
        "name": str(attrs.get("title") or ""),
        "cmc": float(attrs.get("field_cmc") or 0),
        "type_line": str(attrs.get("field_type_line") or ""),
        "pt": f"{power}/{toughness}",
        "oracle_text": str(attrs.get("field_oracle_text") or ""),
        "mana_cost": str(attrs.get("field_mana_cost") or ""),
        "produced_mana": _parse_list_field(attrs.get("field_produced_mana")),
    }


def _card_info_from(info: dict, quantity: int, sideboard: bool) -> CardInfo:
    """Build a CardInfo from an enriched dict."""
    return CardInfo(
        name=info["name"],
        quantity=quantity,
        sideboard=sideboard,
        cmc=info.get("cmc", 0.0),
        type_line=info.get("type_line", ""),
        pt=info.get("pt", "0/0"),
        oracle_text=info.get("oracle_text", ""),
        mana_cost=info.get("mana_cost", ""),
        produced_mana=info.get("produced_mana", []),
    )


def _chunk_url(chunk: list[str]) -> str:
    """Build a JSON:API OR-filter URL for a batch of card names."""
    params: list[str] = []
    for j, name in enumerate(chunk):
        params.append(f"filter[n{j}][condition][path]=title")
        params.append(f"filter[n{j}][condition][value]={urllib.parse.quote(name)}")
        params.append(f"filter[n{j}][condition][memberOf]=or-group")
    params.append("filter[or-group][group][conjunction]=OR")
    params.append(f"fields[node--mtg_card]={_CARD_FIELDS}")
    params.append("page[limit]=500")
    return f"{DRUPAL_URL}/jsonapi/node/mtg_card?" + "&".join(params)


def _fetch_chunk(chunk: list[str], result: dict[str, dict]) -> None:
    """Paginate through one name-chunk and merge results into `result`."""
    url: str | None = _chunk_url(chunk)
    needed = set(chunk)
    while url and needed:
        resp = requests.get(url, auth=_get_auth(), timeout=20, verify=False)
        resp.raise_for_status()
        body = resp.json()
        for node in body.get("data", []):
            parsed = _parse_card_attrs(node["attributes"])
            title = parsed["name"]
            if title and title not in result:
                result[title] = parsed
            needed.discard(title)
        next_link = body.get("links", {}).get("next", {})
        url = next_link.get("href") if next_link and needed else None


def _enrich_by_name(names: list[str]) -> dict[str, dict]:
    """
    Batch-fetch CMC, type_line, power, toughness from Drupal for card names.

    Uses an OR filter against the mtg_card JSON:API endpoint, batched in
    chunks of 30 to stay within URL length limits. Cards not found fall back
    to safe defaults (caller handles missing keys).
    """
    if not names or not DRUPAL_URL:
        return {}

    unique = list(dict.fromkeys(names))
    result: dict[str, dict] = {}

    for i in range(0, len(unique), 30):
        try:
            _fetch_chunk(unique[i: i + 30], result)
        except requests.RequestException as exc:
            logger.warning("Card enrichment failed for chunk %d: %s", i, exc)

    return result


def fetch_player_deck(deck_nid: int) -> list[CardInfo]:
    """
    Fetch card slots from a deck's field_deck_cards paragraphs.

    The deck owns its cards (deck → paragraph.deck_card → mtg_card).
    A single request includes both paragraphs and card data.
    """
    url = (
        f"{DRUPAL_URL}/jsonapi/node/deck"
        f"?filter[drupal_internal__nid]={deck_nid}"
        "&include=field_deck_cards,field_deck_cards.field_card"
        "&fields[node--deck]=field_deck_cards"
        "&fields[paragraph--deck_card]=field_card,field_quantity,field_is_sideboard"
        f"&fields[node--mtg_card]={_CARD_FIELDS}"
        "&page[limit]=1"
    )
    resp = requests.get(url, auth=_get_auth(), timeout=30, verify=False)
    resp.raise_for_status()
    body = resp.json()

    data = body.get("data", [])
    if not data:
        logger.warning("No deck found for nid %s", deck_nid)
        return []

    para_refs = (
        data[0].get("relationships", {})
        .get("field_deck_cards", {})
        .get("data", [])
    )

    included = body.get("included") or []
    card_map = {
        i["id"]: _parse_card_attrs(i["attributes"])
        for i in included if i.get("type") == "node--mtg_card"
    }
    para_map = {
        i["id"]: i
        for i in included if i.get("type") == "paragraph--deck_card"
    }

    cards: list[CardInfo] = []
    for ref in para_refs:
        para = para_map.get(ref.get("id", ""))
        if not para:
            continue
        card_id = (
            para.get("relationships", {}).get("field_card", {})
            .get("data", {}).get("id", "")
        )
        info = card_map.get(card_id, {})
        if not info.get("name"):
            continue
        cards.append(_card_info_from(
            info,
            quantity=int(para["attributes"].get("field_quantity") or 1),
            sideboard=bool(para["attributes"].get("field_is_sideboard", False)),
        ))
    return cards


@lru_cache(maxsize=64)
def fetch_meta_deck(archetype: str, fmt: str) -> list[CardInfo]:
    """
    Fetch the canonical card list for a meta archetype, enriched with card data.
    """
    url = (
        f"{DRUPAL_URL}/jsonapi/node/meta_deck"
        f"?filter[title]={urllib.parse.quote(archetype)}"
        f"&filter[field_format]={urllib.parse.quote(fmt)}"
        "&fields[node--meta_deck]=title,field_cards_json"
        "&page[limit]=1"
    )
    resp = requests.get(url, auth=_get_auth(), timeout=30, verify=False)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data", [])
    if not data:
        logger.warning("No meta_deck found for %s / %s", archetype, fmt)
        return []

    raw = data[0]["attributes"].get("field_cards_json") or ""
    cards_json = raw.get("value", "") if isinstance(raw, dict) else str(raw)
    try:
        raw_cards: list[dict] = json.loads(cards_json) if cards_json else []
    except json.JSONDecodeError:
        logger.warning("Could not parse field_cards_json for %s", archetype)
        return []

    all_names = [c["name"] for c in raw_cards if c.get("name")]
    enrichment = _enrich_by_name(all_names)

    cards: list[CardInfo] = []
    for c in raw_cards:
        name = c.get("name", "")
        if not name:
            continue
        info = enrichment.get(name, {})
        cards.append(_card_info_from(
            info or {"name": name},
            quantity=int(c.get("quantity", 1)),
            sideboard=bool(c.get("sideboard", False)),
        ))
    return cards
