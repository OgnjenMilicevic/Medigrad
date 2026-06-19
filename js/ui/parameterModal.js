import { taskConfigs } from '../config/taskConfigs.js';
import { getDialogState, setDialogState, recordAction } from '../state/sessionState.js';

// Small inline-SVG glyphs for the visual plot-type picker (plot_gallery field).
// Kept deliberately schematic — enough to recognise the chart at a glance.
const PLOT_GLYPHS = {
  histogram: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="18" width="6" height="12"/><rect x="13" y="10" width="6" height="20"/><rect x="22" y="4" width="6" height="26"/><rect x="31" y="14" width="6" height="16"/></svg>',
  density: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 29 C12 29 14 8 23 8 C32 8 34 29 43 29"/></svg>',
  ecdf: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 28 H14 V20 H24 V11 H34 V5 H42" stroke-linejoin="round"/></svg>',
  qq: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="29" x2="41" y2="5" stroke-dasharray="3 3"/><circle cx="13" cy="24" r="1.6" fill="currentColor"/><circle cx="21" cy="19" r="1.6" fill="currentColor"/><circle cx="29" cy="13" r="1.6" fill="currentColor"/><circle cx="35" cy="10" r="1.6" fill="currentColor"/></svg>',
  box: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><line x1="23" y1="4" x2="23" y2="10"/><rect x="14" y="10" width="18" height="14"/><line x1="14" y1="17" x2="32" y2="17"/><line x1="23" y1="24" x2="23" y2="30"/></svg>',
  violin: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4 C14 9 14 16 18 17 C14 18 14 25 23 30 C32 25 32 18 28 17 C32 16 32 9 23 4 Z"/></svg>',
  strip: '<svg viewBox="0 0 46 34" fill="currentColor"><circle cx="20" cy="8" r="1.6"/><circle cx="26" cy="12" r="1.6"/><circle cx="21" cy="16" r="1.6"/><circle cx="27" cy="20" r="1.6"/><circle cx="22" cy="24" r="1.6"/><circle cx="25" cy="28" r="1.6"/></svg>',
  raincloud: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 14 C12 6 22 6 26 13" /><g fill="currentColor" stroke="none"><circle cx="10" cy="24" r="1.5"/><circle cx="16" cy="27" r="1.5"/><circle cx="22" cy="24" r="1.5"/><circle cx="28" cy="27" r="1.5"/></g></svg>',
  _default: '<svg viewBox="0 0 46 34" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="5" width="36" height="24" rx="2"/></svg>',
};

