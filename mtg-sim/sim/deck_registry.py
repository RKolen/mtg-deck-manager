"""
Fetches deck lists from Drupal JSON:API for use in Forge simulations.

Returns card lists in the format ForgeAdapter.start_game() expects:
  [{"name": "Lightning Bolt", "quantity": 4, "sideboard": False}, ...]

Forge card names match Scryfall canonical names exactly, which is what
Drupal stores in the node title field.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

DRUPAL_URL: str = os.environ.get("DRUPAL_URL", "")
DRUPAL_USER: str = os.environ.get("DRUPAL_USER", "")
DRUPAL_PASS: str = os.environ.get("DRUPAL_PASS", "")


def _get_auth() -> tuple[str, str]:
    """Return the (user, pass) tuple for Drupal HTTP Basic Auth."""
    return (DRUPAL_USER, DRUPAL_PASS)


def fetch_player_deck(deck_nid: int) -> list[dict]:
    """
    Fetch all deck_card nodes for a deck and return a card list for Forge.

    Args:
        deck_nid: Drupal node ID of the deck.

    Returns:
        List of dicts with ``name``, ``quantity``, and ``sideboard`` keys.
    """
    url: str | None = (
        f"{DRUPAL_URL}/jsonapi/node/deck_card"
        f"?filter[field_deck.drupal_internal__nid]={deck_nid}"
        "&include=field_card"
        "&fields[node--deck_card]=field_quantity,field_is_sideboard,field_card"
        "&fields[node--mtg_card]=title"
        "&page[limit]=200"
    )
    cards: list[dict] = []
    while url:
        resp = requests.get(url, auth=_get_auth(), timeout=30)
        resp.raise_for_status()
        body = resp.json()
        card_map: dict[str, str] = {
            node["id"]: node["attributes"]["title"]
            for node in (body.get("included") or [])
        }
        for node in body.get("data", []):
            qty = int((node["attributes"].get("field_quantity") or 1))
            sideboard = bool(node["attributes"].get("field_is_sideboard", False))
            card_ref = (
                node.get("relationships", {})
                .get("field_card", {})
                .get("data") or {}
            )
            name = card_map.get(card_ref.get("id", ""), "")
            if name:
                cards.append({"name": name, "quantity": qty, "sideboard": sideboard})
        next_link = body.get("links", {}).get("next", {})
        url = next_link.get("href") if next_link else None
    return cards


@lru_cache(maxsize=64)
def fetch_meta_deck(archetype: str, fmt: str) -> list[dict]:
    """
    Fetch the canonical card list for a meta archetype from Drupal.

    The ``field_cards`` value is stored as a JSON string:
    ``[{"name": "...", "quantity": N, "sideboard": bool}]``

    Args:
        archetype: Archetype title matching a meta_deck node (e.g. "Jund").
        fmt: MTG format name (e.g. "Modern").

    Returns:
        List of card dicts, or an empty list when no node is found.
    """
    url = (
        f"{DRUPAL_URL}/jsonapi/node/meta_deck"
        f"?filter[title]={urllib.parse.quote(archetype)}"
        f"&filter[field_format]={urllib.parse.quote(fmt)}"
        "&fields[node--meta_deck]=title,field_cards"
        "&page[limit]=1"
    )
    resp = requests.get(url, auth=_get_auth(), timeout=30)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data", [])
    if not data:
        logger.warning("No meta_deck found for %s / %s", archetype, fmt)
        return []
    raw = (data[0]["attributes"].get("field_cards") or {})
    cards_json = raw.get("value", "") if isinstance(raw, dict) else str(raw)
    try:
        return json.loads(cards_json) if cards_json else []
    except json.JSONDecodeError:
        logger.warning("Could not parse field_cards JSON for %s", archetype)
        return []
