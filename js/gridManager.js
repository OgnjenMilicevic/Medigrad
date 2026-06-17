/**
 * gridManager.js — spreadsheet grid backed by Tabulator (MIT-licensed).
 *
 * Public API is unchanged from the previous Handsontable implementation, so
 * main.js requires no changes:
 *   initialize, destroy, loadTableData, getHotInstance, getUniqueColumnValues,
 *   updateGridSettings, handleColumnChange, setExclusionState,
 *   setImputationState, toggleImputedData, highlightColumns
 *
 * Data model note: the backend speaks array-of-arrays (rows of cells, indexed
 * by column position). Tabulator works with array-of-objects, so internally we
 * map each column position to a stable field key "c0", "c1", … and convert at
 * the boundaries.
 */

import {
  updateCell,
  updateColumn,
  deleteRows,
  castColumn,
} from './api.js';

export function createGridManager({
  containerElement,
  gridElement,
  welcomeElement,
  getHeaders,
  getColumnDataTypes,
  setColumnDataType,
  generateColHeaders,
  updateStatus,
  onTableDataUpdate,
  onExclusionStateUpdate,
  onRequestExcludeValues,
  onRequestClearExclusions,
  onRequestRecodeValues,
}) {
  let table = null;             // Tabulator instance
  let ready = false;
  let resizeObserver = null;
  let rowExcludedMask = [];
  let rowExclusionReasons = [];
  let imputationMetaMap = {};
  let showImputedData = true;
  let highlightedColumns = new Set();
  let lastSelectedCol = null;

  const fieldFor = (i) => `c${i}`;

  // ---- conversions between backend rows (arrays) and Tabulator rows (objects)

  function rowsToObjects(dataArray) {
    return (dataArray || []).map((row, rIdx) => {
      const obj = { __row: rIdx };
      row.forEach((val, cIdx) => { obj[fieldFor(cIdx)] = val; });
      return obj;
    });
  }

  function objectsToRows() {
    if (!table) return [];
    const headers = getHeaders();
    const data = table.getData();
    return data.map(obj => headers.map((_, cIdx) => {
      const v = obj[fieldFor(cIdx)];
      return v === undefined ? null : v;
    }));
  }

  // ---- cell formatting (numeric rounding) + status styling -----------------

  function formatNumeric(value) {
    if (value === null || value === undefined || value === '') return '';
    const num = Number(value);
    if (Number.isNaN(num)) return String(value);
    if (num === 0) return '0';
    if (Math.abs(num) < 1) return num.toPrecision(2);
    return (Math.round(num * 10) / 10).toLocaleString();
  }

  function isNumericColumn(colIdx) {
    const headers = getHeaders();
    const types = getColumnDataTypes();
    const dt = types[headers[colIdx]];
    return dt && (dt.includes('int') || dt.includes('float'));
  }

  // Tabulator formatter: applies numeric rounding, imputation markers, and
  // exclusion / highlight styling to each cell element.
  function cellFormatter(cell) {
    const colIdx = colIndexOfField(cell.getField());
    const rowIdx = cell.getRow().getData().__row;
    const raw = cell.getValue();

    const el = cell.getElement();
    el.classList.remove('excluded-row-cell', 'highlighted-column-cell',
                        'cell-imputed-high', 'cell-imputed-low');
    el.removeAttribute('title');

    let display = isNumericColumn(colIdx) ? formatNumeric(raw)
                                          : (raw == null ? '' : String(raw));

    // Imputation markers / hiding
    const meta = imputationMetaMap[`${rowIdx},${colIdx}`];
    let hidden = false;
    if (meta) {
      if (!showImputedData) {
        display = '';
        hidden = true;
      } else {
        el.classList.add(meta.status === 'high' ? 'cell-imputed-high' : 'cell-imputed-low');
        const icon = meta.status === 'high' ? '🪄' : '⚠️';
        display = `${icon} ${display}`;
      }
    }

    if (!hidden && rowExcludedMask[rowIdx]) {
      el.classList.add('excluded-row-cell');
      const reason = rowExclusionReasons[rowIdx];
      if (reason) el.title = `Excluded: ${reason}`;
    }

    if (highlightedColumns.has(colIdx)) {
      el.classList.add('highlighted-column-cell');
    }

    return display;
  }

  function colIndexOfField(field) {
    return parseInt(String(field).replace(/^c/, ''), 10);
  }

  // ---- column definitions ---------------------------------------------------

  function buildColumns() {
    const headers = getHeaders();
    return headers.map((header, idx) => ({
      title: header,
      field: fieldFor(idx),
      headerSort: false,
      editor: 'input',
      formatter: cellFormatter,
      headerContextMenu: headerMenu(idx),
      contextMenu: cellMenu(idx),
      cellEdited: (cell) => onCellEdited(cell),
      headerClick: (e, column) => { lastSelectedCol = idx; },
      cellClick: (e, cell) => { lastSelectedCol = idx; },
    }));
  }

  // ---- public: highlight / exclusion / imputation --------------------------

  function highlightColumns(colIndices = []) {
    highlightedColumns = new Set(
      colIndices.filter(i => Number.isInteger(i) && i >= 0)
    );
    redraw();
  }

  function setExclusionState({ row_excluded_mask = [], row_exclusion_reason = [] } = {}) {
    rowExcludedMask = Array.isArray(row_excluded_mask) ? row_excluded_mask : [];
    rowExclusionReasons = Array.isArray(row_exclusion_reason) ? row_exclusion_reason : [];
    redraw();
  }

  function setImputationState(metadataList, skipRender = false) {
    imputationMetaMap = {};
    (metadataList || []).forEach(meta => {
      imputationMetaMap[`${meta.row},${meta.col}`] = meta;
    });
    if (!skipRender) redraw();
  }

  function toggleImputedData(show, skipRender = false) {
    showImputedData = show;
    if (!skipRender) redraw();
  }

  function redraw() {
    if (table && ready) {
      try { table.redraw(true); } catch (_) {}
    }
  }

  // ---- lifecycle ------------------------------------------------------------

  function getHotInstance() {
    // Kept for API compatibility; returns the Tabulator instance (or null).
    return table;
  }

  function destroy() {
    if (table) {
      try { table.destroy(); } catch (_) {}
      table = null;
    }
    ready = false;
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    rowExcludedMask = [];
    rowExclusionReasons = [];
    imputationMetaMap = {};
    showImputedData = true;
  }

  function updateGridSettings() {
    if (!table || !ready) return;
    table.setColumns(buildColumns());
    redraw();
  }

  function loadTableData(tableData) {
    setExclusionState(tableData);

    if ('imputation_metadata' in tableData) {
      imputationMetaMap = {};
      setImputationState(tableData.imputation_metadata || [], true);
    }

    if (!table) {
      initialize(tableData.data);
      return;
    }
    ready = false;
    table.setColumns(buildColumns());
    table.replaceData(rowsToObjects(tableData.data)).then(() => {
      ready = true;
      redraw();
    });
  }

  function initialize(data) {
    welcomeElement.style.display = 'none';
    containerElement.style.display = 'block';

    if (table) { try { table.destroy(); } catch (_) {} table = null; }
    if (resizeObserver) resizeObserver.disconnect();

    table = new Tabulator(gridElement, {
      data: rowsToObjects(data),
      columns: buildColumns(),
      layout: 'fitDataStretch',
      height: containerElement.offsetHeight || '100%',
      reactiveData: false,
      index: '__row',
      movableColumns: false,
      rowHeader: { formatter: 'rownum', headerSort: false, resizable: false, frozen: true, width: 50, hozAlign: 'center' },
    });

    table.on('tableBuilt', () => {
      ready = true;
      redraw();
    });

    resizeObserver = new ResizeObserver(() => {
      if (table && ready) {
        try { table.setHeight(containerElement.offsetHeight); } catch (_) {}
      }
    });
    resizeObserver.observe(containerElement);
  }

  // ---- cell edit -> backend save (with type-change confirm + revert) -------

  async function onCellEdited(cell) {
    const colIdx = colIndexOfField(cell.getField());
    const rowIdx = cell.getRow().getData().__row;
    const newValue = cell.getValue();
    const oldValue = cell.getOldValue();
    if (oldValue === newValue) return;

    async function sendUpdate(force = false) {
      updateStatus(`Saving cell (${rowIdx}, ${colIdx})...`);
      try {
        const resp = await updateCell({ row: rowIdx, col: colIdx, newValue, force });

        if (resp.status === 'confirm_type_change') {
          if (window.confirm(resp.message)) {
            await sendUpdate(true);
          } else {
            cell.setValue(oldValue, true);   // mutate=true, but no re-fire of edit-save
            updateStatus('Edit cancelled.');
          }
        } else if (resp.status === 'success') {
          const headers = getHeaders();
          const colName = headers[colIdx];
          if (resp.new_dtype) {
            const oldDtype = getColumnDataTypes()[colName];
            setColumnDataType(colName, resp.new_dtype);
            if (resp.new_dtype !== oldDtype) updateGridSettings();
          }
          if (typeof onExclusionStateUpdate === 'function') onExclusionStateUpdate(resp);
          updateStatus(`Edit at Row ${rowIdx + 1}, ${colName} [${colIdx + 1}] saved.`);
          redraw();
        } else if (resp.error) {
          cell.setValue(oldValue, true);
          updateStatus(`Error: ${resp.error}`, true);
          alert(`Error updating cell: ${resp.error}`);
        }
      } catch (err) {
        console.error('Network error:', err);
        cell.setValue(oldValue, true);
        updateStatus('Network error while saving.', true);
      }
    }
    sendUpdate(false);
  }

  // ---- context menus (header + cell) ---------------------------------------

  function headerMenu(colIdx) {
    return [
      {
        label: 'Rename Column',
        action: () => {
          const headers = getHeaders();
          const oldName = headers[colIdx];
          const raw = prompt(`Rename column "${oldName}" to:`, oldName);
          const newName = raw ? raw.trim() : '';
          if (newName && newName !== oldName) handleColumnChange('rename', { oldName, newName });
        },
      },
      {
        label: 'Insert column left',
        action: () => handleColumnChange('add', { index: colIdx }),
      },
      {
        label: 'Insert column right',
        action: () => handleColumnChange('add', { index: colIdx + 1 }),
      },
      {
        label: 'Remove this column',
        action: () => {
          const headers = getHeaders();
          const name = headers[colIdx];
          if (confirm(`Are you sure you want to remove the column "${name}"?`)) {
            handleColumnChange('remove_multiple', { names: [name] });
          }
        },
      },
      { separator: true },
      {
        label: 'Change type → Text',
        action: () => castColumnType(colIdx, 'text'),
      },
      {
        label: 'Change type → Numeric (float)',
        action: () => castColumnType(colIdx, 'numeric'),
      },
      {
        label: 'Change type → Integer',
        action: () => castColumnType(colIdx, 'integer'),
      },
      { separator: true },
      {
        label: 'Exclude category values…',
        action: () => {
          if (typeof onRequestExcludeValues === 'function') {
            onRequestExcludeValues(colIdx, getUniqueColumnValues(colIdx));
          }
        },
      },
      {
        label: 'Recode values…',
        action: () => {
          if (typeof onRequestRecodeValues === 'function') {
            onRequestRecodeValues(colIdx, getUniqueColumnValues(colIdx));
          }
        },
      },
      {
        label: 'Clear all exclusions',
        action: () => {
          if (typeof onRequestClearExclusions === 'function') onRequestClearExclusions();
        },
      },
    ];
  }

  function cellMenu(colIdx) {
    return [
      {
        label: 'Remove this row',
        action: (e, cell) => {
          const rowIdx = cell.getRow().getData().__row;
          handleRowDelete([rowIdx]);
        },
      },
      {
        label: 'Exclude category values…',
        action: () => {
          if (typeof onRequestExcludeValues === 'function') {
            onRequestExcludeValues(colIdx, getUniqueColumnValues(colIdx));
          }
        },
      },
      {
        label: 'Recode values…',
        action: () => {
          if (typeof onRequestRecodeValues === 'function') {
            onRequestRecodeValues(colIdx, getUniqueColumnValues(colIdx));
          }
        },
      },
    ];
  }

  // ---- unique values (for exclude / recode dialogs) ------------------------

  function normalizeRecodeKey(value) {
    if (value === null || value === undefined || value === '') return '__BLANK__';
    const text = String(value).trim();
    if (text === '') return '__BLANK__';
    const num = Number(text);
    if (Number.isFinite(num)) return String(num);
    return text;
  }

  function getUniqueColumnValues(colIndex) {
    if (!table) return [];
    const field = fieldFor(colIndex);
    const valuesWithCounts = new Map();
    table.getData().forEach(obj => {
      const key = normalizeRecodeKey(obj[field]);
      const label = key === '__BLANK__' ? '(blank)' : key;
      const entry = valuesWithCounts.get(key) || { value: key, label, count: 0 };
      entry.count += 1;
      valuesWithCounts.set(key, entry);
    });
    return Array.from(valuesWithCounts.values()).sort((a, b) => {
      const aNum = Number(a.value), bNum = Number(b.value);
      if (Number.isFinite(aNum) && Number.isFinite(bNum)) return aNum - bNum;
      return a.label.localeCompare(b.label);
    });
  }

  // ---- column + row operations (delegate to backend, refresh on result) ----

  async function handleColumnChange(action, details = {}) {
    const headers = getHeaders();
    let payload;

    if (action === 'rename') {
      const oldName = details.oldName;
      const newName = (details.newName || '').trim();
      if (!newName) return;
      payload = { action, oldName, newName };
    } else if (action === 'remove') {
      payload = { action, name: headers[details.index] };
    } else if (action === 'remove_multiple') {
      payload = { action, names: details.names || [] };
      if (!payload.names.length) return;
    } else if (action === 'add') {
      const raw = prompt('Enter new column name:', 'NewColumn');
      const newName = raw ? raw.trim() : '';
      if (!newName) return;
      payload = { action, name: newName, index: details.index };
    } else {
      return;
    }

    try {
      const result = await updateColumn(payload);
      if (result && Array.isArray(result.headers) && Array.isArray(result.data)
          && typeof onTableDataUpdate === 'function') {
        onTableDataUpdate(result);
      }
      if (action === 'rename') updateStatus(`Column '${payload.oldName}' renamed to '${payload.newName}'.`);
      else if (action === 'add') updateStatus(`Column '${payload.name}' added successfully.`);
      else if (action === 'remove') updateStatus(`Column '${payload.name}' removed successfully.`);
      else if (action === 'remove_multiple') updateStatus(`${payload.names.length} column(s) removed successfully.`);
      return result;
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
      throw error;
    }
  }

  async function handleRowDelete(indices) {
    if (!indices.length) return;
    const label = indices.length === 1 ? `row ${indices[0] + 1}` : `${indices.length} rows`;
    if (!confirm(`Are you sure you want to permanently delete ${label}?`)) return;
    try {
      updateStatus(`Deleting ${label}...`);
      const result = await deleteRows(indices);
      if (result && Array.isArray(result.headers) && Array.isArray(result.data)
          && typeof onTableDataUpdate === 'function') {
        onTableDataUpdate(result);
      }
      updateStatus(`${indices.length} row(s) deleted successfully.`);
      return result;
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
      throw error;
    }
  }

  async function castColumnType(colIdx, newType) {
    const headers = getHeaders();
    const colName = headers[colIdx];
    if (!colName) return;
    updateStatus(`Casting column '${colName}' to ${newType}...`);
    try {
      const result = await castColumn({ name: colName, newType });
      setColumnDataType(colName, result.new_dtype);
      // Update just this column's values in place.
      if (table && Array.isArray(result.column_data)) {
        const field = fieldFor(colIdx);
        const rows = table.getRows();
        result.column_data.forEach((val, i) => {
          if (rows[i]) rows[i].update({ [field]: val });
        });
      }
      updateGridSettings();
      if (typeof onExclusionStateUpdate === 'function') onExclusionStateUpdate(result);
      updateStatus(`Column '${colName}' successfully cast to ${result.new_dtype}.`);
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  }

  return {
    initialize,
    destroy,
    loadTableData,
    getHotInstance,
    getUniqueColumnValues,
    updateGridSettings,
    handleColumnChange,
    setExclusionState,
    setImputationState,
    toggleImputedData,
    highlightColumns,
  };
}
