"""JSON endpoints called from the browser with fetch().

Game flow:
  GET  /api/game/word?difficulty=&exclude=  -> next prompt (definition + audio),
                                               never the spelling
  GET  /api/game/audio/<id>                 -> pronunciation mp3, proxied so the
                                               API key and the audio file name
                                               (which spells the word) stay on
                                               the server
  POST /api/game/answer                     -> checks a guess; reveals the word
                                               only when the guess is correct
  POST /api/game/reveal                     -> gives up on a word and reveals it
"""

import random
from functools import wraps

from flask import Response, jsonify, request, url_for

from spelling_game import dictionary, word_bank
from spelling_game.routes import api_bp
from spelling_game.routes.auth import get_current_user

MAX_ANSWER_LENGTH = 100
LOOKUP_ATTEMPTS = 5  # words to try if the dictionary has no entry for some


def _error(message: str, status: int):
    return jsonify(error=message), status


def api_login_required(view):
    """Like login_required, but answers 401 JSON instead of redirecting to a page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            return _error("Please log in to continue.", 401)
        return view(*args, **kwargs)

    return wrapped


def _dictionary_failure(error: dictionary.DictionaryError):
    if isinstance(error, dictionary.DictionaryNotConfigured):
        return _error(str(error), 503)
    return _error(str(error), 502)


def _parse_ids(raw: str) -> set[int]:
    return {int(part) for part in raw.split(",") if part.strip().isdigit()}


def _json_word_id():
    """Validate a JSON body containing an integer word "id".

    Returns (word, body, None) on success, or (None, body, error_response).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, data, _error("Send a JSON body.", 400)
    word_id = data.get("id")
    if not isinstance(word_id, int) or isinstance(word_id, bool):
        return None, data, _error("Expected an integer 'id'.", 400)
    word = word_bank.get_word(word_id)
    if word is None:
        return None, data, _error("Unknown word.", 404)
    return word, data, None


@api_bp.get("/game/word")
@api_login_required
def game_word():
    """Pick a random word of ?difficulty= that is not in ?exclude=1,2,3.

    Returns {"done": true} when every word of that difficulty was excluded.
    "available" is how many words exist at this difficulty.
    """
    difficulty = request.args.get("difficulty", "easy")
    if difficulty not in word_bank.DIFFICULTIES:
        return _error("Unknown difficulty.", 400)

    pool = word_bank.ids_for(difficulty)
    excluded = _parse_ids(request.args.get("exclude", ""))
    candidates = [i for i in pool if i not in excluded]
    if not candidates:
        return jsonify(done=True, available=len(pool))
    random.shuffle(candidates)

    for word_id in candidates[:LOOKUP_ATTEMPTS]:
        word = word_bank.WORDS[word_id]
        try:
            entry = dictionary.lookup(word.text)
        except dictionary.WordNotFound:
            continue
        except dictionary.DictionaryError as error:
            return _dictionary_failure(error)

        return jsonify(
            id=word_id,
            difficulty=difficulty,
            available=len(pool),
            length=len(word.text),
            definitions=entry["definitions"],
            part_of_speech=entry["part_of_speech"],
            audio_url=url_for("api.game_audio", word_id=word_id) if entry["audio"] else None,
        )

    if len(candidates) <= LOOKUP_ATTEMPTS:
        # Every remaining word was tried and none has a dictionary entry.
        return jsonify(done=True, available=len(pool))
    return _error("Could not find a usable dictionary entry. Please try again.", 502)


@api_bp.get("/game/audio/<int:word_id>")
@api_login_required
def game_audio(word_id: int):
    word = word_bank.get_word(word_id)
    if word is None:
        return _error("Unknown word.", 404)
    try:
        entry = dictionary.lookup(word.text)
        if not entry["audio"]:
            return _error("No audio for this word.", 404)
        audio = dictionary.fetch_audio(entry["audio"])
    except dictionary.WordNotFound:
        return _error("No audio for this word.", 404)
    except dictionary.DictionaryError as error:
        return _dictionary_failure(error)

    return Response(audio, mimetype="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@api_bp.post("/game/answer")
@api_login_required
def game_answer():
    """Body: {"id": int, "answer": str} -> {"correct": bool, "word": str | null}.

    The word is only included when the guess is correct, so a wrong guess can
    be retried without giving the spelling away.
    """
    word, data, error = _json_word_id()
    if error:
        return error
    answer = data.get("answer")
    if not isinstance(answer, str):
        return _error("Expected a string 'answer'.", 400)
    if len(answer) > MAX_ANSWER_LENGTH:
        return _error("Answer is too long.", 400)

    correct = answer.strip().lower() == word.text.lower()
    return jsonify(correct=correct, word=word.text if correct else None)


@api_bp.post("/game/reveal")
@api_login_required
def game_reveal():
    """Body: {"id": int} -> {"word": str}. For the "Show answer" button."""
    word, _, error = _json_word_id()
    if error:
        return error
    return jsonify(word=word.text)