function getAllFields(config) {
  if (Array.isArray(config.fields)) return config.fields;
  if (Array.isArray(config.levels)) {
    return config.levels.flatMap(level => level.fields || []);
  }
  return [];
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function getHeaderOptions(headers, { optional = false } = {}) {
  const options = headers
    .map(h => `<option value="${escapeHtml(h)}">${escapeHtml(h)}</option>`)
    .join('');

  if (optional) {
    return `<option value="">-- None --</option>${options}`;
  }

  return options;
}

function getSelectOptions(field, headers, value) {
  const selectedValues = field.multiple
    ? Array.isArray(value) ? value : []
    : [value];

  if (field.type === 'select_headers') {
    const options = headers
      .map(h => {
        const selected = selectedValues.includes(h) ? 'selected' : '';
        return `<option value="${escapeHtml(h)}" ${selected}>${escapeHtml(h)}</option>`;
      })
      .join('');

    if (field.optional) {
      const noneSelected = !value ? 'selected' : '';
      return `<option value="" ${noneSelected}>-- None --</option>${options}`;
    }

    return options;
  }

  if (field.type === 'select') {
    return (field.options || [])
      .map(opt => {
        const optionValue = typeof opt === 'string' ? opt : opt.value;
        const label = typeof opt === 'string' ? opt : opt.label;
        const selected = selectedValues.includes(optionValue) ? 'selected' : '';

        return `<option value="${escapeHtml(String(optionValue))}" ${selected}>${escapeHtml(String(label))}</option>`;
      })
      .join('');
  }
  return '';
}

// ---------------------------------------------------------------------------
// Random Effects Builder
// ---------------------------------------------------------------------------

function _reHeaderOptions(headers, selected = '') {
  const none = `<option value="">-- None --</option>`;
  const opts = headers
    .map(h => {
      const sel = h === selected ? 'selected' : '';
      return `<option value="${escapeHtml(h)}" ${sel}>${escapeHtml(h)}</option>`;
    })
    .join('');
  return none + opts;
}

function _reSlopeOptions(headers, selected = []) {
  return headers
    .map(h => {
      const sel = selected.includes(h) ? 'selected' : '';
      return `<option value="${escapeHtml(h)}" ${sel}>${escapeHtml(h)}</option>`;
    })
    .join('');
}

function _renderPrimaryBlock(headers, saved) {
  const s = saved || {};
  const covHidden = !(Array.isArray(s.slopes) && s.slopes.length > 0);

  return `
    <div class="re-block re-primary" data-re-index="0" data-re-role="primary">
      <div class="text-xs font-semibold text-blue-600 mb-2">★ Primary Random Effect</div>
      <div class="space-y-2">
        <div>
          <span class="re-field-label">Grouping Variable</span>
          <select class="re-groups">${_reHeaderOptions(headers, s.groups)}</select>
        </div>
        <div>
          <span class="re-field-label">Random Slopes <span class="text-gray-400">(optional)</span></span>
          <select class="re-slopes" multiple>${_reSlopeOptions(headers, s.slopes || [])}</select>
          <p class="text-xs text-gray-400 mt-0.5">Hold Ctrl/Cmd to select multiple.</p>
        </div>
        <div class="re-cov-wrapper" ${covHidden ? 'style="display:none"' : ''}>
          <span class="re-field-label">Covariance Structure</span>
          <select class="re-covariance">
            <option value="unstructured" ${s.covariance === 'unstructured' || !s.covariance ? 'selected' : ''}>Unstructured (full)</option>
            <option value="diagonal" ${s.covariance === 'diagonal' ? 'selected' : ''}>Diagonal (no correlations)</option>
            <option value="cs" ${s.covariance === 'cs' ? 'selected' : ''}>Compound Symmetry</option>
          </select>
        </div>
      </div>
    </div>
  `;
}

function _renderAdditionalBlock(headers, index, saved) {
  const s = saved || {};
  const isNested = s.structure === 'nested';

  return `
    <div class="re-block re-additional" data-re-index="${index}" data-re-role="additional">
      <div class="flex justify-between items-center mb-2">
        <span class="text-xs font-semibold text-gray-500">Additional Random Effect</span>
        <button type="button" class="re-remove-btn text-red-500 text-xs hover:underline">Remove</button>
      </div>
      <div class="space-y-2">
        <div>
          <span class="re-field-label">Grouping Variable</span>
          <select class="re-groups">${_reHeaderOptions(headers, s.groups)}</select>
        </div>
        <div>
          <span class="re-field-label">Structure</span>
          <select class="re-structure">
            <option value="crossed" ${!isNested ? 'selected' : ''}>Crossed (independent)</option>
            <option value="nested" ${isNested ? 'selected' : ''}>Nested within…</option>
          </select>
        </div>
    <div class="re-nested-parent" ${isNested ? '' : 'style="display:none"'}>
          <span class="re-field-label">Parent Group</span>
          <select class="re-parent" data-saved-parent="${escapeHtml(s.nested_in || '')}"><option value="">-- Select --</option></select>
        </div>
      </div>
    </div>
  `;
}

function renderRandomEffectsBuilder(field, headers, savedState) {
  const saved = savedState || [];
  const primarySaved = Array.isArray(saved) && saved.length > 0 ? saved[0] : null;
  const additionalSaved = Array.isArray(saved) && saved.length > 1 ? saved.slice(1) : [];

  let additionalHtml = '';
  additionalSaved.forEach((s, i) => {
    additionalHtml += _renderAdditionalBlock(headers, i + 1, s);
  });

  return `
    <div class="param-field space-y-3" data-field-id="${field.id}" id="${field.id}">
      <label class="block text-sm font-medium text-gray-700">${escapeHtml(field.label)}</label>
      ${_renderPrimaryBlock(headers, primarySaved)}
      <div id="re-additional-container">${additionalHtml}</div>
      <button type="button" id="re-add-btn"
        class="text-blue-600 text-sm font-medium hover:underline">
        + Add Random Effect
      </button>
      <div class="re-info-note">
        Additional effects support random intercepts only.
        Only the primary grouping variable supports random slopes and covariance structure.
      </div>
    </div>
  `;
}

let _reNextIndex = 100;

function bindRandomEffectsBuilder(container, headers) {
  if (!container) return;
  const builder = container.querySelector('[data-field-id="random_effects"]');
  if (!builder) return;

  const addBtn = builder.querySelector('#re-add-btn');
  const additionalContainer = builder.querySelector('#re-additional-container');

  // --- Primary: show/hide covariance based on slope selection ---
  const primaryBlock = builder.querySelector('[data-re-role="primary"]');
  if (primaryBlock) {
    const slopesSelect = primaryBlock.querySelector('.re-slopes');
    const covWrapper = primaryBlock.querySelector('.re-cov-wrapper');
    if (slopesSelect && covWrapper) {
      slopesSelect.addEventListener('change', () => {
        const hasSlopes = Array.from(slopesSelect.selectedOptions).length > 0;
        covWrapper.style.display = hasSlopes ? '' : 'none';
      });
    }
  }

  // --- Add button ---
  if (addBtn && additionalContainer) {
    addBtn.addEventListener('click', () => {
      const html = _renderAdditionalBlock(headers, _reNextIndex++, null);
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      const block = wrapper.firstElementChild;
      additionalContainer.appendChild(block);
      _bindAdditionalBlock(block, builder);
      _updateParentDropdowns(builder);
    });
  }

  // --- Primary group change updates parent dropdowns ---
  const primaryGroups = primaryBlock?.querySelector('.re-groups');
  if (primaryGroups) {
    primaryGroups.addEventListener('change', () => _updateParentDropdowns(builder));
  }

  // --- Bind existing additional blocks ---
  additionalContainer?.querySelectorAll('[data-re-role="additional"]').forEach(block => {
    _bindAdditionalBlock(block, builder);
  });

  _updateParentDropdowns(builder);
}

function _updateParentDropdowns(builder) {
  // Collect all currently selected grouping variables
  const groups = [];
  builder.querySelectorAll('.re-block').forEach(block => {
    const val = block.querySelector('.re-groups')?.value;
    if (val) groups.push(val);
  });

  // Update each additional block's parent dropdown to only show sibling groups
  builder.querySelectorAll('[data-re-role="additional"]').forEach(block => {
    const parentSelect = block.querySelector('.re-parent');
    const ownGroup = block.querySelector('.re-groups')?.value;
    if (!parentSelect) return;

    const currentParent = parentSelect.value || parentSelect.dataset.savedParent || '';
    // Clear saved after first use
    parentSelect.dataset.savedParent = '';
    const options = groups
      .filter(g => g !== ownGroup)
      .map(g => {
        const sel = g === currentParent ? 'selected' : '';
        return `<option value="${escapeHtml(g)}" ${sel}>${escapeHtml(g)}</option>`;
      })
      .join('');
    parentSelect.innerHTML = `<option value="">-- Select --</option>${options}`;
  });
}

function _bindAdditionalBlock(block, builder) {
  // Remove button
  const removeBtn = block.querySelector('.re-remove-btn');
  if (removeBtn) {
    removeBtn.addEventListener('click', () => {
      block.remove();
      _updateParentDropdowns(builder);
    });
  }

  // Group change updates parent dropdowns
  const groupsSelect = block.querySelector('.re-groups');
  if (groupsSelect) {
    groupsSelect.addEventListener('change', () => _updateParentDropdowns(builder));
  }

  // Structure toggle → show/hide nested parent
  const structureSelect = block.querySelector('.re-structure');
  const nestedParent = block.querySelector('.re-nested-parent');
  if (structureSelect && nestedParent) {
    structureSelect.addEventListener('change', () => {
      nestedParent.style.display = structureSelect.value === 'nested' ? '' : 'none';
    });
  }
}

function extractRandomEffects(container) {
  const builder = container.querySelector('[data-field-id="random_effects"]');
  if (!builder) return [];

  const effects = [];

  // Primary
  const primary = builder.querySelector('[data-re-role="primary"]');
  if (primary) {
    const groups = primary.querySelector('.re-groups')?.value || '';
    const slopes = Array.from(primary.querySelector('.re-slopes')?.selectedOptions || []).map(o => o.value);
    const covariance = primary.querySelector('.re-covariance')?.value || 'unstructured';

    if (groups) {
      effects.push({
        groups,
        slopes,
        covariance: slopes.length > 0 ? covariance : 'diagonal',
        nested_in: null,
        role: 'primary',
      });
    }
  }

  // Additional
  builder.querySelectorAll('[data-re-role="additional"]').forEach(block => {
    const groups = block.querySelector('.re-groups')?.value || '';
    if (!groups) return;

    const structure = block.querySelector('.re-structure')?.value || 'crossed';
    const nestedIn = structure === 'nested'
      ? (block.querySelector('.re-parent')?.value || null)
      : null;

    effects.push({
      groups,
      slopes: [],
      covariance: 'diagonal',
      nested_in: nestedIn,
      role: 'additional',
    });
  });

  return effects;
}

// ---------------------------------------------------------------------------
// Interaction Term Builder
// ---------------------------------------------------------------------------

function renderInteractionBuilder(field, headers, savedState) {
  const saved = Array.isArray(savedState) ? savedState : [];
  const chipsHtml = saved.map((terms, i) =>
    `<span class="ix-chip" data-ix-index="${i}" data-ix-terms='${escapeHtml(JSON.stringify(terms))}'>
      ${terms.map(t => escapeHtml(t)).join(' × ')}
      <button type="button" class="ix-chip-remove">&times;</button>
    </span>`
  ).join('');

  const headerOpts = headers
    .map(h => `<option value="${escapeHtml(h)}">${escapeHtml(h)}</option>`)
    .join('');

  return `
    <div class="param-field space-y-2" data-field-id="${field.id}" id="${field.id}">
      <label class="block text-sm font-medium text-gray-700">${escapeHtml(field.label)}</label>
      <div class="ix-composer">
        <div class="ix-dropdowns">
          <select class="ix-term">${headerOpts}</select>
          <span class="ix-times">×</span>
          <select class="ix-term">${headerOpts}</select>
        </div>
        <div class="ix-actions">
          <button type="button" class="ix-add-term-btn" title="Add another variable to this interaction">+ term</button>
          <button type="button" class="ix-add-btn">Add</button>
        </div>
      </div>
      <div class="ix-chips">${chipsHtml}</div>
    </div>
  `;
}

function bindInteractionBuilder(container, headers) {
  const builders = container.querySelectorAll('[data-field-id="interactions"]');
  builders.forEach(builder => _bindOneInteractionBuilder(builder, headers));
}

function _bindOneInteractionBuilder(builder, headers) {
  const composer = builder.querySelector('.ix-composer');
  const dropdowns = composer.querySelector('.ix-dropdowns');
  const chipsContainer = builder.querySelector('.ix-chips');
  const addBtn = composer.querySelector('.ix-add-btn');
  const addTermBtn = composer.querySelector('.ix-add-term-btn');

  const headerOpts = headers
    .map(h => `<option value="${escapeHtml(h)}">${escapeHtml(h)}</option>`)
    .join('');

  // + term: append another dropdown
  addTermBtn.addEventListener('click', () => {
    const span = document.createElement('span');
    span.className = 'ix-times';
    span.textContent = '×';
    dropdowns.appendChild(span);

    const sel = document.createElement('select');
    sel.className = 'ix-term';
    sel.innerHTML = headerOpts;
    dropdowns.appendChild(sel);
  });

  // Add: read all dropdowns, validate, create chip
  addBtn.addEventListener('click', () => {
    const selects = dropdowns.querySelectorAll('.ix-term');
    const terms = Array.from(selects).map(s => s.value);

    // Must have at least 2 terms
    if (terms.length < 2) return;

    // No duplicates within one interaction
    if (new Set(terms).size !== terms.length) {
      alert('An interaction cannot include the same variable twice.');
      return;
    }

    // Check if this interaction already exists
    const existing = extractInteractions(builder.closest('.modal-body') || document.body);
    const sorted = [...terms].sort().join('|');
    for (const ex of existing) {
      if ([...ex].sort().join('|') === sorted) {
        alert('This interaction is already added.');
        return;
      }
    }

    _addInteractionChip(chipsContainer, terms);
    _resetComposer(dropdowns, headerOpts);
  });

  // Bind remove on existing chips
  chipsContainer.querySelectorAll('.ix-chip-remove').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.ix-chip').remove());
  });
}

