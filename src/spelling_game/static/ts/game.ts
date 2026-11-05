// Game screen logic, compiled to static/dist/game.js with `npm run build`.
//
// The server owns the words: it sends a word id, the definition(s) and an audio
// URL (both from Merriam-Webster), never the spelling. Guesses are checked by
// POSTing them to the server, which reveals the word only when the guess is
// correct or the player asks to see it.

const ROUND_LENGTH = 8;
const DIFFICULTIES = ["easy", "medium", "hard"];

interface WordPrompt {
  id: number;
  available: number;
  length: number;
  definitions: string[];
  part_of_speech: string | null;
  audio_url: string | null;
}

interface RoundOver {
  done: true;
  available: number;
}

interface AnswerResult {
  correct: boolean;
  word: string | null;
}

// Provided by the shared static/js/spelling.js (home-page stats). Optional here.
interface SpellingLib {
  stats(): { rounds: number; correct: number; total: number };
  save(key: string, value: unknown): void;
}

class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

const els = {
  error: byId<HTMLDivElement>("game-error"),
  round: byId<HTMLSpanElement>("round"),
  score: byId<HTMLElement>("score"),
  title: byId<HTMLElement>("game-title"),
  playButton: byId<HTMLButtonElement>("play-word"),
  audio: byId<HTMLAudioElement>("word-audio"),
  audioStatus: byId<HTMLElement>("audio-status"),
  definitionBox: byId<HTMLElement>("definition-box"),
  partOfSpeech: byId<HTMLElement>("part-of-speech"),
  definitions: byId<HTMLOListElement>("definitions"),
  letterCount: byId<HTMLElement>("letter-count"),
  form: byId<HTMLFormElement>("spelling-form"),
  answer: byId<HTMLInputElement>("answer"),
  checkButton: byId<HTMLButtonElement>("check-answer"),
  feedback: byId<HTMLElement>("feedback"),
  revealButton: byId<HTMLButtonElement>("reveal-word"),
  nextButton: byId<HTMLButtonElement>("next-word"),
};

const csrfToken =
  document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";

const requested = new URLSearchParams(window.location.search).get("difficulty") ?? "";
const difficulty = DIFFICULTIES.includes(requested) ? requested : "easy";

// ---- game state ----------------------------------------------------------
let askedIds: number[] = [];
let roundTotal = ROUND_LENGTH;
let score = 0;
let current: WordPrompt | null = null;
let resolved = false; // this word is finished (answered correctly or revealed)
let complete = false; // the round is over
let busy = false;

