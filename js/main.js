import {
  uploadFile,
  runConfiguredTask,
  getDatasetDownloadUrl,
  downloadReportFile,
  triggerBrowserDownload,
  correctColumns,
  runNumericalQC,
  excludeValues,
  clearAllExclusions,
  encodeColumn,
  recodeColumn,
  imputeMissingData,
  acceptImputation,
  revertImputation,
  setSessionId,
  getSessionId,
  loadExample,
  newBlankDataset,
  getMfubManifest,
  getMfubMarkdown,
  getLogTail,
  getLogLocation
} from './api.js';

import { createParameterModal } from './ui/parameterModal.js';
import { createReportModal } from './ui/reportModal.js';
import { createHelpSystem } from './helpSystem.js';
import { createGridManager } from './gridManager.js';
import { createDatasetSession, getCurrentDatasetSession } from './state/sessionState.js';

// --- SHARED PLOTLY CONFIG ---
// One config for every figure in the app so export behaviour is consistent.
// Clinicians paste these into manuscripts, so we expose vector SVG (default
// download) plus a high-resolution PNG button, and keep the modebar visible.
// Built lazily so Plotly (and Plotly.Icons) is guaranteed loaded at call time.
export function getPlotConfig({ editable = false } = {}) {
  const cfg = {
    responsive: true,
    displaylogo: false,
    // Default download = SVG (vector, journal-ready).
    toImageButtonOptions: { format: 'svg', filename: 'figure', scale: 1 },
    // High-res PNG (3x) button alongside the default SVG download; drop the
    // noisier lasso/box-select buttons that clutter the bar for static figures.
    modeBarButtonsToAdd: [{
      name: 'Download PNG (high-res)',
      icon: (typeof Plotly !== 'undefined' && Plotly.Icons) ? Plotly.Icons.camera : undefined,
      click: (gd) => {
        if (typeof Plotly !== 'undefined') {
          Plotly.downloadImage(gd, { format: 'png', scale: 3, filename: 'figure' });
        }
      },
    }],
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
  };
  if (editable) cfg.editable = true;
  return cfg;
}

// --- GLOBAL STATE ---
let currentHeaders = [];
let columnDataTypes = {};
let exclusionState = {
  row_excluded_mask: [],
  row_exclusion_reason: [],
  filter_summary: { total_rows: 0, active_rows: 0, excluded_rows: 0, rule_count: 0 },
};

// --- DOM ELEMENTS ---
const fileUpload = document.getElementById('file-upload');
const paramModal = document.getElementById('param-modal');
const reportModalEl = document.getElementById('report-modal');
const plotModal = document.getElementById('plot-modal');
const helpPanel = document.getElementById('help-panel');
const globalTooltip = document.getElementById('global-tooltip');
const dataGridContainer = document.getElementById('data-grid-container');
const dataGrid = document.getElementById('data-grid');
const welcomeMessage = document.getElementById('welcome-message');
const dropOverlay = document.getElementById('drop-overlay');
const filenameContainer = document.getElementById('filename-container');
const filenameInput = document.getElementById('current-filename');
const filterSummaryEl = document.getElementById('filter-summary');
const encodeModal = document.getElementById('encode-modal');
const encodeColSelect = document.getElementById('encode-col-select');
const encodeMethodSelect = document.getElementById('encode-method-select');
const encodeOrderContainer = document.getElementById('encode-order-container');
const encodeSortableList = document.getElementById('encode-sortable-list');
const encodeDirectionContainer = document.getElementById('encode-direction-container');
const encodeDirectionSelect = document.getElementById('encode-direction-select');
const realityToggleWrapper = document.getElementById('reality-toggle-wrapper');
const realityToggle = document.getElementById('reality-toggle');
const imputeAcceptBtn = document.getElementById('impute-accept-btn');
const imputeRevertBtn = document.getElementById('impute-revert-btn');
const encodeDropOriginal = document.getElementById('encode-drop-original');

// --- HELPERS ---
function updateStatus(message, isError = false) {
  const statusBar = document.getElementById('status-bar');
  statusBar.textContent = message;
  statusBar.style.color = isError ? 'red' : 'black';
}

function updateFilterSummary(summary = exclusionState.filter_summary) {
  const { total_rows = 0, active_rows = 0, excluded_rows = 0, rule_count = 0 } = summary || {};
  filterSummaryEl.textContent = `Rows: ${active_rows}/${total_rows} active • ${excluded_rows} excluded • ${rule_count} rule${rule_count === 1 ? '' : 's'}`;
}

function applyExclusionState(payload = {}) {
  exclusionState = {
    row_excluded_mask: payload.row_excluded_mask || exclusionState.row_excluded_mask || [],
    row_exclusion_reason: payload.row_exclusion_reason || exclusionState.row_exclusion_reason || [],
    filter_summary: payload.filter_summary || exclusionState.filter_summary || { total_rows: 0, active_rows: 0, excluded_rows: 0, rule_count: 0 },
    filter_rules: payload.filter_rules || exclusionState.filter_rules || [],
  };

  gridManager.setExclusionState(exclusionState);
  updateFilterSummary(exclusionState.filter_summary);
}