function _addInteractionChip(container, terms) {
  const chip = document.createElement('span');
  chip.className = 'ix-chip';
  chip.dataset.ixTerms = JSON.stringify(terms);
  chip.innerHTML = `${terms.map(t => escapeHtml(t)).join(' × ')}
    <button type="button" class="ix-chip-remove">&times;</button>`;
  chip.querySelector('.ix-chip-remove').addEventListener('click', () => chip.remove());
  container.appendChild(chip);
}

function _resetComposer(dropdowns, headerOpts) {
  // Remove extra dropdowns and separators, keep first two
  const children = Array.from(dropdowns.children);
  children.forEach((child, i) => {
    if (i > 2) child.remove(); // keep: select, ×, select
  });
  // Reset the remaining selects to first option
  dropdowns.querySelectorAll('.ix-term').forEach(s => s.selectedIndex = 0);
}

function extractInteractions(container) {
  const builder = container.querySelector('[data-field-id="interactions"]');
  if (!builder) return [];

  const interactions = [];

  // From chips with data-ixTerms
  builder.querySelectorAll('.ix-chip[data-ix-terms]').forEach(chip => {
    try {
      const terms = JSON.parse(chip.dataset.ixTerms);
      if (Array.isArray(terms) && terms.length >= 2) {
        interactions.push(terms);
      }
    } catch (e) { /* skip malformed */ }
  });

  // From chips without data attribute (rendered from saved state)
  builder.querySelectorAll('.ix-chip:not([data-ix-terms])').forEach(chip => {
    const text = chip.textContent.replace('×', '').trim();
    const terms = text.split(/\s*×\s*/).map(t => t.trim()).filter(Boolean);
    if (terms.length >= 2) {
      interactions.push(terms);
    }
  });

  return interactions;
}

