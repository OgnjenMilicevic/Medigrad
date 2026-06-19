const BACKEND_URL = ''; // same-origin when served by Flask

// --- Session ID (student name / number) attached to every logged action ---
let _sessionId = '';
export function setSessionId(id) { _sessionId = (id || '').trim(); }
export function getSessionId() { return _sessionId; }

/**
 * Build a full backend URL from a relative endpoint.
 * Accepts either "upload" or "/upload".
 */
function buildUrl(endpoint) {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${BACKEND_URL}${cleanEndpoint}`;
}

/**
 * Safely try to parse a response as JSON.
 * Returns null if parsing fails.
 */
async function tryParseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * Normalize backend/network errors into a single Error.
 */
async function makeRequestError(response, fallbackMessage = 'Request failed.') {
  const data = await tryParseJson(response);
  const message = data?.error || data?.message || fallbackMessage;
  return new Error(message);
}

/**
 * Generic JSON request helper.
 */
async function requestJson(endpoint, options = {}, fallbackMessage = 'Request failed.') {
  const response = await fetch(buildUrl(endpoint), {
    credentials: 'same-origin',
    ...options,
  });

  if (!response.ok) {
    throw await makeRequestError(response, fallbackMessage);
  }

  const data = await tryParseJson(response);

  // Async job protocol: a 202 with { status: 'pending', job_id } means the
  // work is running in a server worker process. Poll /jobs/<id> until done,
  // so callers receive the final result exactly as if it were synchronous.
  if (response.status === 202 && data && data.status === 'pending' && data.job_id) {
    return await pollJob(data.job_id, fallbackMessage);
  }

  return data ?? {};
}

/**
 * Poll an async job to completion. Resolves with the result payload, or
 * throws with the worker's error message.
 */
async function pollJob(jobId, fallbackMessage, { intervalMs = 600, timeoutMs = 600000 } = {}) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const response = await fetch(buildUrl(`/jobs/${jobId}`), {
      credentials: 'same-origin',
    });
    if (!response.ok) {
      throw await makeRequestError(response, fallbackMessage);
    }
    const data = await tryParseJson(response) ?? {};

    if (data.status === 'done') {
      return data.result ?? {};
    }
    if (data.status === 'error') {
      throw new Error(data.error || fallbackMessage);
    }
    // status === 'pending' — wait and poll again.
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('The operation timed out. Please try again.');
}

/**
 * Generic blob request helper.
 */
async function requestBlob(endpoint, options = {}, fallbackMessage = 'Download failed.') {
  const response = await fetch(buildUrl(endpoint), {
    credentials: 'same-origin',
    ...options,
  });

  if (!response.ok) {
    throw await makeRequestError(response, fallbackMessage);
  }

  return await response.blob();
}

/**
 * Upload a data file to the backend.
 * @param {FormData} formData
 * @returns {Promise<Object>}
 */
export async function uploadFile(formData) {
  if (_sessionId && !formData.has('session_id')) formData.append('session_id', _sessionId);
  return requestJson('/upload', {
    method: 'POST',
    body: formData,
  }, 'File upload failed.');
}

/**
 * Run a configured analysis or plotting task.
 * @param {Object} config
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
export async function runConfiguredTask(config, payload) {
  if (!config?.endpoint) {
    throw new Error('Task config is missing an endpoint.');
  }

  const body = { ...(payload || {}) };
  if (_sessionId) body.session_id = _sessionId;

  return requestJson(`/${config.endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, `Failed to run task: ${config.title || config.endpoint}`);
}

/**
 * Create a new blank, editable dataset of the given shape.
 */
export async function newBlankDataset({ rows, cols, column_names }) {
  return requestJson('/new-blank', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, cols, column_names, session_id: _sessionId || undefined }),
  }, 'Could not create a blank dataset.');
}

/**
 * Add a new column by splitting a pasted delimited string.
 */
export async function addColumnFromText({ name, text, delimiter, trim, drop_empty, as_numeric }) {
  return requestJson('/add-column-from-text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name, text, delimiter, trim, drop_empty, as_numeric,
      session_id: _sessionId || undefined,
    }),
  }, 'Could not add the column.');
}

/**
 * Fetch the list of built-in example datasets.
 */
export async function listExamples() {
  return requestJson('/examples', { method: 'GET' }, 'Could not list examples.');
}

/**
 * Load a built-in example dataset by id.
 */
