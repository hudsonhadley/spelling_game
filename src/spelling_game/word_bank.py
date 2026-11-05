"""The words the game quizzes players on, grouped by difficulty.

TODO: Temporary built-in list. Replace with a `words` table in the database
(managed by admins on the /words page). A word's id is its index in WORDS, so
ids are only stable until the list is edited; a database primary key fixes that.
"""

from typing import NamedTuple

DIFFICULTIES = ("easy", "medium", "hard")


class Word(NamedTuple):
    text: str
    difficulty: str


WORDS: list[Word] = [
    *(Word(text, "easy") for text in (
        "friend", "because", "school", "people", "answer",
        "family", "animal", "pencil", "orange", "water",
    )),
    *(Word(text, "medium") for text in (
        "calendar", "library", "island", "receive", "knowledge",
        "separate", "necessary", "rhythm", "favorite", "temperature",
    )),
    *(Word(text, "hard") for text in (
        "accommodate", "bureaucracy", "conscience", "embarrass", "liaison",
        "mischievous", "pharaoh", "questionnaire", "silhouette", "surveillance",
    )),
]


def get_word(word_id: int) -> Word | None:
    """Return the word with this id, or None if the id is out of range."""
    if 0 <= word_id < len(WORDS):
        return WORDS[word_id]
    return None


def ids_for(difficulty: str) -> list[int]:
    """Ids of every word at this difficulty."""
    return [i for i, word in enumerate(WORDS) if word.difficulty == difficulty]