// ---------------------------------------------------------------------------
// Search + chips multi-select widget. Each widget is backed by a hidden
// <select multiple> (same id), which holds the real selection so existing
// value-collection code is unchanged. The chips UI drives that select.
// ---------------------------------------------------------------------------

function bindChipsMultiselects(scopeEl) {
  const widgets = (scopeEl || document).querySelectorAll('.chips-multiselect');
  widgets.forEach(widget => {
    const hidden = widget.querySelector('.chips-hidden-select');
    const chipsBox = widget.querySelector('.chips-box');
    const chipsSelected = widget.querySelector('.chips-selected');
    const input = widget.querySelector('.chips-input');
    const dropdown = widget.querySelector('.chips-dropdown');
    if (!hidden || !chipsSelected || !input || !dropdown) return;

    const allOptions = Array.from(hidden.options).map(o => o.value);

    function selectedValues() {
      return Array.from(hidden.selectedOptions).map(o => o.value);
    }

    function setSelected(value, on) {
      const opt = Array.from(hidden.options).find(o => o.value === value);
      if (opt) opt.selected = on;
      // Notify any showIf listeners that depend on this field.
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function renderChips() {
      chipsSelected.innerHTML = '';
      selectedValues().forEach(val => {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.innerHTML = `${escapeHtml(val)}<button type="button" class="chip-remove" aria-label="Remove">&times;</button>`;
        chip.querySelector('.chip-remove').addEventListener('click', (e) => {
          e.stopPropagation();
          setSelected(val, false);
          renderChips();
          renderDropdown(input.value);
        });
        chipsSelected.appendChild(chip);
      });
    }

    function renderDropdown(filterText) {
      const ft = (filterText || '').trim().toLowerCase();
      const chosen = new Set(selectedValues());
      const matches = allOptions.filter(o =>
        !chosen.has(o) && o.toLowerCase().includes(ft)
      );
      dropdown.innerHTML = '';
      if (matches.length === 0) {
        dropdown.hidden = true;
        return;
      }
      matches.forEach((opt, idx) => {
        const item = document.createElement('div');
        item.className = 'chips-option';
        item.textContent = opt;
        item.dataset.value = opt;
        if (idx === 0) item.classList.add('active');
        item.addEventListener('mousedown', (e) => {
          // mousedown (not click) so it fires before input blur
          e.preventDefault();
          setSelected(opt, true);
          input.value = '';
          renderChips();
          renderDropdown('');
          input.focus();
        });
        dropdown.appendChild(item);
      });
      dropdown.hidden = false;
    }

    function moveActive(dir) {
      const items = Array.from(dropdown.querySelectorAll('.chips-option'));
      if (items.length === 0) return;
      let i = items.findIndex(el => el.classList.contains('active'));
      if (i >= 0) items[i].classList.remove('active');
      i = (i + dir + items.length) % items.length;
      items[i].classList.add('active');
      items[i].scrollIntoView({ block: 'nearest' });
    }

    input.addEventListener('input', () => renderDropdown(input.value));
    input.addEventListener('focus', () => renderDropdown(input.value));
    chipsBox.addEventListener('click', () => input.focus());

    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); moveActive(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); moveActive(-1); }
      else if (e.key === 'Enter') {
        const active = dropdown.querySelector('.chips-option.active');
        if (active && !dropdown.hidden) {
          e.preventDefault();
          setSelected(active.dataset.value, true);
          input.value = '';
          renderChips();
          renderDropdown('');
        }
      } else if (e.key === 'Backspace' && input.value === '') {
        const vals = selectedValues();
        if (vals.length) {
          setSelected(vals[vals.length - 1], false);
          renderChips();
          renderDropdown('');
        }
      } else if (e.key === 'Escape') {
        dropdown.hidden = true;
      }
    });

    // Hide dropdown when focus leaves the widget.
    document.addEventListener('click', (e) => {
      if (!widget.contains(e.target)) dropdown.hidden = true;
    });

    renderChips();
  });
}