// ---- server calls --------------------------------------------------------
async function api<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-CSRFToken", csrfToken);

  const response = await fetch(url, { ...init, headers });

  if (response.status === 401) {
    // Session expired: log in again, then come back to this page.
    const back = window.location.pathname + window.location.search;
    window.location.href = `/login?next=${encodeURIComponent(back)}`;
    throw new ApiError("Please log in to continue.", 401);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (e.g. a server error page); use the generic message below.
  }

  if (!response.ok) {
    const message =
      body && typeof body === "object" && "error" in body && typeof body.error === "string"
        ? body.error
        : `Request failed (${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return body as T;
}

function postJson<T>(url: string, payload: unknown): Promise<T> {
  return api<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---- UI helpers ----------------------------------------------------------
function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function showError(message: string): void {
  els.error.textContent = message;
  els.error.hidden = false;
}

function clearError(): void {
  els.error.hidden = true;
  els.error.textContent = "";
}

function showFeedback(message: string, style: string): void {
  els.feedback.className = `alert alert-${style} mt-3 mb-0`;
  els.feedback.textContent = message;
}

function clearFeedback(): void {
  els.feedback.className = "mt-3";
  els.feedback.textContent = "";
}

function updateRoundLabel(): void {
  els.round.textContent = `${difficulty} - Word ${askedIds.length} of ${roundTotal}`;
}

function stopAudio(): void {
  els.audio.pause();
}

function listenForPlaybackEnd(): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      els.audio.removeEventListener("ended", onEnded);
      els.audio.removeEventListener("error", onError);
    };
    const onEnded = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("The pronunciation could not be loaded."));
    };
    els.audio.addEventListener("ended", onEnded);
    els.audio.addEventListener("error", onError);
  });
}

async function playWord(): Promise<void> {
  if (!current?.audio_url) {
    return;
  }
  els.audioStatus.textContent = "Playing word...";
  els.answer.focus();
  try {
    els.audio.currentTime = 0;
    await els.audio.play();
    await listenForPlaybackEnd();
    els.audioStatus.textContent = "Listen again whenever you need.";
  } catch {
    els.audioStatus.textContent = "The pronunciation could not be played. Press Play word to try again.";
  }
}

function renderPrompt(prompt: WordPrompt): void {
  current = prompt;
  resolved = false;

  updateRoundLabel();
  els.letterCount.textContent = String(prompt.length);
  els.partOfSpeech.textContent = prompt.part_of_speech ?? "";
  els.definitions.replaceChildren(
    ...prompt.definitions.map((text) => {
      const item = document.createElement("li");
      item.textContent = text; // textContent, never innerHTML: text comes from an API
      return item;
    }),
  );
  els.definitionBox.hidden = false;

  stopAudio();
  if (prompt.audio_url) {
    els.audio.src = prompt.audio_url;
    els.playButton.disabled = false;
    els.audioStatus.textContent = "Press Play word to listen.";
  } else {
    els.audio.removeAttribute("src");
    els.playButton.disabled = true;
    els.audioStatus.textContent = "No pronunciation is available for this word. Use the definition.";
  }

  els.answer.value = "";
  els.answer.disabled = false;
  els.checkButton.disabled = false;
  els.revealButton.disabled = false;
  els.nextButton.disabled = true;
  els.nextButton.textContent = askedIds.length >= roundTotal ? "See results" : "Next word";
  clearFeedback();
  (prompt.audio_url ? els.playButton : els.answer).focus();
}

function finishWord(): void {
  resolved = true;
  els.answer.disabled = true;
  els.checkButton.disabled = true;
  els.revealButton.disabled = true;
  els.nextButton.disabled = false;
  els.nextButton.focus();
}

function saveStats(): void {
  const library = (globalThis as { Spelling?: SpellingLib }).Spelling;
  try {
    if (!library) {
      throw new Error("stats library not loaded");
    }
    const stats = library.stats();
    stats.rounds += 1;
    stats.correct += score;
    stats.total += askedIds.length;
    library.save("spelling.stats", stats);
    els.audioStatus.textContent = "Round saved! See your stats on the home page.";
  } catch {
    els.audioStatus.textContent =
      "Practice finished, but browser storage was unavailable. Stats could not be saved.";
  }
}

function finishRound(): void {
  complete = true;
  stopAudio();
  els.title.textContent = "Practice complete!";
  els.definitionBox.hidden = true;
  showFeedback(
    `You spelled ${score} of ${askedIds.length} words correctly. Play again to keep practicing.`,
    "success",
  );
  els.nextButton.textContent = "Play again";
  els.nextButton.disabled = false;
  els.playButton.disabled = true;
  els.answer.disabled = true;
  els.checkButton.disabled = true;
  els.revealButton.disabled = true;
  saveStats();
  els.nextButton.focus();
}

// ---- game flow -----------------------------------------------------------
async function loadNextWord(): Promise<void> {
  if (busy) {
    return;
  }
  busy = true;
  clearError();
  els.nextButton.disabled = true;
  try {
    const params = new URLSearchParams({ difficulty, exclude: askedIds.join(",") });
    const next = await api<WordPrompt | RoundOver>(`/api/game/word?${params}`);

    roundTotal = Math.min(ROUND_LENGTH, next.available);
    if ("done" in next) {
      if (askedIds.length === 0) {
        els.audioStatus.textContent = "There are no words at this difficulty yet.";
      } else {
        finishRound();
      }
      return;
    }
    askedIds.push(next.id);
    renderPrompt(next);
  } catch (error) {
    showError(errorMessage(error));
    // Let the player try again; the same next button re-requests the word.
    els.nextButton.disabled = false;
  } finally {
    busy = false;
  }
}

async function checkAnswer(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  if (resolved || !current || busy) {
    return;
  }
  const typed = els.answer.value.trim();
  if (!typed) {
    showFeedback("Type your spelling first.", "warning");
    els.answer.focus();
    return;
  }

  busy = true;
  clearError();
  els.checkButton.disabled = true;
  try {
    const result = await postJson<AnswerResult>("/api/game/answer", { id: current.id, answer: typed });
    if (result.correct) {
      score += 1;
      els.score.textContent = String(score);
      showFeedback("Correct! Great spelling.", "success");
      finishWord();
    } else {
      showFeedback("Almost! Listen again and give it another try.", "warning");
      els.checkButton.disabled = false;
      els.answer.focus();
      els.answer.select();
    }
  } catch (error) {
    els.checkButton.disabled = false;
    showError(errorMessage(error));
  } finally {
    busy = false;
  }
}

async function revealWord(): Promise<void> {
  if (resolved || !current || busy) {
    return;
  }
  busy = true;
  clearError();
  try {
    const result = await postJson<{ word: string }>("/api/game/reveal", { id: current.id });
    showFeedback(`The spelling is "${result.word}". Try to remember it for next time!`, "info");
    finishWord();
  } catch (error) {
    showError(errorMessage(error));
  } finally {
    busy = false;
  }
}

function onNext(): void {
  if (complete) {
    window.location.reload();
  } else if (resolved || current === null) {
    // current === null: the very first word failed to load, so retry it.
    if (askedIds.length >= roundTotal && current !== null) {
      finishRound();
    } else {
      void loadNextWord();
    }
  }
}

els.playButton.addEventListener("click", () => void playWord());
els.form.addEventListener("submit", (event) => void checkAnswer(event));
els.revealButton.addEventListener("click", () => void revealWord());
els.nextButton.addEventListener("click", onNext);
window.addEventListener("pagehide", stopAudio);

// Start the round straight away; the difficulty was chosen on the home page.
els.answer.disabled = true;
els.checkButton.disabled = true;
els.revealButton.disabled = true;
void loadNextWord();

export {};
