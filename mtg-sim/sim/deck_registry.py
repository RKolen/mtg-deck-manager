"""
Fetches deck lists from Drupal GraphQL for use in game simulations.

Returns CardInfo objects with CMC, type, power and toughness so the mock
engine can make realistic gameplay decisions based on the actual cards.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

DRUPAL_URL: str = os.environ.get("DRUPAL_URL", "")
DRUPAL_USER: str = os.environ.get("DRUPAL_USER", "")
DRUPAL_PASS: str = os.environ.get("DRUPAL_PASS", "")

def _parse_list_field(value: object) -> list[str]:
    """Parse a JSON:API multi-value field into a list of strings."""
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def _get_auth() -> tuple[str, str]:
    """Return Basic Auth credentials from environment variables."""
    return (DRUPAL_USER, DRUPAL_PASS)


@dataclass
class ManaProfile:
    """Mana-related card data grouped to keep CardInfo attribute count within bounds."""

    cmc: float = 0.0
    cost: str = ""
    produced: list[str] = field(default_factory=list)


@dataclass
class CardInfo:
    """Enriched card data used by the simulation engine.

    Power and toughness are stored as a combined 'pt' string (e.g. '2/2')
    matching the canonical MTG notation, keeping attribute count within bounds.
    """

    name: str
    quantity: int
    sideboard: bool
    mana: ManaProfile = field(default_factory=ManaProfile)
    type_line: str = ""
    pt: str = "0/0"
    oracle_text: str = ""

    @property
    def cmc(self) -> float:
        """Mana value of this card."""
        return self.mana.cmc

    @property
    def mana_cost(self) -> str:
        """Mana cost string of this card."""
        return self.mana.cost

    @property
    def produced_mana(self) -> list[str]:
        """Mana types this card produces."""
        return self.mana.produced

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


def _graphql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query to Drupal and return the data payload."""
    if not DRUPAL_URL:
        return {}
    url = urljoin(f"{DRUPAL_URL.rstrip('/')}/", "graphql")
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(
        url,
        json=payload,
        auth=_get_auth(),
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise requests.RequestException(str(body["errors"]))
    return body.get("data") or {}


def _parse_gql_card(card: dict) -> dict:
    """Extract card fields from a GraphQL MtgCard object."""
    power = str(card.get("power") or "0")
    toughness = str(card.get("toughness") or "0")
    return {
        "name": str(card.get("title") or ""),
        "cmc": float(card.get("cmc") or 0),
        "type_line": str(card.get("typeLine") or ""),
        "pt": f"{power}/{toughness}",
        "oracle_text": str(card.get("oracleText") or ""),
        "mana_cost": str(card.get("manaCost") or ""),
        "produced_mana": card.get("producedMana") or [],
    }


def _card_info_from(info: dict, quantity: int, sideboard: bool) -> CardInfo:
    """Build a CardInfo from an enriched dict."""
    return CardInfo(
        name=info["name"],
        quantity=quantity,
        sideboard=sideboard,
        mana=ManaProfile(
            cmc=info.get("cmc", 0.0),
            cost=info.get("mana_cost", ""),
            produced=info.get("produced_mana", []),
        ),
        type_line=info.get("type_line", ""),
        pt=info.get("pt", "0/0"),
        oracle_text=info.get("oracle_text", ""),
    )


_CARD_GQL = """
  title cmc typeLine power toughness oracleText manaCost producedMana
"""

def _fetch_name_chunk(chunk: list[str], result: dict[str, dict]) -> None:
    """Fetch exact card names via GraphQL cardsByName."""
    query = (
        "query CardsByName($name: String!) { cardsByName(name: $name) {"
        + _CARD_GQL
        + "} }"
    )
    for name in chunk:
        try:
            data = _graphql(query, {"name": name})
            for card in data.get("cardsByName") or []:
                parsed = _parse_gql_card(card)
                if parsed["name"] and parsed["name"] not in result:
                    result[parsed["name"]] = parsed
        except requests.RequestException as exc:
            logger.warning("Card lookup failed for %s: %s", name, exc)


def _enrich_by_name(names: list[str]) -> dict[str, dict]:
    """
    Batch-fetch CMC, type_line, power, toughness from Drupal for card names.

    Uses GraphQL cardsByName per name, batched in chunks of 30.
    Cards not found fall back to safe defaults (caller handles missing keys).
    """
    if not names or not DRUPAL_URL:
        return {}

    unique = list(dict.fromkeys(names))
    result: dict[str, dict] = {}

    for i in range(0, len(unique), 30):
        try:
            _fetch_name_chunk(unique[i: i + 30], result)
        except requests.RequestException as exc:
            logger.warning("Card enrichment failed for chunk %d: %s", i, exc)

    return result


def fetch_deck_title(deck_nid: int) -> str:
    """Return the deck node title, or a fallback string if unavailable."""
    attrs = _fetch_deck_attributes(deck_nid, "title")
    title = attrs.get("title")
    return str(title) if title else f"Deck #{deck_nid}"


def fetch_deck_notes(deck_nid: int) -> str:
    """Return the deck's field_notes pilot prompt, or empty string when unset."""
    attrs = _fetch_deck_attributes(deck_nid, "title,field_notes")
    notes = attrs.get("field_notes")
    if isinstance(notes, dict):
        value = notes.get("value")
        return str(value).strip() if value else ""
    if isinstance(notes, str):
        return notes.strip()
    return ""


def _fetch_deck_attributes(deck_nid: int, fields: str) -> dict:
    """Fetch selected JSON:API attributes for a deck node."""
    if not DRUPAL_URL:
        return {}
    url = urljoin(DRUPAL_URL, "/jsonapi/node/deck")
    try:
        resp = requests.get(
            url,
            params={
                "filter[drupal_internal__nid]": str(deck_nid),
                "fields[node--deck]": fields,
            },
            auth=_get_auth(),
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        items = resp.json()["data"]
        if not items:
            logger.warning("JSON:API deck nid %s not found", deck_nid)
            return {}
        attrs = items[0].get("attributes") or {}
        return attrs if isinstance(attrs, dict) else {}
    except (requests.RequestException, KeyError, TypeError, ValueError, IndexError) as exc:
        logger.warning("Deck attribute fetch failed for nid %s: %s", deck_nid, exc)
        return {}


def fetch_player_deck(deck_nid: int) -> list[CardInfo]:
    """
    Fetch card slots from a deck's field_deck_cards paragraphs via GraphQL.
    """
    query = (
        "query DeckCards($nid: Int!) { deckCardsByNid(nid: $nid) {"
        " quantity isSideboard card {"
        + _CARD_GQL
        + "} } }"
    )
    try:
        data = _graphql(query, {"nid": deck_nid})
    except requests.RequestException as exc:
        logger.warning("Deck fetch failed for nid %s: %s", deck_nid, exc)
        return []

    slots = data.get("deckCardsByNid") or []
    if not slots:
        logger.warning("No deck found for nid %s", deck_nid)
        return []

    cards: list[CardInfo] = []
    for slot in slots:
        card = slot.get("card")
        if not card:
            continue
        info = _parse_gql_card(card)
        if not info.get("name"):
            continue
        cards.append(_card_info_from(
            info,
            quantity=int(slot.get("quantity") or 1),
            sideboard=bool(slot.get("isSideboard", False)),
        ))
    return cards


def _build_card_list(raw_cards: list[dict], enrichment: dict[str, dict]) -> list[CardInfo]:
    """Build a list of CardInfo from raw card dicts and pre-fetched enrichment data."""
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


@lru_cache(maxsize=64)
def fetch_meta_deck(archetype: str, fmt: str) -> tuple[list[CardInfo], str]:
    """
    Fetch the canonical card list for a meta archetype, enriched with card data.

    Returns ``(cards, pilot_prompt)`` where ``pilot_prompt`` is the value of
    ``field_pilot_prompt`` from the Drupal node, or empty string when the field
    is unset.  Callers should pass the returned prompt to
    ``get_pilot_prompt(archetype, drupal_prompt=...)`` so the Drupal value
    takes precedence over the built-in default.
    """
    query = (
        "query MetaDeck($format: String!) { metaDecks(format: $format) {"
        " title cardsJson pilotPrompt } }"
    )
    try:
        data = _graphql(query, {"format": fmt})
    except requests.RequestException as exc:
        logger.warning("Meta deck fetch failed for %s / %s: %s", archetype, fmt, exc)
        return [], ""

    meta_list = data.get("metaDecks") or []
    match = next((m for m in meta_list if m.get("title") == archetype), None)
    if match is None:
        logger.warning("No meta_deck found for %s / %s", archetype, fmt)
        return [], ""

    pilot_prompt: str = match.get("pilotPrompt") or ""

    cards_json = str(match.get("cardsJson") or "")
    try:
        raw_cards: list[dict] = json.loads(cards_json) if cards_json else []
    except json.JSONDecodeError:
        logger.warning("Could not parse field_cards_json for %s", archetype)
        return [], pilot_prompt

    all_names = [c["name"] for c in raw_cards if c.get("name")]
    enrichment = _enrich_by_name(all_names)
    return _build_card_list(raw_cards, enrichment), pilot_prompt
