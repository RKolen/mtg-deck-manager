"""Oracle text helpers with no game_object dependencies."""


def oracle_has_keyword(oracle_text: str, keyword: str) -> bool:
    """Return True when oracle text contains the keyword (case-insensitive)."""
    return keyword.lower() in oracle_text.lower()
