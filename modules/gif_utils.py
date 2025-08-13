import time
import requests
from typing import List, Optional

OTA_BASE_URL = "https://api.otakugifs.xyz"
_REACTIONS_CACHE: List[str] = []
_REACTIONS_CACHE_TS: float = 0.0
_REACTIONS_TTL_SECONDS: int = 3600

# Maps command names we already use (or friendlier aliases) to OtakuGIFs reactions
REACTION_ALIASES = {
    # one-to-one
    "hug": "hug",
    "kiss": "kiss",
    "pat": "pat",
    "slap": "slap",
    "blush": "blush",
    "shrug": "shrug",
    "pout": "pout",
    "cry": "cry",
    "tickle": "tickle",
    "dance": "dance",
    "wave": "wave",
    "laugh": "laugh",
    "wink": "wink",
    "cheer": "cheers",
    "clap": "clap",
    "applaud": "clap",
    "smirk": "smug",
    # best-effort mappings where exact reaction does not exist
    "kick": "punch",
    "roast": "smug",
    "highfive": "brofist",
    "salute": "thumbsup",
    "think": "confused",
    "spin": "roll",
    "bully": "smack",
    "kill": "evillaugh",
    "kuru": "roll",
}

def get_otaku_gif(reaction: str, fmt: str = "gif") -> Optional[str]:
    """Return a single GIF URL for the given reaction from OtakuGIFs.

    Args:
        reaction: A valid OtakuGIFs reaction (e.g., 'hug', 'kiss').
        fmt: One of 'gif', 'webp', 'avif' (defaults to gif).

    Returns:
        URL string if successful, else None.
    """
    try:
        response = requests.get(
            f"{OTA_BASE_URL}/gif",
            params={"reaction": reaction, "format": fmt.lower()},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("url")
    except requests.exceptions.RequestException as exc:
        print(f"OtakuGIFs request failed for reaction '{reaction}': {exc}")
        return None

def get_all_reactions() -> List[str]:
    """Fetch the full list of available reactions (no cache)."""
    try:
        response = requests.get(f"{OTA_BASE_URL}/gif/allreactions", timeout=10)
        response.raise_for_status()
        data = response.json() or {}
        return data.get("reactions", [])
    except requests.exceptions.RequestException as exc:
        print(f"Failed to fetch OtakuGIFs reactions: {exc}")
        return []

def get_cached_reactions() -> List[str]:
    """Return reactions with a simple TTL cache to avoid frequent network calls."""
    global _REACTIONS_CACHE, _REACTIONS_CACHE_TS
    now = time.time()
    if _REACTIONS_CACHE and (now - _REACTIONS_CACHE_TS) < _REACTIONS_TTL_SECONDS:
        return _REACTIONS_CACHE
    _REACTIONS_CACHE = get_all_reactions()
    _REACTIONS_CACHE_TS = now
    return _REACTIONS_CACHE

def resolve_reaction(name: str, available: Optional[List[str]] = None) -> Optional[str]:
    """Resolve a friendly command name into a valid OtakuGIFs reaction.

    Prioritizes exact matches in `available`, then falls back to `REACTION_ALIASES`.
    """
    if not name:
        return None
    lower = name.lower()
    if available is None:
        available = get_cached_reactions()
    if lower in available:
        return lower
    return REACTION_ALIASES.get(lower)