export async function loadExample(datasetId) {
  return requestJson(`/examples/${datasetId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: _sessionId || undefined }),
  }, 'Could not load example dataset.');
}

/**
 * Fetch the MFUB course-materials manifest.
 */
export async function getMfubManifest() {
  return requestJson('/mfub/manifest', { method: 'GET' }, 'Could not load MFUB materials.');
}

/**
 * Fetch a rendered MFUB markdown item as HTML.
 */
export async function getMfubMarkdown(filename) {
  return requestJson(`/mfub/markdown/${encodeURIComponent(filename)}`, { method: 'GET' },
    'Could not load that material.');
}

/**
 * Fetch the most recent activity-log lines for the live log panel.
 */
export async function getLogTail(n = 200) {
  return requestJson(`/log-tail?n=${encodeURIComponent(n)}`, { method: 'GET' },
    'Could not load the activity log.');
}

/**
 * Ask the backend where the local activity log is stored.
 */
export async function getLogLocation() {
  return requestJson('/log-location', { method: 'GET' }, 'Could not get log location.');
}

/**
 * Build a direct browser download URL for CSV/XLSX dataset download.
 * This matches the current behavior in main.js where window.location.href is used.
 * @param {'csv'|'xlsx'} fileType
 * @param {string} filename
 * @returns {string}
 */
export function getDatasetDownloadUrl(fileType, filename = 'data') {
  const params = new URLSearchParams({
    type: fileType,
    filename,
  });

  return buildUrl(`/download?${params.toString()}`);
}

/**
 * Download a generated XLSX report as a Blob.
 * @param {string} filename
 * @param {Object} tables
 * @returns {Promise<Blob>}
 */
export async function downloadReportFile(filename, tables) {
  return requestBlob('/download-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename,
      tables,
    }),
  }, 'Report download failed.');
}

/**
 * Trigger browser download from a Blob.
 * @param {Blob} blob
 * @param {string} filename
 */
export function triggerBrowserDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');

  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();

  window.URL.revokeObjectURL(url);
}

/**
 * Run automatic column correction.
 * @returns {Promise<Object>}
 */
export async function correctColumns() {
  return requestJson('/wrangling/correct-columns', {
    method: 'POST',
  }, 'Column correction failed.');
}

/**
 * Run numerical QC.
 * @returns {Promise<Object>}
 */
export async function runNumericalQC() {
  return requestJson('/description/numerical-qc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_sessionId ? { session_id: _sessionId } : {}),
  }, 'Numerical QC failed.');
}

/**
 * Update a single cell value.
 * @param {Object} params
 * @param {number} params.row
 * @param {number} params.col
 * @param {*} params.newValue
 * @param {boolean} [params.force=false]
 * @returns {Promise<Object>}
 */
export async function updateCell({ row, col, newValue, force = false }) {
  return requestJson('/update-cell', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      row,
      col,
      newValue,
      force,
    }),
  }, 'Cell update failed.');
}

/**
 * Update column structure (rename, add, remove).
 * Examples:
 * - { action: 'rename', oldName: 'A', newName: 'B' }
 * - { action: 'remove', name: 'A' }
 * - { action: 'add', name: 'NewColumn', index: 2 }
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
export async function updateColumn(payload) {
  return requestJson('/update-column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 'Column update failed.');
}

/**
 * Delete rows by index.
 * @param {number[]} indices - Row indices to delete
 * @returns {Promise<Object>}
 */
export async function deleteRows(indices) {
  return requestJson('/delete-rows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices }),
  }, 'Row deletion failed.');
}

/**
 * Cast a column to a new backend type.
 * @param {Object} params
 * @param {string} params.name
 * @param {string} params.newType
 * @returns {Promise<Object>}
 */
export async function castColumn({ name, newType }) {
  return requestJson('/cast-column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      new_type: newType,
    }),
  }, 'Column type cast failed.');
}

/**
 * Initialize help system data.
 * @returns {Promise<Object>}
 */
export async function initHelpSystem() {
  return requestJson('/help/init', {
    method: 'GET',
  }, 'Could not load help index from server.');
}

/**
 * Fetch a single help page by name.
 * @param {string} pageName
 * @returns {Promise<Object>}
 */
export async function getHelpPage(pageName) {
  return requestJson(`/help/${encodeURIComponent(pageName)}`, {
    method: 'GET',
  }, `Could not load help page: ${pageName}`);
}

/**
 * Optional generic JSON POST helper for future expansion.
 * Useful if you later want other modules to call arbitrary backend routes.
 */
export async function postJson(endpoint, payload, fallbackMessage = 'POST request failed.') {
  return requestJson(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, fallbackMessage);
}

/**
 * Optional generic GET helper for future expansion.
 */
export async function getJson(endpoint, fallbackMessage = 'GET request failed.') {
  return requestJson(endpoint, {
    method: 'GET',
  }, fallbackMessage);
}

export { BACKEND_URL };

export async function getFilterStatus() {
  return requestJson('/filter/status', { method: 'GET' }, 'Could not load filter status.');
}

export async function excludeValues(column, values) {
  return requestJson('/filter/exclude-values', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ column, values }),
  }, 'Value exclusion failed.');
}

export async function clearAllExclusions() {
  return requestJson('/filter/include-all', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  }, 'Could not clear exclusions.');
}

export async function encodeColumn(payload) {
  return requestJson('/wrangling/encode-column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 'Column encoding failed.');
}

export async function imputeMissingData() {
      return requestJson('/wrangling/impute', {
        method: 'POST',
      }, 'Imputation failed.');
    }

export async function acceptImputation() {
  return requestJson('/wrangling/impute/accept', {
    method: 'POST',
  }, 'Accept imputation failed.');
}

export async function revertImputation() {
  return requestJson('/wrangling/impute/revert', {
    method: 'POST',
  }, 'Revert imputation failed.');
}

export async function recodeColumn({ column, mapping }) {
  return requestJson('/wrangling/recode-column', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ column, mapping }),
  }, 'Column recode failed.');
}