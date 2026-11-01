"""Token-aware partial keyword matching used by role search.

Job titles are full of glued and punctuated words such as ``GenAI``,
``AI/ML``, ``Front-End`` or ``Full Stack``.  Plain ``LIKE '%ai%'`` catches
unrelated words (``Affairs``, ``Spain``, ``paid``), so instead we split text
into word tokens and match query tokens against whole tokens (short queries)
or token prefixes (longer queries).

Examples:
    >>> partial_match("AI", "GenAI Engineer")
    True
    >>> partial_match("AI", "Deal Team - Business Affairs")
    False
    >>> partial_match("front", "Front-End Developer")
    True
    >>> partial_match("frontend", "Front End Developer")
    True
    >>> partial_match("data eng", "Senior Data Platform Engineer")
    True
"""

import re
from typing import List, Optional

# Split camelCase / PascalCase and letter <-> digit boundaries so that
# "GenAI" -> "Gen AI", "Python3" -> "Python 3" and "AI/ML" -> "AI ML".
_BOUNDARY = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])"
    r"|(?<=[A-Z])(?=[A-Z][a-z])"
    r"|(?<=[A-Za-z])(?=[0-9])"
    r"|(?<=[0-9])(?=[A-Za-z])"
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Query tokens shorter than this must match a whole title token, so "AI"
# matches "AI Engineer" / "GenAI" / "AI/ML" but not "Airflow" or "Airbnb".
# Longer tokens match as prefixes ("eng" -> "engineer").
_MIN_PREFIX_QUERY_LEN = 3

# Query tokens at least this long may also match words that are glued
# together with punctuation/whitespace ("Front End" -> "frontend").
_MIN_COMPACT_QUERY_LEN = 4


def tokenize(text: Optional[str]) -> List[str]:
    """Lowercase ``text`` and split it into alphanumeric word tokens."""
    if not text:
        return []
    spaced = _BOUNDARY.sub(" ", text)
    return [token for token in _NON_ALNUM.split(spaced.lower()) if token]


def _token_matches(query_token: str, tokens: List[str]) -> bool:
    if len(query_token) < _MIN_PREFIX_QUERY_LEN:
        # "AI", "ML", "UX", "C": whole-token match only.
        return query_token in tokens
    # Prefix match covers partial words: "eng" -> "engineer", "soft" -> "software".
    if any(token.startswith(query_token) for token in tokens):
        return True
    # Compact match covers titles split by punctuation/spaces:
    # "frontend" -> "front end", "fullstack" -> "full stack".
    if len(query_token) >= _MIN_COMPACT_QUERY_LEN:
        return query_token in "".join(tokens)
    return False


def partial_match(query: Optional[str], *fields: Optional[str]) -> bool:
    """Return True when every query token partially matches the given fields.

    Matching is case-insensitive and AND-based across query words, so
    ``"data eng"`` matches both "Senior Data Platform Engineer" and
    "Data Engineer" but requires both words to be present.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return True

    field_tokens = [token for field in fields if field for token in tokenize(field)]
    if not field_tokens:
        return False

    return all(_token_matches(token, field_tokens) for token in query_tokens)