function generateColHeaders() {
  return currentHeaders.map(
    h => `<div class="col-header-container" title="${h}">${h}<span class="col-header-dtype">${columnDataTypes[h] || ''}</span></div>`
  );
}

function setColumnDataType(header, dtype) {
  columnDataTypes[header] = dtype;
}

function applyTableState(tableData) {
  currentHeaders = tableData.headers || [];
  columnDataTypes = tableData.dtypes || {};
  applyExclusionState(tableData);
}

function updateTable(tableData) {
  applyTableState(tableData);
  gridManager.loadTableData(tableData);
  updateImputationToolbar(tableData);
}

function updateImputationToolbar(tableData) {
  const hasPending = tableData.has_pending_imputation === true;
  const hasMeta = Array.isArray(tableData.imputation_metadata) && tableData.imputation_metadata.length > 0;

  if (hasPending || hasMeta) {
    realityToggleWrapper.style.display = 'flex';
  } else if (!hasPending) {
    realityToggleWrapper.style.display = 'none';
  }
}

function displayPlot(figObj) {
  const plotDiv = document.getElementById('plot-div');
  plotModal.style.display = 'block';

  requestAnimationFrame(() => {
    Plotly.newPlot(plotDiv, figObj.data, figObj.layout, getPlotConfig({ editable: true }));
  });
}

