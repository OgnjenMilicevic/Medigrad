export function createReportModal({
  modalElement,
  onDownloadReport,
  getPlotConfig,
}) {
  // Shared export config (SVG default + high-res PNG). Fallback keeps the modal
  // working standalone if the host didn't pass one.
  const plotConfig = (opts) =>
    (typeof getPlotConfig === 'function' ? getPlotConfig(opts) : { responsive: true });
  const titleEl = modalElement.querySelector('#report-modal-title');
  const bodyEl = modalElement.querySelector('#report-modal-body');
  const closeBtn = modalElement.querySelector('.close-button');

  let lastReportData = null;
  let unrenderedPlotlyData = {};

  if (closeBtn) {
    closeBtn.onclick = () => {
      modalElement.style.display = 'none';
    };
  }

  function hide() {
    modalElement.style.display = 'none';
  }

  function show() {
    modalElement.style.display = 'block';
  }

  function getLastReportData() {
    return lastReportData;
  }

  function setTitle(title) {
    titleEl.textContent = title;
  }

  function renderTable(title, data) {
    if (!data || !data.data || data.data.length === 0) return '';

    let table = `<h3 class="font-bold text-lg mt-4">${title}</h3><table class="report-table"><thead><tr>`;
    data.headers.forEach(h => {
      table += `<th>${h}</th>`;
    });
    table += '</tr></thead><tbody>';

    data.data.forEach(row => {
      table += '<tr>';
      row.forEach(cell => {
        table += `<td>${cell === null ? '' : cell}</td>`;
      });
      table += '</tr>';
    });

    table += '</tbody></table>';
    return table;
  }

  function openTab(evt, tabName) {
    const modal = evt.target.closest('.modal-content');
    const tabcontent = modal.getElementsByClassName('tab-content');
    const tablinks = modal.getElementsByClassName('tab-button');

    for (let i = 0; i < tabcontent.length; i++) {
      tabcontent[i].style.display = 'none';
      tabcontent[i].classList.remove('active');
    }

    for (let i = 0; i < tablinks.length; i++) {
      tablinks[i].className = tablinks[i].className.replace(' active', '');
    }

    const activeTab = document.getElementById(tabName);
    if (activeTab) {
      activeTab.style.display = 'block';
      activeTab.classList.add('active');
    }

    // Render Plotly chart on demand when tab opens ---
    const plotContainer = activeTab.querySelector('.plotly-chart-container');
    if (plotContainer && !plotContainer.hasAttribute('data-rendered')) {
        const figData = unrenderedPlotlyData[plotContainer.id];
        if (figData && typeof Plotly !== 'undefined') {
            Plotly.newPlot(plotContainer.id, figData.data, figData.layout, plotConfig());
            plotContainer.setAttribute('data-rendered', 'true');
        }
    }

    evt.currentTarget.className += ' active';
  }

  function bindTabHandlers() {
    bodyEl.querySelectorAll('.tab-button[data-tab-target]').forEach(btn => {
      btn.addEventListener('click', evt => {
        openTab(evt, btn.dataset.tabTarget);
      });
    });
  }

  function bindDownloadHandler() {
    const btn = bodyEl.querySelector('#download-report-btn');
    if (!btn) return;

    btn.onclick = async () => {
      if (!lastReportData) {
        alert('No report data to download.');
        return;
      }
      await onDownloadReport(lastReportData, titleEl.textContent);
    };
  }

  function displayReport(title, results) {
    setTitle(title);
    let html = '';
    unrenderedPlotlyData = {}; // Reset plot data store
    const regFigData = {};     // containerId -> figure dict (regression branch: forest + ROC)
    const diagFigData = {};    // containerId -> diagnostic panel figure (rendered lazily on <details> open)

    const hasTables = results.tables && Object.keys(results.tables).length > 0;
    const hasPlots = results.plotly_figures && Object.keys(results.plotly_figures).length > 0;
    let tabNames = [];

    if (hasTables || hasPlots) {
      lastReportData = results.tables || {};

      // Order tabs: Plots first, then Tables
      if (hasPlots) tabNames.push(...Object.keys(results.plotly_figures));
      if (hasTables) tabNames.push(...Object.keys(results.tables));

      let tabButtons = '<div class="tab-container">';
      let tabContents = '<div class="tab-content-wrapper">';

      tabNames.forEach((name, index) => {
        const isActive = index === 0 ? 'active' : '';
        const cleanId = name.replace(/[^a-zA-Z0-9]/g, '') + index;

        tabButtons += `
          <button class="tab-button ${isActive}" data-tab-target="${cleanId}">
            ${name}
          </button>
        `;

        let contentHtml = '';
        if (hasPlots && results.plotly_figures[name]) {
            // It's a plot: Create container and store data for openTab()
            const containerId = `plotly-container-${cleanId}`;
            unrenderedPlotlyData[containerId] = results.plotly_figures[name];
            contentHtml = `<div id="${containerId}" class="plotly-chart-container" style="width:100%; height:550px;"></div>`;
        } else {
            // It's a table
            contentHtml = renderTable('', results.tables[name]);
        }

        tabContents += `
          <div id="${cleanId}" class="tab-content ${isActive}" style="${index === 0 ? 'display:block;' : 'display:none;'}">
            ${contentHtml}
          </div>
        `;
      });

      tabButtons += '</div>';
      tabContents += '</div>';

      const downloadButton = hasTables ? `
        <div>
          <button id="download-report-btn" class="bg-green-600 text-white font-bold py-2 px-4 rounded-md hover:bg-green-700 text-sm">
            Download as XLSX
          </button>
        </div>
      ` : '<div></div>';

      html = `<div class="report-header">${tabButtons}${downloadButton}</div>${tabContents}`;

      // Render optional note banner (used by correlation, etc.)
      if (results.note) {
        html = `<div class="bg-blue-50 border-l-4 border-blue-400 text-blue-800 text-sm px-4 py-2 mb-3">${results.note}</div>` + html;
      }
    } else if (results.regression_results) {
      // Per-model: optional warning + quality log, then the forest plot
      // (built server-side from coefficient data), then the text summary.
      lastReportData = null;
      if (results.regression_results.length > 0) {
        results.regression_results.forEach((res, i) => {
          if (res.outcome_name) html += `<h3 class="font-bold text-lg mt-6 pt-2 border-t border-gray-200">${res.outcome_name}</h3>`;
          if (res.has_warning) html += `<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mt-4 mb-2"><strong>⚠️ Warning:</strong> ${res.warning_text}</div>`;
          if (res.quality_log && res.quality_log.length > 0) html += `<div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mt-4 mb-2 shadow-sm"><h3 class="text-sm font-bold text-yellow-800">Data Quality Adjustments (Pre-Analysis)</h3><ul class="mt-2 text-sm text-yellow-700 list-disc pl-5 space-y-1">${res.quality_log.map(log => `<li>${log}</li>`).join('')}</ul></div>`;
          if (res.forest_figure) {
            const containerId = `regforest-${i}`;
            regFigData[containerId] = res.forest_figure;
            html += `<div id="${containerId}" class="regression-forest" style="width:100%;"></div>`;
          }
          if (res.roc_figure) {
            const containerId = `regroc-${i}`;
            regFigData[containerId] = res.roc_figure;
            html += `<div id="${containerId}" class="regression-roc" style="width:100%;"></div>`;
          }
          if (res.diagnostic_figure) {
            // Tall 4-panel figure — collapsed by default, rendered on expand.
            const containerId = `regdiag-${i}`;
            diagFigData[containerId] = res.diagnostic_figure;
            html += `<details class="regression-diagnostics mt-2" data-diag-container="${containerId}"><summary class="cursor-pointer text-sm font-semibold text-blue-700 py-1">Regression diagnostics (residuals, Q–Q, scale–location, leverage)</summary><div id="${containerId}" style="width:100%;"></div></details>`;
          }
          html += `<pre class="bg-gray-100 p-2 rounded-md mt-2 text-sm">${res.model_summary || JSON.stringify(res, null, 2)}</pre>`;
        });
      } else {
        html = '<p>No regression results.</p>';
      }
    } else {
      lastReportData = null;
      html = '<p>No report content available.</p>';
    }

    bodyEl.innerHTML = html;
    show();
    bindTabHandlers();
    bindDownloadHandler();

    // Regression figures (forest + ROC) are not tabbed — render each now. A
    // slight delay lets the modal compute its width before Plotly draws.
    Object.entries(regFigData).forEach(([containerId, figData]) => {
      setTimeout(() => {
        if (typeof Plotly !== 'undefined' && document.getElementById(containerId)) {
          Plotly.newPlot(containerId, figData.data, figData.layout, plotConfig());
        }
      }, 50);
    });

    // Diagnostic panels are collapsed by default; render on first expand so the
    // tall figure costs nothing for users who don't open it.
    bodyEl.querySelectorAll('details[data-diag-container]').forEach(det => {
      det.addEventListener('toggle', () => {
        if (!det.open) return;
        const containerId = det.dataset.diagContainer;
        const el = document.getElementById(containerId);
        const figData = diagFigData[containerId];
        if (el && figData && !el.hasAttribute('data-rendered') && typeof Plotly !== 'undefined') {
          Plotly.newPlot(containerId, figData.data, figData.layout, plotConfig());
          el.setAttribute('data-rendered', 'true');
        }
      });
    });

    // Trigger immediate render if the first default tab is a Plotly chart
    const firstTabName = tabNames[0];
    if (firstTabName && hasPlots && results.plotly_figures[firstTabName]) {
        const cleanId = firstTabName.replace(/[^a-zA-Z0-9]/g, '') + '0';
        const containerId = `plotly-container-${cleanId}`;
        const figData = unrenderedPlotlyData[containerId];
        // Wait 50ms so the browser can calculate the modal's width/height before Plotly draws
        setTimeout(() => {
            if (typeof Plotly !== 'undefined') {
                Plotly.newPlot(containerId, figData.data, figData.layout, plotConfig());
                document.getElementById(containerId).setAttribute('data-rendered', 'true');
            }
        }, 50);
    }
  }

  function displayNumericalQCReport(report, currentHeaders, hot) {
    setTitle('Numerical Quality Control Report');

    let html = '';
    const cellMeta = [];

    html += '<h3 class="font-bold text-lg mt-4">Outlier Summary</h3>';

    if (report.outlier_summary && Object.keys(report.outlier_summary.by_column).length > 0) {
      html += '<h4>By Column:</h4><ul>';

      Object.entries(report.outlier_summary.by_column).forEach(([colName, info]) => {
        html += `<li><strong>${colName}:</strong> ${info.count} outliers found.</li>`;
        const colIndex = currentHeaders.indexOf(colName);

        if (colIndex !== -1) {
          info.indices.forEach(r => {
            cellMeta.push({ row: r, col: colIndex, className: 'outlier' });
          });
        }
      });

      html += '</ul>';
    }

    if (report.outlier_summary && report.outlier_summary.rows_with_outlier_counts.length > 0) {
      html += '<h4>Rows with High Number of Outliers:</h4><ul>';
      report.outlier_summary.rows_with_outlier_counts.forEach(([row, count]) => {
        html += `<li><strong>Row ${row + 1}:</strong> ${count} outliers</li>`;
      });
      html += '</ul>';
    }

    html += '<h3 class="font-bold text-lg mt-4">Constant Increment Patterns</h3>';

    if (report.constant_increment_patterns && Object.keys(report.constant_increment_patterns).length > 0) {
      html += '<ul>';

      Object.entries(report.constant_increment_patterns).forEach(([colName, patterns]) => {
        const colIndex = currentHeaders.indexOf(colName);

        patterns.forEach(p => {
          html += `<li><strong>${colName}:</strong> Pattern found from row ${p[0] + 1} to ${p[1] + 1} with an increment of ${p[2]}.</li>`;
          if (colIndex !== -1) {
            for (let r = p[0]; r <= p[1]; r++) {
              cellMeta.push({ row: r, col: colIndex, className: 'pattern' });
            }
          }
        });
      });

      html += '</ul>';
    } else {
      html += '<p>No patterns found.</p>';
    }

    if (hot) {
      hot.updateSettings({ cell: cellMeta });
    }

    bodyEl.innerHTML = html;
    show();
  }

  return {
    show,
    hide,
    displayReport,
    displayNumericalQCReport,
    getLastReportData,
  };
}