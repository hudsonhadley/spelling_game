"""Client for the Merriam-Webster Collegiate Dictionary API.

Looks a word up and returns its definitions, part of speech and the file name
of its pronunciation audio, and downloads that audio. The API key comes from
the MW_API_KEY config value and is only ever used here on the server.

API docs: https://dictionaryapi.com/products/api-collegiate-dictionary
"""

import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from urllib.parse import quote

from flask import current_app

ENTRY_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={key}"
AUDIO_URL = "https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{name}.mp3"

TIMEOUT_SECONDS = 8
MAX_DEFINITIONS = 3
MASK = "_____"

_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
_AUDIO_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class DictionaryError(Exception):
    """Something went wrong talking to Merriam-Webster."""


class DictionaryNotConfigured(DictionaryError):
    """No MW_API_KEY has been set."""


class WordNotFound(DictionaryError):
    """The dictionary has no usable entry for this word."""


def _audio_subdirectory(name: str) -> str:
    """Folder rule from the MW docs for building an audio URL."""
    if name.startswith("bix"):
        return "bix"
    if name.startswith("gg"):
        return "gg"
    if not name[0].isalpha():  # starts with a digit or punctuation
        return "number"
    return name[0]


def _mask_word(text: str, word: str) -> str:
    """Hide the word (and forms like 'word's' or 'words') inside a definition."""
    return re.sub(rf"\b{re.escape(word)}\w*", MASK, text, flags=re.IGNORECASE)


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        # Deliberately not including the URL: it contains the API key.
        raise DictionaryError(f"Dictionary service returned HTTP {error.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise DictionaryError("Could not reach the dictionary service.") from None


@lru_cache(maxsize=256)
def _lookup_cached(word: str, key: str) -> dict:
    body = _http_get(ENTRY_URL.format(word=quote(word), key=quote(key)))
    try:
        data = json.loads(body)
    except ValueError:
        # MW answers a bad/missing key with a plain-text message, not JSON.
        raise DictionaryError("Dictionary service rejected the request (check MW_API_KEY).") from None

    # When the word is unknown MW returns a list of spelling suggestions (strings).
    entries = [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []
    wanted = word.lower()
    matches = [
        entry for entry in entries
        if entry.get("hwi", {}).get("hw", "").replace("*", "").lower() == wanted
    ]
    with_definitions = [entry for entry in matches if entry.get("shortdef")]
    if not with_definitions:
        raise WordNotFound(f"No dictionary entry for {word!r}.")
    entry = with_definitions[0]

    audio = None
    for candidate in matches:
        for pronunciation in candidate.get("hwi", {}).get("prs", []):
            name = pronunciation.get("sound", {}).get("audio")
            if name and _AUDIO_NAME_RE.match(name):
                audio = name
                break
        if audio:
            break

    return {
        "definitions": [_mask_word(text, word) for text in entry["shortdef"][:MAX_DEFINITIONS]],
        "part_of_speech": entry.get("fl"),
        "audio": audio,
    }


def lookup(word: str) -> dict:
    """Return {"definitions": [...], "part_of_speech": str | None, "audio": str | None}.

    Raises WordNotFound, DictionaryNotConfigured or DictionaryError. Successful
    lookups are cached in memory to stay within the API's daily request limit.
    """
    if not _WORD_RE.match(word):
        raise WordNotFound(f"Not a valid word: {word!r}.")
    key = current_app.config.get("MW_API_KEY")
    if not key:
        raise DictionaryNotConfigured("MW_API_KEY is not set in .appenv.")
    return _lookup_cached(word, key)


@lru_cache(maxsize=64)
def _audio_cached(name: str) -> bytes:
    return _http_get(AUDIO_URL.format(subdir=_audio_subdirectory(name), name=name))


def fetch_audio(audio_name: str) -> bytes:
    """Download a pronunciation mp3 (the name comes from lookup()["audio"])."""
    if not _AUDIO_NAME_RE.match(audio_name):
        raise DictionaryError("Invalid audio name.")
    return _audio_cached(audio_name)
