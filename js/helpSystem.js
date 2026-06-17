import { initHelpSystem, getHelpPage } from './api.js';

export function createHelpSystem({
  helpPanel,
  updateStatus,
}) {
  let helpStructure = [];
  let glossary = {};

  const titleEl = helpPanel.querySelector('#help-panel-title');
  const bodyEl = helpPanel.querySelector('#help-panel-body');
  const closeBtn = helpPanel.querySelector('#help-panel-close');

  if (closeBtn) {
    closeBtn.onclick = () => helpPanel.classList.remove('open');
  }

  async function load() {
    try {
      const data = await initHelpSystem();
      helpStructure = data.help_structure || [];
      glossary = data.glossary || {};
    } catch (error) {
      console.error('Help system initialization failed:', error);
      updateStatus('Could not initialize help system. Ensure backend is running.', true);
    }
  }

  function renderStructuredHelp(structure, container) {
    if (!structure || structure.length === 0) {
      container.innerHTML = '<p>No help topics available.</p>';
      return;
    }

    const renderTopic = (topic, path) => `
      <li>
        <a href="#" data-help-file="${topic.file}" class="text-blue-600 hover:underline">${topic.name}</a>
      </li>
    `;

    const renderSubCategory = (sub, path) => {
      const newPath = `${path} > ${sub.name}`;
      return `
        <li class="ml-4 mt-2">
          <details open>
            <summary class="font-semibold cursor-pointer list-none -ml-5 mb-1">${sub.name}</summary>
            <ul class="list-disc pl-5">
              ${sub.topics.map(topic => renderTopic(topic, newPath)).join('')}
            </ul>
          </details>
        </li>
      `;
    };

    const renderCategory = cat => {
      let content = '';
      const path = cat.category;

      if (cat.topics) {
        content += `<ul class="list-disc pl-5">${cat.topics.map(topic => renderTopic(topic, path)).join('')}</ul>`;
      }

      if (cat.subcategories) {
        content += `<ul>${cat.subcategories.map(sub => renderSubCategory(sub, path)).join('')}</ul>`;
      }

      return `
        <div class="mb-4">
          <h3 class="text-lg font-bold text-gray-700 border-b pb-1 mb-2">${cat.category}</h3>
          ${content}
        </div>
      `;
    };

    container.innerHTML = structure.map(renderCategory).join('');
    bindHelpTopicLinks(container);
  }

  function searchHelpTopics(query, structure) {
    const results = [];
    const lowerCaseQuery = query.toLowerCase();

    const search = (items, path) => {
      for (const item of items) {
        const currentItemName = item.name || item.category;
        const newPath = path ? `${path} > ${currentItemName}` : currentItemName;

        if (item.name && item.name.toLowerCase().includes(lowerCaseQuery)) {
          results.push({ ...item, path: path || 'Topic' });
        }

        if (item.topics) search(item.topics, newPath);
        if (item.subcategories) search(item.subcategories, newPath);
      }
    };

    search(structure, '');
    return results;
  }

  function renderFlatHelpResults(results, container) {
    if (results.length === 0) {
      container.innerHTML = '<p>No matching topics found.</p>';
      return;
    }

    let html = '<ul class="list-disc pl-5 space-y-2">';
    results.forEach(topic => {
      html += `
        <li>
          <a href="#" data-help-file="${topic.file}" class="text-blue-600 hover:underline">${topic.name}</a>
          <div class="text-xs text-gray-500">${topic.path}</div>
        </li>
      `;
    });
    html += '</ul>';

    container.innerHTML = html;
    bindHelpTopicLinks(container);
  }

  function bindHelpTopicLinks(container) {
    container.querySelectorAll('[data-help-file]').forEach(link => {
      link.addEventListener('click', async evt => {
        evt.preventDefault();
        await showPage(link.dataset.helpFile);
      });
    });
  }

  async function openSearch() {
    titleEl.textContent = 'Help Topics';
    bodyEl.innerHTML = `
      <input type="text" id="help-search-input" placeholder="Search for a topic..." class="w-full p-2 border rounded-md mb-4">
      <div id="help-results-container"></div>
    `;

    helpPanel.classList.add('open');

    const searchInput = document.getElementById('help-search-input');
    const resultsContainer = document.getElementById('help-results-container');

    renderStructuredHelp(helpStructure, resultsContainer);

    searchInput.addEventListener('input', e => {
      const query = e.target.value.toLowerCase().trim();

      if (query === '') {
        renderStructuredHelp(helpStructure, resultsContainer);
      } else {
        const flatResults = searchHelpTopics(query, helpStructure);
        renderFlatHelpResults(flatResults, resultsContainer);
      }
    });
  }

  async function showPage(pageName) {
    updateStatus(`Loading help for ${pageName}...`);
    try {
      const result = await getHelpPage(pageName);

      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = result.html_content;

      const h1 = tempDiv.querySelector('h1');
      if (h1) {
        titleEl.textContent = h1.textContent;
        h1.remove();
      } else {
        titleEl.textContent = `${pageName.replace(/_/g, ' ')} Help`;
      }

      bodyEl.innerHTML = tempDiv.innerHTML;
      helpPanel.classList.add('open');
      updateStatus('Help page loaded.');
    } catch (error) {
      updateStatus(`Error: ${error.message}`, true);
    }
  }

  return {
    load,
    openSearch,
    showPage,
    getGlossary: () => glossary,
    getStructure: () => helpStructure,
  };
}