// ---------------------------------------------------------------------------

function renderField(field, headers, savedState = {}) {
  savedState = savedState || {}; // extra safety
  const label = `
    <label for="${field.id}" class="block text-sm font-medium text-gray-700">
      ${escapeHtml(field.label)}
      ${field.required ? '<span class="text-red-500">*</span>' : ''}
    </label>
  `;
  const rememberedValue = savedState[field.id];
  const value = rememberedValue !== undefined ? rememberedValue : field.default;

  if (field.type === 'number') {
    const inputValue = value ?? '';
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <input
          type="number"
          id="${field.id}"
          value="${escapeHtml(String(inputValue))}"
          class="mt-1 block w-full border border-gray-300 rounded-md p-2 shadow-sm"
        >
      </div>
    `;
  }

  if (field.type === 'text') {
    const inputValue = value ?? (field.default ?? '');
    const ph = field.placeholder ? `placeholder="${escapeHtml(field.placeholder)}"` : '';
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <input
          type="text"
          id="${field.id}"
          value="${escapeHtml(String(inputValue))}"
          ${ph}
          class="mt-1 block w-full border border-gray-300 rounded-md p-2 shadow-sm"
        >
      </div>
    `;
  }

  if (field.type === 'plot_gallery') {
    // A visual chart-type picker: a hidden input (the value the modal reads and
    // that drives showIf) plus a grid of clickable cards with small glyphs.
    // bindPlotGallery wires clicks, active styling, and dependent updates.
    const current = (value != null && value !== '')
      ? String(value)
      : (field.default || (field.options && field.options[0] && field.options[0].value) || '');
    const cards = (field.options || []).map(opt => {
      const active = String(opt.value) === current;
      return `
        <button type="button" class="pg-card${active ? ' pg-active' : ''}"
                data-pg-value="${escapeHtml(String(opt.value))}"
                title="${escapeHtml(opt.label)}"
                style="display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 6px;border:2px solid ${active ? '#2563eb' : '#e5e7eb'};border-radius:8px;background:#fff;cursor:pointer;min-width:84px;">
          <span style="width:46px;height:34px;display:inline-flex;align-items:center;justify-content:center;color:#374151;">${PLOT_GLYPHS[opt.value] || PLOT_GLYPHS._default}</span>
          <span style="font-size:11px;color:#374151;text-align:center;line-height:1.1;">${escapeHtml(opt.label)}</span>
        </button>`;
    }).join('');
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <input type="hidden" id="${field.id}" value="${escapeHtml(current)}">
        <div class="pg-grid" data-pg-for="${field.id}"
             style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;">
          ${cards}
        </div>
        <style>
          .pg-card.pg-active { border-color:#2563eb !important; box-shadow:0 0 0 1px #2563eb33; }
          .pg-card:hover { border-color:#93c5fd; }
        </style>
      </div>
    `;
  }

  if (field.type === 'select_headers' && field.multiple) {
    // Search + chips multi-select. A hidden <select multiple> with the same id
    // holds the actual selection so the existing value-collection code keeps
    // working unchanged; the chips UI just drives that hidden select.
    const selectedValues = Array.isArray(value) ? value.filter(v => headers.includes(v)) : [];
    const hiddenOptions = headers
      .map(h => `<option value="${escapeHtml(h)}"${selectedValues.includes(h) ? ' selected' : ''}>${escapeHtml(h)}</option>`)
      .join('');
    const placeholder = field.optional
      ? 'Type to search… (leave empty to use all)'
      : 'Type to search and add…';
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <div class="chips-multiselect" data-chips-for="${field.id}">
          <select id="${field.id}" multiple class="chips-hidden-select">${hiddenOptions}</select>
          <div class="chips-box">
            <span class="chips-selected"></span>
            <input type="text" class="chips-input" placeholder="${escapeHtml(placeholder)}" autocomplete="off">
          </div>
          <div class="chips-dropdown" hidden></div>
        </div>
      </div>
    `;
  }

  if (field.type === 'select' || field.type === 'select_headers') {
    const options = getSelectOptions(field, headers, value);
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <select
          id="${field.id}"
          ${field.multiple ? 'multiple' : ''}
          class="mt-1 block w-full border border-gray-300 rounded-md p-2 shadow-sm"
        >
          ${options}
        </select>
      </div>
    `;
  }

  if (field.type === 'select_column_values') {
    // A dependent dropdown populated with the unique values of whatever column
    // the `depends_on` field currently names. Options are filled in/refreshed by
    // bindColumnValueFields after render; we start with a placeholder.
    const placeholder = field.optional
      ? '<option value="">-- None --</option>'
      : '<option value="">-- pick a column above first --</option>';
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        ${label}
        <select
          id="${field.id}"
          data-depends-on="${escapeHtml(field.depends_on || '')}"
          data-current-value="${escapeHtml(value == null ? '' : String(value))}"
          class="mt-1 block w-full border border-gray-300 rounded-md p-2 shadow-sm"
        >
          ${placeholder}
        </select>
      </div>
    `;
  }

  if (field.type === 'checkbox') {
    const checked = value ? 'checked' : '';
    return `
      <div class="param-field space-y-1" data-field-id="${field.id}">
        <label class="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            id="${field.id}"
            ${checked}
            class="h-4 w-4"
          >
          <span>${escapeHtml(field.label)}</span>
        </label>
      </div>
    `;
  }

  if (field.type === 'random_effects_builder') {
    return renderRandomEffectsBuilder(field, headers, value);
  }

  if (field.type === 'interaction_builder') {
    return renderInteractionBuilder(field, headers, value);
  }

  return '';
}

function renderFieldsList(fields, headers, savedState = {}) {
  return fields.map(field => renderField(field, headers, savedState)).join('');
}

function validateField(field, value) {
  if (!field.required) return null;

  if (field.multiple) {
    if (!Array.isArray(value) || value.length === 0) {
      return `${field.label} is required.`;
    }
    return null;
  }

  if (value === '' || value === null || value === undefined) {
    return `${field.label} is required.`;
  }

  return null;
}

function buildPayload(config) {
  const payload = {};

  const fields = getAllFields(config);

  for (const field of fields) {
    // A field hidden by a showIf condition is not part of this submission.
    // (Lets a consolidated modal carry, e.g., a value field that is `x` for some
    // plot types and `y` for others — only the visible one is collected.)
    const wrapper = document.querySelector(`[data-field-id="${field.id}"]`);
    if (wrapper && wrapper.classList.contains('hidden')) {
      continue;
    }

    // Random effects builder has custom extraction
    if (field.type === 'random_effects_builder') {
      payload[field.id] = extractRandomEffects(document.querySelector('.modal-body') || document.body);
      continue;
    }

    // Interaction builder has custom extraction
    if (field.type === 'interaction_builder') {
      payload[field.id] = extractInteractions(document.querySelector('.modal-body') || document.body);
      continue;
    }

    const el = document.getElementById(field.id);
    if (!el) continue;

    let value;

    if (field.type === 'checkbox') {
      value = el.checked;
    } else if (field.type === 'number') {
      value = el.value === '' ? null : parseFloat(el.value);
    } else if (field.multiple) {
      // Drop the empty-string "None" option (and any blank) so an unselected
      // or None-selected multi-select sends [] rather than [""], which the
      // backend treats as "use all applicable columns".
      value = Array.from(el.selectedOptions)
        .map(opt => opt.value)
        .filter(v => v !== null && String(v).trim() !== '');
    } else {
      value = el.value;

      if (value === 'true') value = true;
      if (value === 'false') value = false;
    }

    const validationError = validateField(field, value);
    if (validationError) {
      throw new Error(validationError);
    }

    payload[field.id] = value;
  }

  // plot_type resolution: a `plot_type` chooser/gallery field (collected above)
  // wins; otherwise fall back to the config's static plot_type.
  if (!payload.plot_type && config.plot_type) {
    payload.plot_type = config.plot_type;
  }

  return payload;
}

function renderLevel(level, headers, savedState = {}, { open = false, accent = false } = {}) {
  const bodyClass = open ? 'complexity-body open' : 'complexity-body';
  const chevron = open ? '▲' : '▼';

  return `
    <div class="complexity-level ${accent ? 'rounded border border-gray-200 bg-gray-50 p-4' : ''}">
      <button
        type="button"
        class="complexity-header w-full"
        data-role="level-toggle"
        aria-expanded="${open ? 'true' : 'false'}"
      >
        <span>${escapeHtml(level.name)}</span>
        <span class="text-xs" data-role="chevron">${chevron}</span>
      </button>
      <div class="${bodyClass}">
        <div class="mt-4 space-y-4">
          ${renderFieldsList(level.fields || [], headers, savedState)}
        </div>
      </div>
    </div>
  `;
}

function updateConditionalFields(config) {
  getAllFields(config).forEach(field => {
    if (!field.showIf) return;

    const controller = document.getElementById(field.showIf.field);
    const target = document.querySelector(
      `[data-field-id="${field.id}"]`
    );

    if (!controller || !target) return;

    let currentValue;

    if (controller.type === 'checkbox') {
      currentValue = controller.checked;
    } else {
      currentValue = controller.value;
    }

    const shouldShow = Array.isArray(field.showIf.value)
      ? field.showIf.value.includes(currentValue)
      : currentValue === field.showIf.value;

    target.classList.toggle('hidden', !shouldShow);
  });
}

export function createParameterModal({
  modalElement,
  onRunTask,
  onError = (msg) => alert(msg),
}) {
  const titleEl = modalElement.querySelector('#param-modal-title');
  const bodyEl = modalElement.querySelector('#param-modal-body');
  const closeBtn = modalElement.querySelector('.close-button');

  if (closeBtn) {
    closeBtn.onclick = () => {
      modalElement.style.display = 'none';
    };
  }

  // Wire the visual plot-type picker (type: plot_gallery). Clicking a card sets
  // the hidden input's value and dispatches 'change' (so showIf fields update),
  // updates active styling, and applies two mitigations: it resets the
  // significance toggle and rewrites the value field's axis-role label so the
  // x/y orientation change is visible when switching plot types.
  function bindPlotGallery(scopeEl) {
    const grids = scopeEl.querySelectorAll('.pg-grid[data-pg-for]');
    grids.forEach(grid => {
      const inputId = grid.getAttribute('data-pg-for');
      const input = document.getElementById(inputId);
      if (!input) return;

      const yFamily = ['box', 'violin', 'strip', 'raincloud'];
      const applySideEffects = (val) => {
        // (1) reset the significance toggle so stale hidden state can't mislead
        const sig = scopeEl.querySelector('#show_significance');
        if (sig && sig.type === 'checkbox') sig.checked = false;
        // (2) dynamic axis-role label on the value field
        const valLabel = scopeEl.querySelector('[data-field-id="value"] label');
        if (valLabel) {
          const axis = yFamily.includes(val) ? 'y-axis' : 'x-axis';
          valLabel.textContent = `Value column — numeric (${axis})`;
        }
      };

      grid.querySelectorAll('.pg-card').forEach(card => {
        card.addEventListener('click', () => {
          const val = card.getAttribute('data-pg-value');
          input.value = val;
          grid.querySelectorAll('.pg-card').forEach(c => c.classList.remove('pg-active'));
          card.classList.add('pg-active');
          applySideEffects(val);
          input.dispatchEvent(new Event('change', { bubbles: true }));
        });
      });
      applySideEffects(input.value); // initial label for the default selection
    });
  }

  // Wire dependent dropdowns (type: select_column_values). Each such field
  // names a parent field via data-depends-on; when the parent's value changes
  // we repopulate this select with that column's unique values. We also fill it
  // once on open if the parent already has a value (e.g. restored state).
  function bindColumnValueFields(scopeEl, getColumnValues) {
    if (typeof getColumnValues !== 'function') return;
    const dependents = scopeEl.querySelectorAll('select[data-depends-on]');
    dependents.forEach(sel => {
      const parentId = sel.getAttribute('data-depends-on');
      const wanted = sel.getAttribute('data-current-value') || '';
      const parent = parentId ? document.getElementById(parentId) : null;

      const repopulate = () => {
        const col = parent ? parent.value : '';
        const values = col ? getColumnValues(col) : [];
        const optional = sel.options.length && sel.options[0].value === '' &&
          /None/.test(sel.options[0].textContent);
        const head = optional ? '<option value="">-- None --</option>' : '';
        sel.innerHTML = head + values.map(v => {
          const selected = String(v.value) === String(wanted) ? 'selected' : '';
          return `<option value="${escapeHtml(String(v.value))}" ${selected}>${escapeHtml(String(v.label))}</option>`;
        }).join('');
        if (!values.length && !head) {
          sel.innerHTML = '<option value="">-- pick a column above first --</option>';
        }
      };

      if (parent) {
        parent.addEventListener('change', repopulate);
        // Only pre-fill if a control value was actually restored from saved
        // state — NOT from the parent select's default first option.
        if (wanted) repopulate();
      }
    });
  }

  function bindLevelToggles(scopeEl) {    scopeEl.querySelectorAll('[data-role="level-toggle"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const section = btn.closest('.complexity-level');
        const body = section?.querySelector('.complexity-body');
        const chevron = btn.querySelector('[data-role="chevron"]');
        if (!body) return;

        const isOpen = body.classList.toggle('open');
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');

        if (chevron) {
          chevron.textContent = isOpen ? '▲' : '▼';
        }
      });
    });
  }

  function show(taskType, headers, getColumnValues = null) {
    const config = taskConfigs[taskType];

    if (!config) {
      onError(`Unknown task type: ${taskType}`);
      return;
    }

    const rawSavedState = getDialogState(taskType);
    const savedState = sanitizeSavedStateForConfig(rawSavedState, config, headers) || {};
    titleEl.textContent = config.title;

    const modalContent = modalElement.querySelector('.modal-content');

    if (Array.isArray(config.levels) && config.levels.length > 0) {
      const firstLevel = config.levels[0];
      const advancedLevels = config.levels.slice(1);

      const advancedHtml = advancedLevels.length
        ? `
          <div id="advanced-sections" class="hidden mt-6 border-t pt-4">
            <div class="space-y-4">
              ${advancedLevels
                .map((level, index) =>
                  renderLevel(level, headers, savedState, { open: index === 0, accent: false })
                )
                .join('')}
            </div>
          </div>
        `
        : '';

      bodyEl.innerHTML = `
        <div class="space-y-4">
          ${renderLevel(firstLevel, headers, savedState, { open: true, accent: true })}
        </div>

        ${
          advancedLevels.length
            ? `
            <div class="mt-6 flex justify-between items-center border-t pt-4">
              <button
                id="toggle-advanced-btn"
                type="button"
                class="text-blue-600 hover:underline text-sm font-medium focus:outline-none"
                aria-expanded="false"
              >
                Advanced Options ➔
              </button>
              <button
                id="run-btn"
                type="button"
                class="bg-blue-600 text-white font-bold py-2 px-6 rounded-md hover:bg-blue-700"
              >
                Run
              </button>
            </div>
            ${advancedHtml}
          `
            : `
            <div class="mt-6 flex justify-end border-t pt-4">
              <button
                id="run-btn"
                type="button"
                class="bg-blue-600 text-white font-bold py-2 px-6 rounded-md hover:bg-blue-700"
              >
                Run
              </button>
            </div>
          `
        }
      `;

      if (modalContent) {
        modalContent.style.maxWidth = '720px';
      }

      bindLevelToggles(bodyEl);
      bindRandomEffectsBuilder(bodyEl, headers);
      bindInteractionBuilder(bodyEl, headers);
      bindChipsMultiselects(bodyEl);

      const advancedBtn = bodyEl.querySelector('#toggle-advanced-btn');
      const advancedSections = bodyEl.querySelector('#advanced-sections');

      if (advancedBtn && advancedSections) {
        advancedBtn.addEventListener('click', e => {
          e.preventDefault();
          const isHidden = advancedSections.classList.contains('hidden');

          if (isHidden) {
            advancedSections.classList.remove('hidden');
            advancedBtn.textContent = '⬅ Hide Advanced';
            advancedBtn.setAttribute('aria-expanded', 'true');
            if (modalContent) modalContent.style.maxWidth = '900px';
          } else {
            advancedSections.classList.add('hidden');
            advancedBtn.textContent = 'Advanced Options ➔';
            advancedBtn.setAttribute('aria-expanded', 'false');
            if (modalContent) modalContent.style.maxWidth = '720px';
          }
        });
      }

      updateConditionalFields(config);

    } else {
      const flatFields = config.fields || [];

      bodyEl.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          ${renderFieldsList(flatFields, headers, savedState)}
        </div>
        <div class="mt-6 flex justify-end border-t pt-4">
          <button
            id="run-btn"
            type="button"
            class="bg-blue-600 text-white font-bold py-2 px-6 rounded-md hover:bg-blue-700"
          >
            Run
          </button>
        </div>
      `;

      if (modalContent) {
        modalContent.style.maxWidth = '500px';
      }

      bindRandomEffectsBuilder(bodyEl, headers);
      bindInteractionBuilder(bodyEl, headers);
      updateConditionalFields(config);
    }

    const allFields = getAllFields(config);
    allFields.forEach(field => {
      if (!field.showIf) return;

      const controller = document.getElementById(field.showIf.field);
      if (!controller) return;

      controller.addEventListener('change', () => {
        updateConditionalFields(config);
      });
    });

    bindColumnValueFields(bodyEl, getColumnValues);
    bindPlotGallery(bodyEl);
    // Reflect the gallery's default selection in any showIf fields immediately.
    updateConditionalFields(config);

    bodyEl.querySelector('#run-btn').onclick = async () => {
      try {
        const payload = buildPayload(config);
        setDialogState(taskType, payload);

        recordAction({
          taskType,
          params: payload,
        });
        modalElement.style.display = 'none';
        await onRunTask(config, payload);
      } catch (error) {
        onError(error.message);
      }
    };

    modalElement.style.display = 'block';
  }

  function hide() {
    modalElement.style.display = 'none';
  }

  return { show, hide };
}

function sanitizeSavedStateForConfig(savedState, config, headers) {
  if (!savedState) return null;

  const result = {};
  const fields = getAllFields(config);

  fields.forEach(field => {
    const value = savedState[field.id];
    if (value === undefined) return;

    if (field.type === 'random_effects_builder') {
      if (Array.isArray(value)) {
        result[field.id] = value.map(re => ({
          ...re,
          groups: headers.includes(re.groups) ? re.groups : '',
          slopes: Array.isArray(re.slopes) ? re.slopes.filter(s => headers.includes(s)) : [],
          nested_in: re.nested_in && headers.includes(re.nested_in) ? re.nested_in : null,
        })).filter(re => re.groups);
      }
      return;
    }

    if (field.type === 'interaction_builder') {
      if (Array.isArray(value)) {
        result[field.id] = value
          .map(terms => Array.isArray(terms) ? terms.filter(t => headers.includes(t)) : [])
          .filter(terms => terms.length >= 2);
      }
      return;
    }

    if (field.type === 'select_headers') {
      if (field.multiple) {
        result[field.id] = Array.isArray(value)
          ? value.filter(v => headers.includes(v))
          : [];
      } else {
        result[field.id] = headers.includes(value) ? value : '';
      }
      return;
    }

    result[field.id] = value;
  });

  return result;
}