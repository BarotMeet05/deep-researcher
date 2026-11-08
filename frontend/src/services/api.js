/**
 * DeepResearcher API Service
 * Handles SSE streaming from FastAPI backend and LocalStorage persistence.
 */

const PASSCODE_STORAGE_KEY = 'deep_researcher_passcode';
const HISTORY_STORAGE_KEY = 'deep_researcher_history';

export function getStoredPasscode() {
  return localStorage.getItem(PASSCODE_STORAGE_KEY) || '';
}

export function setStoredPasscode(code) {
  if (code) {
    localStorage.setItem(PASSCODE_STORAGE_KEY, code.trim());
  } else {
    localStorage.removeItem(PASSCODE_STORAGE_KEY);
  }
}

export function getResearchHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to parse history from localStorage', e);
    return [];
  }
}

export function saveResearchToHistory(item) {
  try {
    const history = getResearchHistory();
    // Prepend new item, remove any existing with identical ID
    const filtered = history.filter((h) => h.id !== item.id);
    const updated = [item, ...filtered].slice(0, 30); // keep up to 30 reports
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('Failed to save to history', e);
    return [];
  }
}

export function deleteHistoryItem(id) {
  try {
    const history = getResearchHistory();
    const updated = history.filter((h) => h.id !== id);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('Failed to delete history item', e);
    return [];
  }
}

export function clearAllHistory() {
  localStorage.removeItem(HISTORY_STORAGE_KEY);
  return [];
}

/**
 * Sends a follow-up question about an existing dossier.
 * Returns { answer: "<markdown string>" }
 */
export async function followUpChat({ question, dossier = '', topic = '', passcode } = {}) {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const url = `${baseUrl}/api/v1/chat`;

  const headers = { 'Content-Type': 'application/json' };
  const code = passcode || getStoredPasscode();
  if (code) headers['X-App-Key'] = code;

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, dossier, topic }),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).error || detail; } catch (_) {}
    throw new Error(`Chat error ${response.status}: ${detail}`);
  }

  return response.json(); // { answer: string }
}

/**
 * Initiates SSE stream research call.
 * Uses fetch + ReadableStream for custom auth header support.
 */
export async function streamResearch({
  topic,
  maxIterations = 2,
  passcode,
  onStart,
  onPlanner,
  onSearcher,
  onCritic,
  onReport,
  onDone,
  onError,
  signal,
}) {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  const url = `${baseUrl}/api/v1/research/stream`;

  const headers = {
    'Content-Type': 'application/json',
  };

  const code = passcode || getStoredPasscode();
  if (code) {
    headers['X-App-Key'] = code;
  }

  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        topic,
        max_iterations: Number(maxIterations),
      }),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      onError?.(new Error('Research process was cancelled by user.'));
      return;
    }
    onError?.(new Error(`Network error connecting to backend: ${err.message}`));
    return;
  }

  if (response.status === 401) {
    const error = new Error('UNAUTHORIZED: Passcode is invalid or required.');
    error.statusCode = 401;
    onError?.(error);
    return;
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.message || errJson.detail || JSON.stringify(errJson);
    } catch (_) {}
    onError?.(new Error(`Server returned error ${response.status}: ${errorDetail}`));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || ''; // Keep incomplete part in buffer

      for (const block of parts) {
        if (!block.trim()) continue;

        let eventType = 'message';
        let dataStr = '';

        const lines = block.split('\n');
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.replace('event:', '').trim();
          } else if (line.startsWith('data:')) {
            dataStr = line.replace('data:', '').trim();
          }
        }

        if (!dataStr) continue;

        let parsedData;
        try {
          parsedData = JSON.parse(dataStr);
        } catch (e) {
          console.warn('Failed to parse SSE data block:', dataStr);
          continue;
        }

        switch (eventType) {
          case 'start':
            onStart?.(parsedData);
            break;
          case 'planner':
            onPlanner?.(parsedData);
            break;
          case 'searcher':
            onSearcher?.(parsedData);
            break;
          case 'critic':
            onCritic?.(parsedData);
            break;
          case 'report':
            onReport?.(parsedData);
            break;
          case 'done':
            onDone?.(parsedData);
            break;
          case 'error':
            onError?.(new Error(parsedData.error || 'Agent execution failed'));
            break;
          default:
            break;
        }
      }
    }
  } catch (streamErr) {
    if (streamErr.name === 'AbortError') {
      onError?.(new Error('Research process was stopped.'));
    } else {
      onError?.(streamErr);
    }
  }
}
