document.addEventListener('DOMContentLoaded', () => {
  const permsNode = document.getElementById('excel-perms');
  const perms = {
    view: permsNode?.dataset.view === '1',
    create: permsNode?.dataset.create === '1',
    edit: permsNode?.dataset.edit === '1',
    remove: permsNode?.dataset.remove === '1',
    exportXlsx: permsNode?.dataset.exportXlsx === '1',
    manageColumns: permsNode?.dataset.manageColumns === '1',
  };
  const headRow = document.getElementById('excel-head-row');
  const body = document.getElementById('excel-body');
  const searchInput = document.getElementById('search-input');
  const pageSize = document.getElementById('page-size');
  const countEl = document.getElementById('records-count');
  const pageInfo = document.getElementById('page-info');
  const btnPrev = document.getElementById('btn-prev');
  const btnNext = document.getElementById('btn-next');
  const btnNew = document.getElementById('btn-new');
  const btnExport = document.getElementById('btn-export');
  const btnImport = document.getElementById('btn-import');
  const importFile = document.getElementById('import-file');
  const btnManageColumns = document.getElementById('btn-manage-columns');
  const columnToggleBtn = document.getElementById('column-toggle-btn');
  const columnMenu = document.getElementById('column-menu');

  const recordModalEl = document.getElementById('recordModal');
  const recordModal = recordModalEl ? new bootstrap.Modal(recordModalEl) : null;
  const recordForm = document.getElementById('record-form');
  const recordTitle = document.getElementById('record-modal-title');
  const btnSaveRecord = document.getElementById('save-record');

  const columnModalEl = document.getElementById('columnModal');
  const columnModal = columnModalEl ? new bootstrap.Modal(columnModalEl) : null;
  const btnSaveColumn = document.getElementById('save-column');

  let columns = [];
  let items = [];
  let currentPage = 1;
  let totalPages = 1;
  let editingId = null;
  let hiddenColumns = new Set();

  function storageKey() {
    return 'excel_module_hidden_columns';
  }

  function loadHiddenColumns() {
    try {
      const raw = localStorage.getItem(storageKey());
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      return new Set(Array.isArray(arr) ? arr : []);
    } catch {
      return new Set();
    }
  }

  function saveHiddenColumns() {
    try {
      localStorage.setItem(storageKey(), JSON.stringify(Array.from(hiddenColumns)));
    } catch {}
  }

  function escapeHtml(v) {
    return String(v ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function displayValue(col, rawVal) {
    if (rawVal === null || rawVal === undefined || String(rawVal).trim() === '') {
      return '<span class="cell-empty">-</span>';
    }
    // Strip time part from datetime strings (e.g. '2025-10-22 00:00:00' → '2025-10-22')
    if (col.data_type === 'date' || typeof rawVal === 'string') {
      const trimmed = String(rawVal).trim();
      const dateOnly = trimmed.replace(/\s+\d{2}:\d{2}:\d{2}(\.\d+)?$/, '');
      return escapeHtml(dateOnly);
    }
    return escapeHtml(rawVal);
  }

  async function apiFetch(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    const ct = (res.headers.get('content-type') || '').toLowerCase();
    const payload = ct.includes('application/json') ? await res.json() : null;
    if (!res.ok) {
      const msg = payload?.message || payload?.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return payload;
  }

  function renderHead() {
    const actionHeader = (perms.edit || perms.remove) ? '<th>Actions</th>' : '';
    headRow.innerHTML = columns
      .map(c => `<th data-col="${escapeHtml(c.key)}" class="${hiddenColumns.has(c.key) ? 'hidden-col' : ''}">${escapeHtml(c.label)}</th>`)
      .join('') + actionHeader;
    if (perms.edit || perms.remove) {
      const last = headRow.querySelector('th:last-child');
      if (last) last.setAttribute('data-col', '__actions');
    }
    renderColumnMenu();
  }

  function renderRows() {
    if (!items.length) {
      body.innerHTML = `<tr><td colspan="${columns.length + ((perms.edit || perms.remove) ? 1 : 0)}">Aucune donnée</td></tr>`;
      return;
    }

    body.innerHTML = items.map(it => {
      const tds = columns
        .map(c => {
          const raw = it[c.key];
          const display = displayValue(c, raw);
          const titleVal = (raw !== null && raw !== undefined && String(raw).trim() !== '') ? escapeHtml(String(raw).replace(/\s+\d{2}:\d{2}:\d{2}(\.\d+)?$/, '')) : '';
          return `<td data-col="${escapeHtml(c.key)}" class="${hiddenColumns.has(c.key) ? 'hidden-col' : ''}" title="${titleVal}">${display}</td>`;
        })
        .join('');
      let actions = '';
      if (perms.edit || perms.remove) {
        const editBtn = perms.edit ? `<button class="btn btn-outline-primary btn-sm btn-edit" data-id="${it.id}">Edit</button>` : '';
        const delBtn = perms.remove ? `<button class="btn btn-outline-danger btn-sm btn-delete" data-id="${it.id}">Delete</button>` : '';
        actions = `<td data-col="__actions" class="${hiddenColumns.has('__actions') ? 'hidden-col' : ''}"><div class="em-row-actions">${editBtn}${delBtn}</div></td>`;
      }
      return `<tr>${tds}${actions}</tr>`;
    }).join('');

    body.querySelectorAll('.btn-edit').forEach(btn => {
      btn.addEventListener('click', () => openRecordModal(Number(btn.dataset.id)));
    });
    body.querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', () => deleteRecord(Number(btn.dataset.id)));
    });
  }

  function buildForm(record = {}) {
    if (!recordForm) return;
    recordForm.innerHTML = columns.map(c => {
      const val = record[c.key] ?? '';
      const inputType = c.data_type === 'date' ? 'date' : (c.data_type === 'number' ? 'number' : 'text');
      return `
        <div class="col-12 col-md-6 col-lg-4">
          <label class="form-label">${escapeHtml(c.label)}</label>
          <input type="${inputType}" class="form-control form-control-sm" data-key="${escapeHtml(c.key)}" value="${escapeHtml(val)}">
        </div>
      `;
    }).join('');
  }

  function collectPayload() {
    const payload = { extra: {} };
    recordForm.querySelectorAll('input[data-key]').forEach(input => {
      const key = input.dataset.key;
      const col = columns.find(c => c.key === key);
      if (!col) return;
      const value = input.value;
      if (col.is_default) payload[key] = value;
      else payload.extra[key] = value;
    });
    return payload;
  }

  async function loadColumns() {
    columns = await apiFetch('/api/excel-module/columns');
    hiddenColumns = loadHiddenColumns();
    renderHead();
  }

  function setColumnVisible(key, visible) {
    if (!key) return;
    if (visible) hiddenColumns.delete(key);
    else hiddenColumns.add(key);
    saveHiddenColumns();
    document.querySelectorAll(`[data-col="${CSS.escape(key)}"]`).forEach(el => {
      el.classList.toggle('hidden-col', !visible);
    });
  }

  function renderColumnMenu() {
    if (!columnMenu) return;
    const actionItem = (perms.edit || perms.remove)
      ? [{ key: '__actions', label: 'Actions' }]
      : [];
    const allCols = [...columns.map(c => ({ key: c.key, label: c.label })), ...actionItem];
    columnMenu.innerHTML = allCols.map(col => {
      const checked = !hiddenColumns.has(col.key) ? 'checked' : '';
      return `<label class="em-col-item"><input type="checkbox" data-col-toggle="${escapeHtml(col.key)}" ${checked}><span>${escapeHtml(col.label)}</span></label>`;
    }).join('');

    columnMenu.querySelectorAll('input[data-col-toggle]').forEach(input => {
      input.addEventListener('change', () => {
        setColumnVisible(input.dataset.colToggle, input.checked);
      });
    });
  }

  async function loadRecords() {
    const q = encodeURIComponent(searchInput?.value?.trim() || '');
    const rawSize = Number(pageSize?.value ?? 100);
    const size = rawSize === 0 ? 10000 : (rawSize || 100);
    const data = await apiFetch(`/api/excel-module/records?page=${currentPage}&per_page=${size}&q=${q}`);
    items = data.items || [];
    totalPages = Math.max(1, data.pages || 1);
    if (currentPage > totalPages) currentPage = totalPages;
    pageInfo.textContent = `Page ${currentPage}/${totalPages}`;
    const total = Number(data.total || 0);
    countEl.textContent = `Nbr ligne affiché sur la page: ${items.length} / ${total}`;
    renderRows();
  }

  async function refreshAll() {
    try {
      await loadColumns();
      await loadRecords();
    } catch (e) {
      body.innerHTML = `<tr><td colspan="1">Erreur: ${escapeHtml(e.message)}</td></tr>`;
    }
  }

  function openRecordModal(id = null) {
    editingId = id;
    const rec = id ? items.find(x => x.id === id) : {};
    recordTitle.textContent = id ? 'Modifier enregistrement' : 'Nouveau enregistrement';
    buildForm(rec || {});
    recordModal?.show();
  }

  async function saveRecord() {
    const payload = collectPayload();
    try {
      if (editingId) {
        await apiFetch(`/api/excel-module/records/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch('/api/excel-module/records', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }
      recordModal?.hide();
      await loadRecords();
    } catch (e) {
      alert(`Erreur: ${e.message}`);
    }
  }

  async function deleteRecord(id) {
    if (!confirm('Confirmer la suppression ?')) return;
    try {
      await apiFetch(`/api/excel-module/records/${id}`, { method: 'DELETE' });
      await loadRecords();
    } catch (e) {
      alert(`Erreur: ${e.message}`);
    }
  }

  async function createColumn() {
    const label = document.getElementById('new-col-label')?.value?.trim() || '';
    const key = document.getElementById('new-col-key')?.value?.trim() || '';
    const data_type = document.getElementById('new-col-type')?.value || 'text';
    if (!label) {
      alert('Libellé obligatoire');
      return;
    }
    try {
      await apiFetch('/api/excel-module/columns', {
        method: 'POST',
        body: JSON.stringify({ label, key, data_type })
      });
      columnModal?.hide();
      await refreshAll();
    } catch (e) {
      alert(`Erreur: ${e.message}`);
    }
  }

  searchInput?.addEventListener('input', async () => {
    currentPage = 1;
    await loadRecords();
  });

  pageSize?.addEventListener('change', async () => {
    currentPage = 1;
    await loadRecords();
  });

  btnPrev?.addEventListener('click', async () => {
    if (currentPage <= 1) return;
    currentPage -= 1;
    await loadRecords();
  });

  btnNext?.addEventListener('click', async () => {
    if (currentPage >= totalPages) return;
    currentPage += 1;
    await loadRecords();
  });

  btnNew?.addEventListener('click', () => openRecordModal(null));
  btnSaveRecord?.addEventListener('click', saveRecord);

  btnManageColumns?.addEventListener('click', () => columnModal?.show());
  btnSaveColumn?.addEventListener('click', createColumn);

  btnExport?.addEventListener('click', () => {
    const q = encodeURIComponent(searchInput?.value?.trim() || '');
    window.location = `/api/excel-module/records/export.xlsx?q=${q}`;
  });

  btnImport?.addEventListener('click', () => {
    importFile?.click();
  });

  columnToggleBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    columnMenu?.classList.toggle('visible');
  });

  document.addEventListener('click', (e) => {
    if (!columnMenu || !columnToggleBtn) return;
    if (columnMenu.contains(e.target) || columnToggleBtn.contains(e.target)) return;
    columnMenu.classList.remove('visible');
  });

  importFile?.addEventListener('change', async () => {
    const file = importFile.files && importFile.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/api/excel-module/import.xlsx', { method: 'POST', body: formData });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload?.message || payload?.error || `HTTP ${res.status}`);
      const skipped = payload.skipped || 0;
      const msg = skipped > 0
        ? `Import terminé: ${payload.imported || 0} ligne(s) ajoutée(s), ${skipped} doublon(s) ignoré(s) (REF déjà existant).`
        : `Import terminé: ${payload.imported || 0} ligne(s) ajoutée(s).`;
      alert(msg);
      await refreshAll();
    } catch (e) {
      alert(`Erreur import: ${e.message}`);
    } finally {
      importFile.value = '';
    }
  });

  refreshAll();
});