function showSimpleReport(title, html) {
  document.getElementById('report-modal-title').textContent = title;
  document.getElementById('report-modal-body').innerHTML = html;
  reportModalEl.style.display = 'block';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function showExcludeValuesDialog(columnIndex, uniqueValues) {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  const columnName = currentHeaders[columnIndex];
  const body = document.getElementById('report-modal-body');
  const title = document.getElementById('report-modal-title');
  title.textContent = `Exclude values: ${columnName}`;

  const optionsHtml = uniqueValues.map((item, index) => `
    <label class="filter-option-row">
      <input type="checkbox" class="filter-value-checkbox" value="${escapeHtml(item.value)}" ${index === 0 ? '' : ''}>
      <span>${escapeHtml(item.label)} <span class="text-gray-500">(${item.count})</span></span>
    </label>
  `).join('');

  body.innerHTML = `
    <div class="space-y-4">
      <p class="text-sm text-gray-600">Select category values to exclude. Excluded rows stay visible in the table and are crossed out diagonally.</p>
      <input id="filter-search" type="text" placeholder="Search values..." class="block w-full border border-gray-300 rounded-md p-2 shadow-sm">
      <div class="flex gap-2 text-sm">
        <button id="filter-select-all" class="px-3 py-1 rounded border">Select all</button>
        <button id="filter-clear-selection" class="px-3 py-1 rounded border">Clear</button>
        <button id="filter-clear-rules" class="px-3 py-1 rounded border border-red-300 text-red-700 ml-auto">Clear all exclusions</button>
      </div>
      <div id="filter-options" class="filter-options-box">${optionsHtml || '<p class="text-sm text-gray-500">No values available.</p>'}</div>
      <div class="flex justify-end gap-3 border-t pt-4">
        <button id="filter-cancel" class="px-4 py-2 rounded border">Cancel</button>
        <button id="filter-apply" class="px-4 py-2 rounded bg-blue-600 text-white font-semibold">Exclude selected</button>
      </div>
    </div>
  `;

  reportModalEl.style.display = 'block';

  const searchInput = document.getElementById('filter-search');
  const optionRows = () => Array.from(body.querySelectorAll('.filter-option-row'));

  searchInput.addEventListener('input', () => {
    const needle = searchInput.value.trim().toLowerCase();
    optionRows().forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(needle) ? 'flex' : 'none';
    });
  });

  document.getElementById('filter-select-all').onclick = (e) => {
    e.preventDefault();
    body.querySelectorAll('.filter-value-checkbox').forEach(cb => { cb.checked = true; });
  };

  document.getElementById('filter-clear-selection').onclick = (e) => {
    e.preventDefault();
    body.querySelectorAll('.filter-value-checkbox').forEach(cb => { cb.checked = false; });
  };

  document.getElementById('filter-clear-rules').onclick = async (e) => {
    e.preventDefault();
    try {
      const state = await clearAllExclusions();
      applyExclusionState(state);
      updateStatus('All exclusions cleared.');
      reportModalEl.style.display = 'none';
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  };

  document.getElementById('filter-cancel').onclick = () => {
    reportModalEl.style.display = 'none';
  };

  document.getElementById('filter-apply').onclick = async () => {
    const selectedValues = Array.from(body.querySelectorAll('.filter-value-checkbox:checked')).map(cb => cb.value);

    if (selectedValues.length === 0) {
      alert('Select at least one value to exclude.');
      return;
    }

    try {
      const state = await excludeValues(columnName, selectedValues);
      applyExclusionState(state);
      updateStatus(`Excluded ${selectedValues.length} value set${selectedValues.length === 1 ? '' : 's'} from '${columnName}'.`);
      reportModalEl.style.display = 'none';
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  };
}

function showRecodeValuesDialog(columnIndex, uniqueValues) {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  const columnName = currentHeaders[columnIndex];
  const body = document.getElementById('report-modal-body');
  const title = document.getElementById('report-modal-title');

  title.textContent = `Recode values: ${columnName}`;

  const rowsHtml = uniqueValues.map((item, index) => `
    <tr>
      <td class="border px-2 py-1 text-sm">${escapeHtml(item.label)}</td>
      <td class="border px-2 py-1 text-sm text-right text-gray-500">${item.count}</td>
      <td class="border px-2 py-1">
        <input
          class="recode-new-value w-full border rounded px-2 py-1 text-sm"
          data-old-value="${escapeHtml(item.value)}"
          value="${escapeHtml(item.value === '__BLANK__' ? '' : item.label)}"
        >
      </td>
    </tr>
  `).join('');

  body.innerHTML = `
    <div class="space-y-4">
      <p class="text-sm text-gray-600">
        Assign a new value for each current value. Leave unchanged values as they are.
      </p>

      <div class="max-h-[420px] overflow-auto border rounded">
        <table class="w-full border-collapse">
          <thead class="bg-gray-50 sticky top-0">
            <tr>
              <th class="border px-2 py-1 text-left text-sm">Current value</th>
              <th class="border px-2 py-1 text-right text-sm">Count</th>
              <th class="border px-2 py-1 text-left text-sm">New value</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>

      <div class="flex justify-end gap-3 border-t pt-4">
        <button id="recode-cancel" class="px-4 py-2 rounded border">Cancel</button>
        <button id="recode-apply" class="px-4 py-2 rounded bg-blue-600 text-white font-semibold">Apply recode</button>
      </div>
    </div>
  `;

  reportModalEl.style.display = 'block';

  document.getElementById('recode-cancel').onclick = () => {
    reportModalEl.style.display = 'none';
  };

  document.getElementById('recode-apply').onclick = async () => {
    const mapping = {};

    body.querySelectorAll('.recode-new-value').forEach(input => {
      const oldValue = input.dataset.oldValue;
      const newValue = input.value;

      if (oldValue === '__BLANK__') {
        mapping[oldValue] = newValue === '' ? '__BLANK__' : newValue;
      } else {
        mapping[oldValue] = newValue;
      }
    });

    try {
      updateStatus(`Recoding values in '${columnName}'...`);
      const result = await recodeColumn({ column: columnName, mapping });

      updateTable(result);
      const newIndex = currentHeaders.indexOf(columnName);
      gridManager.highlightColumns([newIndex]);

      updateStatus(`Values recoded in '${columnName}'.`);
      reportModalEl.style.display = 'none';
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  };
}

function resetApplicationState() {
  gridManager.destroy();

  currentHeaders = [];
  columnDataTypes = {};
  exclusionState = {
    row_excluded_mask: [],
    row_exclusion_reason: [],
    filter_summary: { total_rows: 0, active_rows: 0, excluded_rows: 0, rule_count: 0 },
  };

  paramModal.style.display = 'none';
  reportModalEl.style.display = 'none';
  plotModal.style.display = 'none';
  helpPanel.classList.remove('open');

  dataGridContainer.style.display = 'none';
  welcomeMessage.style.display = 'flex';
  filenameContainer.style.display = 'none';
  filenameInput.value = '';

  updateFilterSummary();
  updateStatus('Ready');

  // Hide and reset the Reality Toggle for the new file
  if (realityToggleWrapper) {
      realityToggleWrapper.style.display = 'none';
      realityToggle.checked = true;
  }
}

// --- MODULES ---
const reportModal = createReportModal({
  modalElement: reportModalEl,
  getPlotConfig,
  onDownloadReport: async (tables, reportTitle) => {
    const base = filenameInput.value || 'data';
    const suffix = reportTitle ? '_' + reportTitle.replace(/[^a-zA-Z0-9]+/g, '_').replace(/_+$/, '') : '';
    const filename = base + suffix;
    updateStatus('Preparing report for download...');

    try {
      const blob = await downloadReportFile(`${filename}.xlsx`, tables);
      triggerBrowserDownload(blob, `${filename}.xlsx`);
      updateStatus('Report download complete.');
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  },
});

const parameterModal = createParameterModal({
  modalElement: paramModal,
  onRunTask: async (config, payload) => {
    updateStatus(`Running ${config.title} on ${exclusionState.filter_summary.active_rows} active rows...`);

    try {
      // Correlation: convert empty column arrays to null (= auto-select)
      if (config.endpoint === 'analysis/correlation') {
        if (Array.isArray(payload.columns) && payload.columns.length === 0) {
          payload.columns = null;
        }
        if (Array.isArray(payload.covariate_columns) && payload.covariate_columns.length === 0) {
          payload.covariate_columns = null;
        }
      }

      // CFA: build model_spec from factorN_name / factorN_items fields
      if (config.endpoint === 'analysis/tests/cfa') {
        const modelSpec = {};
        for (let i = 1; i <= 3; i++) {
          const name = payload[`factor${i}_name`] || `Factor${i}`;
          const items = payload[`factor${i}_items`];
          if (Array.isArray(items) && items.length >= 2) {
            modelSpec[name] = items;
          }
          delete payload[`factor${i}_name`];
          delete payload[`factor${i}_items`];
        }
        payload.model_spec = modelSpec;
      }

      // Consolidated modals (e.g. Quick plot) carry neutral fields (value,
      // group, plot_type) and remap them to per-plot backend keys here, so the
      // server contract for each individual plot type stays unchanged.
      if (typeof config.buildPlotParams === 'function') {
        payload = config.buildPlotParams(payload);
      }

      const results = await runConfiguredTask(config, payload);

      if (results && results.python_code) {
        updateCodePanel(results.python_code);
      }

      if (config.endpoint.startsWith('graphic')) {
        displayPlot(results);
      } else if (config.endpoint === 'analysis/correlation') {
        // Transform correlation matrices into the tabbed report format
        const tables = {};
        if (results.summary) tables['Summary'] = results.summary;
        if (results.matrix) tables['Coefficients'] = results.matrix;
        if (results.p_matrix) tables['P-Values'] = results.p_matrix;
        if (results.n_matrix) tables['Sample Sizes'] = results.n_matrix;
        if (results.method_map) tables['Method Map'] = results.method_map;

        const title = `Correlation — ${results.method_name || 'Results'}`;
        reportModal.displayReport(title, { tables, note: results.note, plotly_figures: results.plotly_figures });
      } else {
        reportModal.displayReport(config.title, results);
      }

      refreshLogPanel();
      updateStatus('Analysis complete.');
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  },
  onError: (message) => alert(message),
});

const helpSystem = createHelpSystem({
  helpPanel,
  updateStatus,
});

const gridManager = createGridManager({
  containerElement: dataGridContainer,
  gridElement: dataGrid,
  welcomeElement: welcomeMessage,
  getHeaders: () => currentHeaders,
  getColumnDataTypes: () => columnDataTypes,
  setColumnDataType,
  generateColHeaders,
  updateStatus,
  onTableDataUpdate: (tableData) => {
    updateTable(tableData);
  },
  onExclusionStateUpdate: (payload) => {
    applyExclusionState(payload);
  },
  onRequestRecodeValues: (columnIndex, uniqueValues) => {
    showRecodeValuesDialog(columnIndex, uniqueValues);
  },
  onRequestExcludeValues: (columnIndex, uniqueValues) => {
    showExcludeValuesDialog(columnIndex, uniqueValues);
  },
  onRequestClearExclusions: async () => {
    try {
      const state = await clearAllExclusions();
      applyExclusionState(state);
      updateStatus('All exclusions cleared.');
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  },
});

// --- INITIALIZATION ---
window.addEventListener('load', async () => {
  await helpSystem.load();
  updateFilterSummary();
});

// --- FILE & DATA LOGIC ---
function handleFileSelect(file) {
  if (!file) return;

  if (gridManager.getHotInstance()) {
    const confirmReset = window.confirm(
      'You already have a file loaded. Loading a new file will discard your current work. Are you sure you want to continue?'
    );

    if (!confirmReset) {
      fileUpload.value = '';
      return;
    }

    resetApplicationState();
  }

  filenameInput.value = file.name.replace(/\.[^/.]+$/, '');
  filenameContainer.style.display = 'flex';

  const formData = new FormData();
  formData.append('file', file);

  doUpload(formData, file.name);

  fileUpload.value = '';
}

async function doUpload(formData, originalFilename = null) {
  updateStatus('Uploading file...');
  try {
    const result = await uploadFile(formData);
    gridManager.setImputationState([]);
    gridManager.toggleImputedData(true);
    updateTable(result);
    createDatasetSession({
      headers: result.headers || [],
      filename: originalFilename,
    });

    console.log('Current dataset session:', getCurrentDatasetSession());
    updateStatus('Successfully loaded file.');
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
}

function downloadFile(fileType) {
  if (!gridManager.getHotInstance()) {
    alert('No data to download.');
    return;
  }

  const filename = filenameInput.value || 'data';
  window.location.href = getDatasetDownloadUrl(fileType, filename);
}

function showParameterModal(taskType) {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  // Resolve a column's unique values (header name → grid column index), so the
  // modal can populate dependent dropdowns (e.g. control-group selection).
  const getColumnValues = (columnName) => {
    const idx = currentHeaders.indexOf(columnName);
    if (idx < 0) return [];
    return gridManager.getUniqueColumnValues(idx).map(v => ({
      value: String(v.value),
      label: v.label,
    }));
  };

  parameterModal.show(taskType, currentHeaders, getColumnValues);
}

async function runCorrectColumns() {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  updateStatus('Running column correction...');
  try {
    const result = await correctColumns();
    updateTable(result);
    updateStatus('Column correction complete.');

    if (result.log) {
      alert(`Columns corrected. Log: ${JSON.stringify(result.log)}`);
    }
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
}

async function runNumericalQCReport() {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  updateStatus('Running Numerical QC...');
  try {
    const report = await runNumericalQC();
    reportModal.displayNumericalQCReport(report, currentHeaders, gridManager.getHotInstance());
    updateStatus('Numerical QC complete.');
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
}

function bindMenuClick(id, handler) {
  const el = document.getElementById(id);
  if (!el) return;  // menu item not present in this build — skip silently
  el.addEventListener('click', e => {
    e.preventDefault();
    dismissHoverMenu(e.currentTarget);
    handler();
  });
}

// Pure CSS hover menus stay open after a click because their visibility is tied
// to the cursor, not to the click — so the panel hangs over the modal that just
// opened until the mouse moves away. Force the containing panel hidden, then
// release it once the cursor leaves the menu root (so normal hover resumes).
function dismissHoverMenu(itemEl) {
  if (!itemEl) return;
  const root = itemEl.closest('.dropdown');           // hover root (both menu styles)
  if (!root) return;
  // The visible panel is either a .dropdown-content (simple menus) or the
  // absolutely-positioned group-hover panel (mega menus).
  const panel = itemEl.closest('.dropdown-content')
    || (root.querySelector(':scope > div.absolute') /* mega panel wrapper */)
    || itemEl.closest('div.absolute');
  if (!panel) return;
  panel.classList.add('menu-force-hidden');
  const release = () => {
    panel.classList.remove('menu-force-hidden');
    root.removeEventListener('mouseleave', release);
  };
  root.addEventListener('mouseleave', release);
}

// --- EVENT LISTENERS ---
fileUpload.addEventListener('change', e => handleFileSelect(e.target.files[0]));
bindMenuClick('download-csv', () => downloadFile('csv'));
bindMenuClick('download-xlsx', () => downloadFile('xlsx'));

// --- New blank dataset: type values directly into an empty grid ---
bindMenuClick('new-blank-dataset', async () => {
  if (gridManager.getHotInstance()) {
    const proceed = confirm('This will replace the current data with a new blank dataset. Continue?');
    if (!proceed) return;
  }
  const colsRaw = prompt('How many columns?', '3');
  if (colsRaw === null) return;
  const rowsRaw = prompt('How many rows?', '10');
  if (rowsRaw === null) return;
  const cols = Math.max(1, Math.min(parseInt(colsRaw, 10) || 3, 100));
  const rows = Math.max(1, Math.min(parseInt(rowsRaw, 10) || 10, 10000));
  const namesRaw = prompt(
    `Optional: column names, comma-separated (leave blank for var1…var${cols}).`,
    ''
  );
  const column_names = (namesRaw || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);

  updateStatus('Creating blank dataset...');
  try {
    const result = await newBlankDataset({ rows, cols, column_names });
    gridManager.setImputationState([]);
    gridManager.toggleImputedData(true);
    updateTable(result);
    createDatasetSession({ headers: result.headers || [], filename: 'untitled' });
    updateStatus('Blank dataset created — click a cell and start typing.');
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
});

// --- Session ID (student name / number), stamped on every logged action ---
function updateSessionBadge() {
  const badge = document.getElementById('session-badge');
  if (!badge) return;
  const id = getSessionId();
  badge.textContent = id ? `Session: ${id}` : 'Session: (not set)';
}
bindMenuClick('set-session-id', () => {
  const current = getSessionId();
  const entered = prompt(
    'Enter your Session ID (e.g. your name or student number).\n' +
    'It will be recorded with each analysis in the local activity log.',
    current
  );
  if (entered !== null) {
    setSessionId(entered);
    updateSessionBadge();
    updateStatus(entered.trim() ? `Session ID set to "${entered.trim()}".` : 'Session ID cleared.');
  }
});
updateSessionBadge();

// --- Built-in example datasets ---
async function doLoadExample(datasetId) {
  updateStatus('Loading example dataset...');
  try {
    const result = await loadExample(datasetId);
    gridManager.setImputationState([]);
    gridManager.toggleImputedData(true);
    updateTable(result);
    createDatasetSession({ headers: result.headers || [], filename: datasetId });
    updateStatus('Example dataset loaded.');
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
}
document.querySelectorAll('#examples-submenu [data-example]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    dismissHoverMenu(e.currentTarget);
    doLoadExample(el.getAttribute('data-example'));
  });
});

// --- Show where the local activity log lives ---
bindMenuClick('show-log-location', async () => {
  try {
    const res = await getLogLocation();
    showSimpleReport(
      'Activity Log',
      `<p>Your activity log is saved on this computer at:</p>` +
      `<p style="font-family:monospace;background:#f3f4f6;padding:8px;border-radius:6px;word-break:break-all;">${res.folder}</p>` +
      `<p>It records each action (test, columns, and result) with your Session ID and a timestamp, in both <code>datagrad_activity.log</code> and <code>datagrad_activity.csv</code>.</p>`
    );
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
});

bindMenuClick('desc-qc', runNumericalQCReport);
bindMenuClick('desc-stats', () => showParameterModal('describe'));
bindMenuClick('desc-diagnostic', () => showParameterModal('diagnostic_test'));

bindMenuClick('analysis-correlation', () => showParameterModal('correlation'));
bindMenuClick('analysis-linear-regression', () => showParameterModal('linear_regression'));
bindMenuClick('analysis-ttest-ind', () => showParameterModal('ttest_ind'));
bindMenuClick('analysis-ttest-one-sample', () => showParameterModal('ttest_one_sample'));
bindMenuClick('analysis-sign-test', () => showParameterModal('sign_test'));
bindMenuClick('analysis-ttest-paired', () => showParameterModal('ttest_paired'));
bindMenuClick('analysis-mannwhitney', () => showParameterModal('mannwhitney'));
bindMenuClick('analysis-wilcoxon', () => showParameterModal('wilcoxon'));
bindMenuClick('analysis-anova', () => showParameterModal('anova'));
bindMenuClick('analysis-kruskal', () => showParameterModal('kruskal'));
bindMenuClick('analysis-chi-square', () => showParameterModal('chi_square'));
bindMenuClick('analysis-chi-square-gof', () => showParameterModal('chi_square_gof'));
bindMenuClick('analysis-fisher', () => showParameterModal('fisher_exact'));
bindMenuClick('analysis-mcnemar', () => showParameterModal('mcnemar'));
bindMenuClick('help-search', () => helpSystem.openSearch());
bindMenuClick('help-about', () => {
  showSimpleReport(
    'About',
    '<p><strong>Datagrad MFUB Desktop</strong></p><p>Core statistical tests: correlation, t-tests and nonparametric counterparts, ANOVA, Kruskal-Wallis, chi-square (independence and goodness-of-fit), Fisher exact, McNemar, linear regression, and diagnostic test evaluation.</p><p>Medicinski fakultet Univerziteta u Beogradu — Katedra za medicinsku statistiku i informatiku.</p>'
  );
});

// --- MFUB tab: course materials loaded from mfub/manifest.json ---
async function populateMfubMenu() {
  const menu = document.getElementById('mfub-menu');
  if (!menu) return;
  try {
    const manifest = await getMfubManifest();
    const items = Array.isArray(manifest.items) ? manifest.items : [];
    menu.innerHTML = '';

    if (manifest.intro) {
      const introLink = document.createElement('a');
      introLink.href = '#';
      introLink.className = 'menu-item block';
      introLink.textContent = manifest.title || 'About these materials';
      introLink.addEventListener('click', e => {
        e.preventDefault();
        dismissHoverMenu(e.currentTarget);
        showSimpleReport(manifest.title || 'MFUB', `<p>${manifest.intro}</p>`);
      });
      menu.appendChild(introLink);
      const hr = document.createElement('div');
      hr.className = 'border-t my-1';
      menu.appendChild(hr);
    }

    if (items.length === 0) {
      const empty = document.createElement('a');
      empty.className = 'menu-item block text-gray-400';
      empty.textContent = '(no materials added yet)';
      menu.appendChild(empty);
      return;
    }

    items.forEach(item => {
      const link = document.createElement('a');
      link.href = '#';
      link.className = 'menu-item block';
      link.textContent = item.label || item.file || item.url || 'Item';
      link.addEventListener('click', async e => {
        e.preventDefault();
        dismissHoverMenu(e.currentTarget);
        try {
          if (item.type === 'markdown' && item.file) {
            const res = await getMfubMarkdown(item.file);
            showSimpleReport(item.label || 'Material', res.html || '');
          } else if (item.type === 'link' && item.url) {
            window.open(item.url, '_blank');
          } else if (item.type === 'file' && item.file) {
            window.open(`/mfub/file/${encodeURIComponent(item.file)}`, '_blank');
          } else {
            updateStatus('This material has no valid file or link.', true);
          }
        } catch (error) {
          updateStatus(`Error: ${error.message}`, true);
        }
      });
      menu.appendChild(link);
    });
  } catch (error) {
    menu.innerHTML = '<a href="#" class="menu-item block text-gray-400">Could not load materials</a>';
  }
}
populateMfubMenu();

// --- Collapsible bottom panels: activity log + Python code ---
function updateCodePanel(code) {
  const el = document.getElementById('code-content');
  if (el) el.textContent = code;
}

async function refreshLogPanel() {
  const panel = document.getElementById('log-panel');
  const el = document.getElementById('log-content');
  if (!panel || !el) return;
  // Only fetch when the panel is open, to avoid needless work.
  if (!panel.open) return;
  try {
    const res = await getLogTail(300);
    const lines = res.lines || [];
    el.textContent = lines.length ? lines.join('\n') : '(no activity recorded yet)';
    el.scrollTop = el.scrollHeight;
  } catch (error) {
    el.textContent = `Could not load log: ${error.message}`;
  }
}

(function wireBottomPanels() {
  const logPanel = document.getElementById('log-panel');
  const logRefresh = document.getElementById('log-refresh');
  const codeCopy = document.getElementById('code-copy');

  if (logPanel) logPanel.addEventListener('toggle', () => { if (logPanel.open) refreshLogPanel(); });
  if (logRefresh) logRefresh.addEventListener('click', refreshLogPanel);
  if (codeCopy) {
    codeCopy.addEventListener('click', () => {
      const code = document.getElementById('code-content')?.textContent || '';
      if (navigator.clipboard && code) {
        navigator.clipboard.writeText(code)
          .then(() => updateStatus('Python code copied to clipboard.'))
          .catch(() => updateStatus('Could not copy to clipboard.', true));
      }
    });
  }
})();
bindMenuClick('wrangling-impute', async () => {
  if (!gridManager.getHotInstance()) {
    alert('Please upload data first.');
    return;
  }

  // Warn if there's already a pending imputation
  const toggleVisible = realityToggleWrapper.style.display !== 'none';
  if (toggleVisible) {
    const proceed = confirm(
      'You have pending imputed values.\n\n' +
      'Running imputation again will first accept the current imputed values as real data, ' +
      'then impute any remaining missing values on top of them.\n\n' +
      'Continue?'
    );
    if (!proceed) return;
  }

  updateStatus('Running MICE imputation... (This may take a moment)');
  try {
    const result = await imputeMissingData();

    // Reset toggle to "show" for the new imputation
    realityToggle.checked = true;
    gridManager.toggleImputedData(true, true);

    updateTable(result);
    if (!result.imputation_metadata || result.imputation_metadata.length === 0) {
      updateStatus('No missing values found to impute.');
      return;
    }

    let msg = `Imputed ${result.imputation_metadata.length} cells.`;
    if (result.had_previous_imputation) {
      msg += ' Previous imputed values were kept as permanent.';
    }
    if (result.quarantined_cols && result.quarantined_cols.length > 0) {
        msg += ` Quarantined cols (>50% missing): ${result.quarantined_cols.join(', ')}`;
        alert(`Some columns were too sparse to safely impute and were left blank:\n${result.quarantined_cols.join(', ')}`);
    }
    updateStatus(msg);
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
});

imputeAcceptBtn.addEventListener('click', async () => {
  if (!confirm('Accept all imputed values as permanent data?\n\nThis cannot be undone.')) return;

  try {
    updateStatus('Accepting imputed values...');
    const result = await acceptImputation();

    realityToggle.checked = true;
    gridManager.toggleImputedData(true, true);
    gridManager.setImputationState([]);
    updateTable(result);

    updateStatus(`${result.accepted_count} imputed cell(s) permanently accepted.`);
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
});

imputeRevertBtn.addEventListener('click', async () => {
  if (!confirm('Revert all imputed values and restore original data?\n\nAll imputed cells will become empty again.')) return;

  try {
    updateStatus('Reverting imputation...');
    const result = await revertImputation();

    realityToggle.checked = true;
    gridManager.toggleImputedData(true, true);
    gridManager.setImputationState([]);
    updateTable(result);

    updateStatus(`${result.reverted_count} imputed cell(s) reverted to original.`);
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
});

realityToggle.addEventListener('change', (e) => {
    gridManager.toggleImputedData(e.target.checked);
    updateStatus(e.target.checked ? 'Showing imputed data.' : 'Showing original data only.');
});

plotModal.querySelector('.close-button').onclick = () => {
  plotModal.style.display = 'none';
  Plotly.purge('plot-div');
};

// --- DRAG & DROP ---
window.addEventListener('dragover', e => {
  // ONLY show the overlay if the user is dragging a file from their OS
  if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
    e.preventDefault();
    dropOverlay.style.display = 'flex';
  }
});

window.addEventListener('dragleave', e => {
  if (e.relatedTarget === null) dropOverlay.style.display = 'none';
});

window.addEventListener('drop', e => {
  e.preventDefault();
  dropOverlay.style.display = 'none';
  if (e.dataTransfer && e.dataTransfer.files.length > 0) {
    handleFileSelect(e.dataTransfer.files[0]);
  }
});

// --- GLOBAL TOOLTIP LISTENERS ---
document.addEventListener('mouseover', e => {
  if (e.target.classList.contains('tooltip')) {
    const tooltipText = e.target.getAttribute('data-tooltip');
    globalTooltip.textContent = tooltipText;

    const rect = e.target.getBoundingClientRect();
    let top = rect.top - globalTooltip.offsetHeight - 10;
    let left = rect.left + rect.width / 2 - globalTooltip.offsetWidth / 2;

    if (top < 0) top = rect.bottom + 10;
    if (left < 0) left = 5;
    if (left + globalTooltip.offsetWidth > window.innerWidth) {
      left = window.innerWidth - globalTooltip.offsetWidth - 5;
    }

    globalTooltip.style.top = `${top}px`;
    globalTooltip.style.left = `${left}px`;
    globalTooltip.style.opacity = '1';
  }
});

document.addEventListener('mouseout', e => {
  if (e.target.classList.contains('tooltip')) {
    globalTooltip.style.opacity = '0';
  }
});

// Close button logic
document.getElementById('encode-modal-close').onclick = () => encodeModal.style.display = 'none';

function getSelectedEncodeColumns() {
  return Array.from(encodeColSelect.selectedOptions).map(opt => opt.value);
}

// Menu click hook
bindMenuClick('wrangling-encode-cols', () => {
    if (!gridManager.getHotInstance()) {
        alert('Please upload data first.');
        return;
    }
    
    // Populate column select
    encodeColSelect.innerHTML = currentHeaders
      .map(h => `<option value="${escapeHtml(h)}">${escapeHtml(h)}</option>`)
      .join('');

    encodeMethodSelect.value = 'one-hot';
    encodeDropOriginal.checked = false;
    encodeOrderContainer.style.display = 'none';
    encodeDirectionContainer.style.display = 'none';
    encodeModal.style.display = 'block';
});

function updateEncodeOrderedControls() {
  const method = encodeMethodSelect.value;
  const selectedColumns = getSelectedEncodeColumns();

  const needsOrder = method === 'ordinal' || method === 'cumulative';

  if (needsOrder && selectedColumns.length === 1) {
    populateSortableList(selectedColumns[0]);
    encodeOrderContainer.style.display = 'block';
  } else {
    encodeOrderContainer.style.display = 'none';
    encodeSortableList.innerHTML = '';
  }

  encodeDirectionContainer.style.display = method === 'cumulative' ? 'block' : 'none';
}

// Update the UI when the method changes
encodeMethodSelect.addEventListener('change', updateEncodeOrderedControls);

// Update the list if they change the column while an ordered method is selected
encodeColSelect.addEventListener('change', updateEncodeOrderedControls);
encodeSortableList.addEventListener('dragover', e => {
    e.preventDefault();
    const draggable = document.querySelector('.dragging');
    if (!draggable) return;

    const afterElement = getDragAfterElement(encodeSortableList, e.clientY);
    if (afterElement == null) {
        encodeSortableList.appendChild(draggable);
    } else {
        encodeSortableList.insertBefore(draggable, afterElement);
    }
});

// Build the drag-and-drop Smart Menu
function populateSortableList(colName) {
    const colIndex = currentHeaders.indexOf(colName);
    if (colIndex === -1) return;
    
    const hot = gridManager.getHotInstance();
    const uniqueValues = [...new Set(hot.getSourceDataArray().map(row => row[colIndex]))]
        .filter(v => v !== null && v !== undefined && v !== '');

    encodeSortableList.innerHTML = uniqueValues.map(val => `
        <li class="sortable-item" draggable="true" data-value="${escapeHtml(String(val))}">
            <span class="drag-handle">☰</span> ${escapeHtml(String(val))}
        </li>
    `).join('');

    // Attach Drag and Drop Events
    const items = encodeSortableList.querySelectorAll('.sortable-item');
    items.forEach(item => {
        item.addEventListener('dragstart', () => item.classList.add('dragging'));
        item.addEventListener('dragend', () => item.classList.remove('dragging'));
    });
}

// Math to figure out where to drop the element
function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.sortable-item:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Run button logic
document.getElementById('encode-run-btn').onclick = async () => {
  const columns = getSelectedEncodeColumns();
  const method = encodeMethodSelect.value;
  const direction = encodeDirectionSelect.value;
  const dropOriginal = encodeDropOriginal.checked;

  if (!columns.length) {
    alert('Please select at least one column to encode.');
    return;
  }

  if ((method === 'ordinal' || method === 'cumulative') && columns.length !== 1) {
    alert('Ordinal and cumulative encoding currently require exactly one selected column.');
    return;
  }

  let order = [];

  if (method === 'ordinal' || method === 'cumulative') {
    const items = encodeSortableList.querySelectorAll('.sortable-item');
    order = Array.from(items).map(item => item.getAttribute('data-value'));
  }

  try {
    updateStatus(`Encoding ${columns.length} column(s)...`);
    encodeModal.style.display = 'none';

    const oldHeaders = [...currentHeaders];
    
    const result = await encodeColumn({
      columns,
      method,
      order,
      direction,
      drop_original: dropOriginal,
    });

    updateTable(result);

    if (Array.isArray(result.created_columns)) {
      const indices = result.created_columns
        .map(name => result.headers.indexOf(name))
        .filter(i => i >= 0);

      gridManager.highlightColumns(indices);
    } else {
      const newEncodedIndices = result.headers
        .map((h, i) => oldHeaders.includes(h) ? null : i)
        .filter(i => i !== null);

      gridManager.highlightColumns(newEncodedIndices);
    }

    updateStatus(`Successfully encoded ${columns.length} column(s) using ${method} mapping.`);
  } catch (error) {
    updateStatus(`Error: ${error.message}`, true);
  }
};