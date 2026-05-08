"""
Deck deduction classifier — infers archetype from observed plays.

Training:
  Fetches meta_deck canonical lists from Drupal JSON:API.
  Each archetype's full card list becomes a document (space-joined names).
  A TF-IDF vectoriser + LogisticRegression classifier is trained on these.

Inference:
  Observed plays (card names) are joined and vectorised.
  P(archetype) is returned for all known archetypes.

Persistence:
  The trained model is saved to model.joblib so it survives restarts.
  Call /train to rebuild it whenever meta_deck nodes are updated.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = Path(__file__).parent / "model.joblib"
logger = logging.getLogger(__name__)


def _document_from_cards(cards: list[dict]) -> str:
    """Convert a list of card dicts into a weighted text document."""
    parts: list[str] = []
    for entry in cards:
        name = entry.get("name", "")
        qty = int(entry.get("quantity", 1))
        parts.extend([name] * qty)
    return " ".join(parts)


def _fetch_all_meta_decks(drupal_url: str, auth: tuple[str, str]) -> tuple[list[str], list[str]]:
    """
    Fetch all meta_deck nodes from Drupal and return (documents, labels).

    Paginates through all pages of results.
    """
    documents: list[str] = []
    labels: list[str] = []
    url: str | None = (
        f"{drupal_url}/jsonapi/node/meta_deck"
        "?fields[node--meta_deck]=title,field_cards"
        "&page[limit]=100"
    )
    while url:
        resp = requests.get(url, auth=auth, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        for node in body.get("data", []):
            title = node["attributes"].get("title", "")
            cards_raw = node["attributes"].get("field_cards", {})
            raw = (
                cards_raw.get("value", "")
                if isinstance(cards_raw, dict)
                else str(cards_raw)
            )
            try:
                cards = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                cards = []
            doc = _document_from_cards(cards)
            if doc and title:
                documents.append(doc)
                labels.append(title)
        next_link = body.get("links", {}).get("next", {})
        url = next_link.get("href") if next_link else None
    return documents, labels


class DeckClassifier:
    """Bayesian-style archetype classifier backed by scikit-learn."""

    def __init__(self) -> None:
        """Initialise and attempt to load a previously saved model."""
        self.pipeline: Pipeline | None = None
        self.archetypes: list[str] = []
        self._try_load()

    def classify(self, plays: list[dict]) -> dict:
        """
        Return P(archetype) for all known archetypes given observed plays.

        Args:
            plays: List of dicts with at least a ``card_name`` key.

        Returns:
            Dict with ``archetypes`` list or an ``error`` key when untrained.
        """
        if self.pipeline is None:
            return {"error": "Model not trained. POST /train first.", "archetypes": []}
        query = " ".join(p["card_name"] for p in plays if p.get("card_name"))
        if not query.strip():
            return {
                "archetypes": [{"name": a, "probability": 0.0} for a in self.archetypes]
            }
        probs = self.pipeline.predict_proba([query])[0]
        results = sorted(
            [
                {"name": cls, "probability": round(float(p), 4)}
                for cls, p in zip(self.pipeline.classes_, probs)
            ],
            key=lambda x: x["probability"],
            reverse=True,
        )
        return {"archetypes": results}

    def train_from_drupal(self, drupal_url: str, api_user: str, api_pass: str) -> int:
        """
        Fetch all meta_deck nodes from Drupal JSON:API and train the model.

        Args:
            drupal_url: Base URL of the Drupal site.
            api_user: HTTP Basic Auth username.
            api_pass: HTTP Basic Auth password.

        Returns:
            Number of archetypes trained on, or 0 if no data was found.
        """
        auth = (api_user, api_pass)
        documents, labels = _fetch_all_meta_decks(drupal_url, auth)
        if not documents:
            logger.warning("No meta_deck documents found — model not trained.")
            return 0
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                min_df=1,
                sublinear_tf=True,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=1.0,
                solver="lbfgs",
            )),
        ])
        pipeline.fit(documents, labels)
        self.pipeline = pipeline
        self.archetypes = list(pipeline.named_steps['clf'].classes_)
        joblib.dump(pipeline, MODEL_PATH)
        logger.info("Trained on %d archetypes, saved to %s", len(self.archetypes), MODEL_PATH)
        return len(self.archetypes)

    def _try_load(self) -> None:
        """Load a previously saved model from disk if available."""
        if MODEL_PATH.exists():
            try:
                loaded = joblib.load(MODEL_PATH)
                self.pipeline = loaded
                if self.pipeline is not None:
                    self.archetypes = list(self.pipeline.named_steps['clf'].classes_)
                logger.info(
                    "Loaded classifier from %s (%d archetypes)",
                    MODEL_PATH,
                    len(self.archetypes),
                )
            except (OSError, ValueError) as exc:
                logger.warning("Could not load model: %s", exc)
