(() => {
  const state = {
    conversations: [],
    currentId: null,
    currentCallerNumber: null,
    callerNames: {},
    // Persisted follow-ups from the tasks table (/api/action-items).
    actionItems: [],
    showDoneActionItems: false,
  };

  // ---------- helpers ----------

  function parseTimestamp(iso) {
    if (!iso) return null;
    // Python's datetime.isoformat() emits 6-digit microseconds; JS Date only
    // understands up to milliseconds, so trim before parsing.
    const trimmed = iso.replace(/(\.\d{3})\d*$/, '$1');
    const d = new Date(trimmed);
    return isNaN(d.getTime()) ? null : d;
  }

  function formatTimestamp(iso) {
    const d = parseTimestamp(iso);
    if (!d) return '—';
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  function formatDuration(seconds) {
    seconds = Number(seconds) || 0;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function formatPhone(num) {
    const digits = (num || '').replace(/\D/g, '');
    const d = digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits;
    if (d.length === 10) {
      return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
    }
    return num || 'Unknown';
  }

  function formatCallerLabel(callerNumber) {
    return state.callerNames[callerNumber] || formatPhone(callerNumber);
  }

  function formatCallerCell(callerNumber) {
    const name = state.callerNames[callerNumber];
    if (!name) return escapeHtml(formatPhone(callerNumber));
    return `<span class="caller-name">${escapeHtml(name)}</span><span class="caller-phone-sub">${escapeHtml(formatPhone(callerNumber))}</span>`;
  }

  function renderTopicChips(topics) {
    if (!topics || !topics.length) return '<span class="topic-chip topic-chip-empty">—</span>';
    return topics.map((t) => `<span class="topic-chip">${escapeHtml(t)}</span>`).join('');
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  // ---------- clock ----------

  function tickClock() {
    const el = document.getElementById('clock');
    el.textContent = new Date().toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', second: '2-digit',
    });
  }

  // ---------- nav ----------

  function setupNav() {
    document.querySelectorAll('.nav-item').forEach((btn) => {
      // The Live item is a plain link (opens /live in a new tab) with no
      // data-view — let it navigate normally instead of view-switching.
      if (!btn.dataset.view) return;
      btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
        if (btn.dataset.view === 'clients') loadClientsView();
      });
    });
  }

  // ---------- stat tiles ----------

  function renderStatTiles() {
    const convos = state.conversations;
    const total = convos.length;
    const uniqueCallers = new Set(convos.map((c) => c.caller_number)).size;
    const avgDuration = total
      ? Math.round(convos.reduce((sum, c) => sum + (c.duration_seconds || 0), 0) / total)
      : 0;
    const needsFollowUp = state.actionItems.filter((t) => t.status === 'open').length;

    const tiles = [
      { label: 'Total calls', value: total },
      { label: 'Unique callers', value: uniqueCallers },
      { label: 'Avg call length', value: formatDuration(avgDuration) },
      { label: 'Needs follow-up', value: needsFollowUp, warn: needsFollowUp > 0 },
    ];

    document.getElementById('stat-tiles').innerHTML = tiles.map((t) => `
      <div class="stat-tile">
        <div class="stat-label">${t.label}</div>
        <div class="stat-value${t.warn ? ' warn' : ''}">${t.value}</div>
      </div>
    `).join('');
  }

  // ---------- calls table ----------

  function renderTable(rows) {
    const tbody = document.getElementById('calls-tbody');
    const empty = document.getElementById('calls-empty');
    if (!rows.length) {
      tbody.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    // Each td carries a stable class + data-label. Below 860px the table
    // becomes a CSS-only card list (see dashboard.css) — this is the same
    // markup either way, not a second render path, so the rerun button and
    // the row-click handler can't drift out of sync between layouts.
    tbody.innerHTML = rows.map((c) => `
      <tr data-id="${escapeHtml(c.id)}">
        <td class="num time" data-label="Time">${formatTimestamp(c.start_time)}</td>
        <td class="caller">${formatCallerCell(c.caller_number)}</td>
        <td class="num dur" data-label="Duration">${formatDuration(c.duration_seconds)}</td>
        <td class="topics">${renderTopicChips(c.topics)}</td>
        <td class="actions">
          <button type="button" class="btn-icon rerun-btn" title="Re-run extraction on this call" aria-label="Re-run extraction on this call">⟳</button>
          <button type="button" class="btn-icon delete-call-btn" title="Delete this call" aria-label="Delete this call">🗑</button>
        </td>
      </tr>
    `).join('');
  }

  // POST /api/conversations/{call_id}/reextract re-runs post_call_extraction.py
  // against the stored transcript and saves the result (see dashboard.py's
  // api_reextract_conversation) — the same extraction a live call gets once,
  // right after it ends, run again on demand.
  async function rerunExtraction(btn, callId) {
    if (btn.classList.contains('spinning')) return;
    btn.classList.add('spinning');
    try {
      await fetchJSON(`/api/conversations/${encodeURIComponent(callId)}/reextract`, {
        method: 'POST',
      });
      await loadConversations();
      if (state.currentId === callId) await loadDrawerContent(callId);
      showToast(`Re-ran extraction for ${callId}`);
    } catch (err) {
      showToast(`Couldn't re-run extraction: ${err.message}`);
    } finally {
      btn.classList.remove('spinning');
    }
  }

  async function deleteCallRow(callId) {
    if (!confirm(`Delete call ${callId}? This permanently removes its transcript, summary, and any follow-up tasks.`)) return;
    try {
      await fetchJSON(`/api/conversations/${encodeURIComponent(callId)}`, { method: 'DELETE' });
      if (state.currentId === callId) closeDrawer();
      await loadConversations();
      showToast(`Deleted call ${callId}`);
    } catch (err) {
      showToast(`Couldn't delete call: ${err.message}`);
    }
  }

  function setupCallsTable() {
    // One delegated listener, bound once — renderTable() replaces every row
    // on each render, so per-row listeners would need re-binding anyway.
    document.getElementById('calls-tbody').addEventListener('click', (e) => {
      const rerun = e.target.closest('.rerun-btn');
      if (rerun) {
        e.stopPropagation();
        rerunExtraction(rerun, rerun.closest('tr').dataset.id);
        return;
      }
      const del = e.target.closest('.delete-call-btn');
      if (del) {
        e.stopPropagation();
        deleteCallRow(del.closest('tr').dataset.id);
        return;
      }
      const tr = e.target.closest('tr');
      if (tr) openDrawer(tr.dataset.id);
    });
  }

  function applyFilters() {
    const filters = {};
    document.querySelectorAll('.filter-row input').forEach((inp) => {
      filters[inp.dataset.filter] = inp.value.trim().toLowerCase();
    });
    // Mobile-only search box — the filter row above is hidden once the table
    // becomes a card list, so this is the phone entry point for the same
    // filtering, matched against one combined haystack.
    const q = (document.getElementById('calls-search').value || '').trim().toLowerCase();

    const filtered = state.conversations.filter((c) => {
      if (filters.time && !formatTimestamp(c.start_time).toLowerCase().includes(filters.time)) return false;
      if (filters.caller_number) {
        const hay = `${formatPhone(c.caller_number)} ${c.caller_number} ${state.callerNames[c.caller_number] || ''}`.toLowerCase();
        if (!hay.includes(filters.caller_number)) return false;
      }
      if (filters.duration_seconds && c.duration_seconds < Number(filters.duration_seconds)) return false;
      if (filters.topics && !(c.topics || []).join(' ').toLowerCase().includes(filters.topics)) return false;
      if (q) {
        const hay = [
          formatTimestamp(c.start_time),
          formatPhone(c.caller_number),
          c.caller_number,
          state.callerNames[c.caller_number] || '',
          (c.topics || []).join(' '),
        ].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    renderTable(filtered);
  }

  function setupFilters() {
    document.querySelectorAll('.filter-row input').forEach((inp) => {
      inp.addEventListener('input', applyFilters);
    });
    document.getElementById('calls-search').addEventListener('input', applyFilters);
  }

  async function loadConversations() {
    // Three requests in parallel, never one per conversation. This used to fire
    // 31 requests (~19s of blank page) before rendering anything.
    const [convos, names, actionItems] = await Promise.all([
      fetchJSON('/api/conversations'),
      fetchJSON('/api/callers/names'),
      fetchJSON('/api/action-items'),
    ]);
    state.conversations = convos;
    state.callerNames = names;
    state.actionItems = actionItems;

    renderStatTiles();
    renderTable(convos);
    renderActionItems();
  }

  // ---------- action items (persisted tasks, inside the Calls tab) ----------

  // The caller's saved name wins over whatever the extraction guessed, so
  // renaming in the Clients tab shows up here on the next render.
  function actionItemCallerLabel(item) {
    return state.callerNames[item.caller_number]
      || item.caller_name
      || formatPhone(item.caller_number);
  }

  function actionItemCardHtml(item) {
    const done = item.status === 'done';
    const urgent = item.urgency === 'High' || item.urgency === 'Emergency';
    const scheduled = !!item.scheduled_at;
    // is_appointment and suggested_datetime come straight from the
    // extraction LLM's own read of this item (see post_call_extraction.py) —
    // no keyword/regex classification after the fact. A call that ended
    // with "we'll call back to confirm a time" has is_appointment true but
    // no suggested_datetime, so it correctly gets no button yet — there's
    // nothing to schedule until a date is actually known. Once something is
    // actually scheduled, always show the button regardless, so a human
    // correction can never lose its Reschedule entry point.
    const showSchedule = scheduled || (item.is_appointment && !!item.suggested_datetime);

    return `
      <article class="action-item-card${done ? ' done' : ''}"
               data-task-id="${escapeHtml(item.id)}"
               data-call-id="${escapeHtml(item.call_id)}">
        <header class="ai-head">
          <div class="ai-who">
            <span class="ai-caller">${escapeHtml(actionItemCallerLabel(item))}</span>
            <span class="ai-phone">${escapeHtml(formatPhone(item.caller_number))}</span>
          </div>
          <button type="button" class="btn-icon ai-close"
                  aria-label="${done ? 'Reopen this action item' : 'Mark done'}"
                  title="${done ? 'Reopen' : 'Mark done'}">${done ? '↺' : '✓'}</button>
        </header>

        <p class="ai-task">${escapeHtml(item.description)}</p>

        <div class="ai-meta">
          <span class="pill pill-accent">${escapeHtml(item.call_id)}</span>
          <span class="ai-time">${formatTimestamp(item.call_time || item.created_at)}</span>
          ${urgent ? `<span class="pill pill-critical">${escapeHtml(item.urgency)}</span>` : ''}
          ${scheduled ? `<span class="pill pill-roof">📅 ${escapeHtml(formatScheduleLabel(item.scheduled_at))}${item.has_calendar_event ? ' · on calendar' : ''}</span>` : ''}
          ${done ? '<span class="pill pill-good">Done</span>' : ''}
        </div>

        <div class="ai-actions">
          <button type="button" class="btn btn-ghost btn-sm ai-open">Open call</button>
          ${showSchedule && !done
            ? `<button type="button" class="btn btn-primary btn-sm ai-schedule">📅 ${scheduled ? 'Reschedule' : 'Schedule'}</button>`
            : ''}
        </div>
      </article>
    `;
  }

  function renderActionItems() {
    const items = state.actionItems;
    const open = items.filter((t) => t.status === 'open');
    const doneCount = items.length - open.length;
    const visible = state.showDoneActionItems ? items : open;

    document.getElementById('action-items-count').textContent =
      open.length ? `(${open.length})` : '';

    const toggle = document.getElementById('action-items-done-toggle');
    if (toggle) {
      toggle.hidden = doneCount === 0;
      toggle.textContent = state.showDoneActionItems
        ? `Hide done (${doneCount})`
        : `Show done (${doneCount})`;
    }

    const list = document.getElementById('action-items-list');
    const empty = document.getElementById('action-items-empty');
    if (!visible.length) {
      list.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    list.innerHTML = visible.map(actionItemCardHtml).join('');
  }

  async function setActionItemStatus(taskId, status, card) {
    if (card && status === 'done') card.classList.add('closing');
    try {
      const updated = await fetchJSON(`/api/action-items/${encodeURIComponent(taskId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      const i = state.actionItems.findIndex((t) => t.id === taskId);
      if (i > -1) state.actionItems[i] = updated;
      renderActionItems();
      renderStatTiles();
      if (status === 'done') {
        showToast('Marked done', 'Undo', () => setActionItemStatus(taskId, 'open'));
      }
      // Keep the drawer's To-Do pane in step if it's showing the same call.
      if (state.currentId && state.currentId === updated.call_id) {
        renderDrawerTodos(state.actionItems.filter((t) => t.call_id === state.currentId));
      }
    } catch (err) {
      if (card) card.classList.remove('closing');
      showToast(`Couldn't update: ${err.message}`);
    }
  }

  function setupActionItems() {
    document.getElementById('action-items-toggle').addEventListener('click', () => {
      document.querySelector('.action-items-card').classList.toggle('collapsed');
    });

    const doneToggle = document.getElementById('action-items-done-toggle');
    doneToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      state.showDoneActionItems = !state.showDoneActionItems;
      renderActionItems();
    });

    // One delegated listener on the stable container, bound once. Cards are
    // re-rendered wholesale, so per-card listeners would need re-binding and
    // would fight with the buttons inside them.
    document.getElementById('action-items-list').addEventListener('click', (e) => {
      const card = e.target.closest('.action-item-card');
      if (!card) return;
      const taskId = card.dataset.taskId;

      if (e.target.closest('.ai-close')) {
        const item = state.actionItems.find((t) => t.id === taskId);
        return setActionItemStatus(taskId, item && item.status === 'done' ? 'open' : 'done', card);
      }
      if (e.target.closest('.ai-schedule')) return openScheduleSheet(taskId);
      openDrawer(card.dataset.callId);
    });
  }

  // ---------- schedule sheet ----------
  //
  // Saves for real: PATCH /api/action-items/{id} { scheduled_at }, which also
  // upserts a Google Calendar event when calendar_service.py is configured
  // (best-effort — scheduling still works without it, see has_calendar_event).

  let scheduleTaskId = null;

  function pad2(n) { return String(n).padStart(2, '0'); }

  function toDateValue(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

  function formatScheduleLabel(value) {
    const d = parseTimestamp(value);
    if (!d) return value;
    return d.toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  }

  function applySchedulePreset(preset) {
    const now = new Date();
    const date = new Date(now);
    let time = '09:00';
    if (preset === 'today-pm') {
      time = '14:00';
    } else if (preset === 'tomorrow-am') {
      date.setDate(date.getDate() + 1);
      time = '09:00';
    } else if (preset === 'plus2') {
      date.setDate(date.getDate() + 2);
      time = '10:00';
    }
    document.getElementById('schedule-date').value = toDateValue(date);
    document.getElementById('schedule-time').value = time;
  }

  function openScheduleSheet(taskId) {
    const item = state.actionItems.find((t) => t.id === taskId);
    if (!item) return;
    scheduleTaskId = taskId;

    document.getElementById('schedule-sheet-task').textContent =
      `${actionItemCallerLabel(item)} · ${item.description}`;

    const noteEl = document.getElementById('schedule-detected-note');
    const clearBtn = document.getElementById('schedule-clear');

    if (item.scheduled_at) {
      // Already scheduled — edit the existing slot rather than re-guess one.
      const d = parseTimestamp(item.scheduled_at);
      document.getElementById('schedule-date').value = toDateValue(d);
      document.getElementById('schedule-time').value = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
      noteEl.hidden = true;
      clearBtn.hidden = false;
    } else {
      clearBtn.hidden = true;
      // suggested_datetime comes straight from the extraction LLM's own
      // read of this item (see post_call_extraction.py) — no client-side
      // date-parsing needed to prefill this.
      if (item.suggested_datetime) {
        const d = parseTimestamp(item.suggested_datetime);
        document.getElementById('schedule-date').value = toDateValue(d);
        document.getElementById('schedule-time').value = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
        noteEl.textContent = `📅 Detected from the call: ${formatScheduleLabel(item.suggested_datetime)}`;
        noteEl.hidden = false;
      } else {
        applySchedulePreset('tomorrow-am');
        noteEl.hidden = true;
      }
    }
    document.getElementById('schedule-note').value = '';

    document.getElementById('schedule-sheet').showModal();
  }

  async function saveSchedule(scheduledAt, durationMinutes, note) {
    try {
      const body = { scheduled_at: scheduledAt };
      // Only meaningful alongside a real scheduled_at — omitted on clear.
      if (scheduledAt) {
        body.duration_minutes = durationMinutes;
        if (note) body.note = note;
      }
      const updated = await fetchJSON(`/api/action-items/${encodeURIComponent(scheduleTaskId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const i = state.actionItems.findIndex((t) => t.id === scheduleTaskId);
      if (i > -1) state.actionItems[i] = updated;
      document.getElementById('schedule-sheet').close();
      renderActionItems();
      if (scheduledAt) {
        showToast(`Scheduled for ${formatScheduleLabel(updated.scheduled_at)}${updated.has_calendar_event ? ' · added to calendar' : ''}`);
      } else {
        showToast('Schedule cleared');
      }
    } catch (err) {
      showToast(`Couldn't save: ${err.message}`);
    }
  }

  function setupScheduleSheet() {
    const sheet = document.getElementById('schedule-sheet');

    const close = () => sheet.close();
    document.getElementById('schedule-close').addEventListener('click', close);
    document.getElementById('schedule-cancel').addEventListener('click', close);

    // Click the backdrop to dismiss.
    sheet.addEventListener('click', (e) => { if (e.target === sheet) close(); });

    document.getElementById('schedule-clear').addEventListener('click', () => {
      if (confirm('Clear this scheduled time?')) saveSchedule(null);
    });

    document.getElementById('schedule-save').addEventListener('click', () => {
      const date = document.getElementById('schedule-date').value;
      const time = document.getElementById('schedule-time').value;
      if (!date || !time) {
        showToast('Pick a date and time first');
        return;
      }
      const duration = Number(document.getElementById('schedule-duration').value) || 60;
      const note = document.getElementById('schedule-note').value.trim();
      saveSchedule(`${date}T${time}`, duration, note);
    });
  }

  // ---------- toast ----------

  let toastTimer = null;

  function showToast(text, actionLabel, onAction) {
    const host = document.getElementById('toast-host');
    host.innerHTML = `
      <div class="toast">
        <span>${escapeHtml(text)}</span>
        ${actionLabel ? `<button type="button" class="toast-action">${escapeHtml(actionLabel)}</button>` : ''}
      </div>
    `;
    const action = host.querySelector('.toast-action');
    if (action && onAction) {
      action.addEventListener('click', () => { host.innerHTML = ''; onAction(); });
    }
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { host.innerHTML = ''; }, 6000);
  }

  // ---------- drawer ----------

  function openDrawer(id) {
    state.currentId = id;
    document.getElementById('drawer-overlay').classList.add('open');
    document.getElementById('drawer').classList.add('open');
    document.getElementById('drawer').classList.remove('fullscreen');
    document.getElementById('caller-menu').hidden = true;
    document.getElementById('caller-edit-form').hidden = true;
    document.getElementById('note-input').value = '';
    setActiveTab('transcript');
    loadDrawerContent(id);
  }

  function closeDrawer() {
    document.getElementById('drawer-overlay').classList.remove('open');
    document.getElementById('drawer').classList.remove('open');
    state.currentId = null;
    state.currentCallerNumber = null;
  }

  function updateDrawerCallerDisplay() {
    const caller = state.currentCallerNumber;
    const name = state.callerNames[caller];
    document.getElementById('drawer-caller').textContent = name || formatPhone(caller);
    const phoneEl = document.getElementById('drawer-caller-phone');
    if (name) {
      phoneEl.textContent = formatPhone(caller);
      phoneEl.hidden = false;
    } else {
      phoneEl.hidden = true;
    }
  }

  async function saveCallerName() {
    const caller = state.currentCallerNumber;
    if (!caller) return;
    const name = document.getElementById('caller-edit-input').value.trim();
    state.callerNames = await fetchJSON(`/api/callers/${encodeURIComponent(caller)}/name`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    document.getElementById('caller-edit-form').hidden = true;
    updateDrawerCallerDisplay();
    applyFilters();
  }

  function setActiveTab(tab) {
    document.querySelectorAll('.drawer-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.drawer-pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${tab}`));
  }

  function setupDrawer() {
    document.getElementById('drawer-overlay').addEventListener('click', closeDrawer);
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    document.querySelectorAll('.drawer-tab').forEach((btn) => {
      btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
    });

    document.getElementById('drawer-expand').addEventListener('click', () => {
      document.getElementById('drawer').classList.toggle('fullscreen');
    });

    document.getElementById('caller-menu-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      const menu = document.getElementById('caller-menu');
      menu.hidden = !menu.hidden;
    });

    document.addEventListener('click', (e) => {
      const menu = document.getElementById('caller-menu');
      if (!menu.hidden && !e.target.closest('.caller-menu-wrap')) menu.hidden = true;
    });

    document.getElementById('caller-menu-edit').addEventListener('click', () => {
      document.getElementById('caller-menu').hidden = true;
      const form = document.getElementById('caller-edit-form');
      const input = document.getElementById('caller-edit-input');
      input.value = state.callerNames[state.currentCallerNumber] || '';
      form.hidden = false;
      input.focus();
    });

    document.getElementById('caller-menu-delete').addEventListener('click', async () => {
      document.getElementById('caller-menu').hidden = true;
      if (!state.currentId) return;
      if (!confirm(`Delete the entire transcript for call ${state.currentId}? This permanently removes every turn from the database.`)) return;

      await fetchJSON(`/api/conversations/${encodeURIComponent(state.currentId)}`, { method: 'DELETE' });
      closeDrawer();
      await loadConversations();
    });

    document.getElementById('caller-edit-cancel').addEventListener('click', () => {
      document.getElementById('caller-edit-form').hidden = true;
    });

    document.getElementById('caller-edit-save').addEventListener('click', saveCallerName);

    document.getElementById('caller-edit-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') saveCallerName();
      if (e.key === 'Escape') document.getElementById('caller-edit-form').hidden = true;
    });

    document.getElementById('note-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = document.getElementById('note-input');
      const text = input.value.trim();
      if (!text || !state.currentId) return;
      const notes = await fetchJSON(`/api/conversations/${encodeURIComponent(state.currentId)}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      input.value = '';
      renderNotes(notes);
    });

    document.getElementById('notes-list').addEventListener('click', async (e) => {
      const btn = e.target.closest('.note-delete');
      if (!btn || !state.currentId) return;
      const noteId = btn.closest('.note-item').dataset.id;
      const notes = await fetchJSON(
        `/api/conversations/${encodeURIComponent(state.currentId)}/notes/${encodeURIComponent(noteId)}`,
        { method: 'DELETE' }
      );
      renderNotes(notes);
    });

    // Close/reopen an action item from inside the drawer's To-Do pane.
    document.getElementById('pane-todos').addEventListener('click', (e) => {
      const btn = e.target.closest('.todo-check');
      if (!btn) return;
      const row = btn.closest('.todo-item');
      const taskId = row.dataset.taskId;
      const item = state.actionItems.find((t) => t.id === taskId);
      setActionItemStatus(taskId, item && item.status === 'done' ? 'open' : 'done');
    });
  }

  function notesListHtml(notes) {
    return notes.length
      ? notes.map((n) => `
          <div class="note-item" data-id="${escapeHtml(n.id)}">
            <div class="note-time">
              <span>${formatTimestamp(n.created_at)}</span>
              <button type="button" class="note-delete" title="Delete note">Delete</button>
            </div>
            <div>${escapeHtml(n.text)}</div>
          </div>
        `).join('')
      : '<p class="chat-hint">No notes yet — add one below.</p>';
  }

  function renderNotes(notes) {
    document.getElementById('notes-list').innerHTML = notesListHtml(notes);
  }

  function transcriptHtml(messages) {
    return messages.map((m) => `
      <div class="msg ${m.speaker}" data-msg-id="${escapeHtml(m.id || '')}">
        <div class="who">
          ${m.speaker === 'caller' ? 'Caller' : 'Assistant'} · ${formatTimestamp(m.timestamp)}
          ${m.id ? '<button type="button" class="msg-delete" title="Delete this turn">✕</button>' : ''}
        </div>
        <div class="bubble">${escapeHtml(m.text)}</div>
      </div>
    `).join('') || '<p class="chat-hint">No transcript recorded for this call.</p>';
  }

  // Delete one transcript turn. Delegated, so it covers both the drawer and
  // the clients-view transcript pane.
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.msg-delete');
    if (!btn) return;
    const msg = btn.closest('.msg');
    // The drawer and the clients view each track their own open conversation.
    const conversationId = msg?.closest('#pane-c')
      ? clientsState.selectedConversationId
      : state.currentId;
    if (!msg || !conversationId) return;
    if (!confirm('Delete this transcript turn? This removes it from the database.')) return;

    await fetchJSON(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(msg.dataset.msgId)}`,
      { method: 'DELETE' },
    );
    msg.remove();
    await loadConversations();
  });

  async function loadDrawerContent(id) {
    const conversation = await fetchJSON(`/api/conversations/${encodeURIComponent(id)}`);
    state.currentCallerNumber = conversation.caller_number;
    updateDrawerCallerDisplay();
    document.getElementById('drawer-time').textContent = formatTimestamp(conversation.start_time);

    document.getElementById('pane-transcript').innerHTML = transcriptHtml(conversation.messages);

    // Same source of truth as the cards, so closing an item in either place
    // can't disagree. (This used to render regex-derived todos whose checkbox
    // only toggled a CSS class and persisted nothing.)
    renderDrawerTodos(await fetchJSON(`/api/action-items?call_id=${encodeURIComponent(id)}`));

    const notes = await fetchJSON(`/api/conversations/${encodeURIComponent(id)}/notes`);
    renderNotes(notes);
  }

  function renderDrawerTodos(items) {
    const pane = document.getElementById('pane-todos');
    if (!items.length) {
      pane.innerHTML = '<p class="chat-hint">No action items for this call. They come from the AI\'s post-call extraction.</p>';
      return;
    }
    pane.innerHTML = items.map((item) => `
      <div class="todo-item${item.status === 'done' ? ' done' : ''}" data-task-id="${escapeHtml(item.id)}">
        <button type="button" class="btn-icon todo-check"
                aria-label="${item.status === 'done' ? 'Reopen' : 'Mark done'}"
                title="${item.status === 'done' ? 'Reopen' : 'Mark done'}">${item.status === 'done' ? '↺' : '✓'}</button>
        <div class="todo-body">
          <span class="task">${escapeHtml(item.description)}</span>
          ${item.completed_at ? `<span class="source">Closed ${formatTimestamp(item.completed_at)}</span>` : ''}
        </div>
      </div>
    `).join('');
  }

  // ---------- clients view (3-pane desktop / wizard on phone) ----------

  const clientsState = {
    clients: [],
    selectedPhone: null,
    selectedConversationId: null,
  };

  // Below 860px only one pane shows at a time (see dashboard.css); this just
  // flips which one via a data attribute the CSS already keys off. Above
  // 860px all three panes are visible regardless of this value.
  function setClientsStep(step) {
    const shell = document.querySelector('.clients-shell');
    if (shell) shell.dataset.step = step;
  }

  async function loadClientsView() {
    clientsState.clients = await fetchJSON('/api/clients');
    renderClientList();
  }

  function renderClientList() {
    const list = document.getElementById('client-list');
    if (!clientsState.clients.length) {
      list.innerHTML = '<p class="chat-hint pane-placeholder">No clients yet. Add one, or wait for a call to come in.</p>';
      return;
    }
    list.innerHTML = clientsState.clients.map((c) => `
      <div class="client-row${c.phone === clientsState.selectedPhone ? ' active' : ''}" data-phone="${escapeHtml(c.phone)}">
        <div class="client-row-name">${escapeHtml(c.name || formatPhone(c.phone))}</div>
        <div class="client-row-phone">${escapeHtml(formatPhone(c.phone))}</div>
        <div class="client-row-meta">${c.call_count} call${c.call_count === 1 ? '' : 's'}${c.last_call ? ' · ' + formatTimestamp(c.last_call) : ''}</div>
      </div>
    `).join('');
    list.querySelectorAll('.client-row').forEach((row) => {
      row.addEventListener('click', () => selectClient(row.dataset.phone));
    });
  }

  async function selectClient(phone) {
    clientsState.selectedPhone = phone;
    clientsState.selectedConversationId = null;
    renderClientList();
    document.getElementById('pane-c').innerHTML = '<p class="chat-hint pane-placeholder">Select a conversation to view it here.</p>';
    setClientsStep('client');
    await loadClientProfile(phone);
  }

  async function loadClientProfile(phone) {
    const [client, conversations] = await Promise.all([
      fetchJSON(`/api/clients/${encodeURIComponent(phone)}`),
      fetchJSON(`/api/clients/${encodeURIComponent(phone)}/conversations`),
    ]);
    renderClientProfile(client, conversations);
  }

  function renderClientProfile(client, conversations) {
    const paneB = document.getElementById('pane-b');
    paneB.innerHTML = `
      <div class="pane-header">
        <div class="pane-header-left">
          <button type="button" class="btn-icon pane-back" id="pane-b-back" aria-label="Back to clients">←</button>
          <span>Client</span>
        </div>
      </div>
      <div class="client-profile">
        <div class="client-field"><label>Phone</label><input type="text" value="${escapeHtml(formatPhone(client.phone))}" disabled></div>
        <div class="client-field">
          <label>Name${client.name_is_manual ? ' <span class="pill pill-accent" title="Manually corrected — post-call extraction will not overwrite this">🔒 Manually set</span>' : ''}</label>
          <input type="text" id="client-name" value="${escapeHtml(client.name)}" placeholder="Add a name">
        </div>
        <div class="client-field"><label>Email</label><input type="text" id="client-email" value="${escapeHtml(client.email)}" placeholder="Add an email"></div>
        <div class="client-field"><label>Address</label><input type="text" id="client-address" value="${escapeHtml(client.address)}" placeholder="Add an address"></div>
        <button type="button" class="save-btn" id="client-profile-save">Save</button>
      </div>
      <div class="client-section conversations-section">
        <div class="client-section-title">Conversations</div>
        <div class="client-conversations" id="client-conversations"></div>
      </div>
    `;

    renderClientConversations(conversations);

    document.getElementById('pane-b-back').addEventListener('click', () => setClientsStep('list'));

    document.getElementById('client-profile-save').addEventListener('click', async () => {
      const body = {
        name: document.getElementById('client-name').value.trim(),
        email: document.getElementById('client-email').value.trim(),
        address: document.getElementById('client-address').value.trim(),
      };
      const updated = await fetchJSON(`/api/clients/${encodeURIComponent(client.phone)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      clientsState.clients = await fetchJSON('/api/clients');
      renderClientList();
      applyFilters();
      state.callerNames = await fetchJSON('/api/callers/names');
      // Re-render so the "🔒 Manually set" badge shows up immediately —
      // saving a non-empty name here always locks it (see api_update_client).
      renderClientProfile(updated, conversations);
    });

  }

  function renderClientConversations(conversations) {
    const container = document.getElementById('client-conversations');
    if (!conversations.length) {
      container.innerHTML = '<p class="chat-hint pane-placeholder">No calls from this client yet.</p>';
      return;
    }
    container.innerHTML = conversations.map((c) => `
      <div class="conversation-row${c.id === clientsState.selectedConversationId ? ' active' : ''}" data-id="${escapeHtml(c.id)}">
        <div class="conv-time">${formatTimestamp(c.start_time)}</div>
        <div class="conv-meta">${c.message_count} msgs · ${formatDuration(c.duration_seconds)}</div>
        <div>${renderTopicChips(c.topics)}</div>
      </div>
    `).join('');
    container.querySelectorAll('.conversation-row').forEach((row) => {
      row.addEventListener('click', () => selectConversation(row.dataset.id));
    });
  }

  async function selectConversation(conversationId) {
    clientsState.selectedConversationId = conversationId;
    document.querySelectorAll('#client-conversations .conversation-row').forEach((row) => {
      row.classList.toggle('active', row.dataset.id === conversationId);
    });
    setClientsStep('conv');

    const [conversation, notes] = await Promise.all([
      fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}`),
      fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}/notes`),
    ]);

    const paneC = document.getElementById('pane-c');
    paneC.innerHTML = `
      <div class="pane-c-header">
        <div class="pane-c-header-top">
          <button type="button" class="btn-icon pane-back" id="pane-c-back" aria-label="Back to client">←</button>
          <div class="conv-title">${escapeHtml(formatCallerLabel(conversation.caller_number))}</div>
        </div>
        <div class="conv-sub">${formatTimestamp(conversation.start_time)} · ${formatDuration(conversation.duration_seconds)}</div>
      </div>
      <div class="pane-c-tabs">
        <button type="button" class="drawer-tab active" data-tab="pc-transcript">Transcript</button>
        <button type="button" class="drawer-tab" data-tab="pc-notes">Notes</button>
      </div>
      <div class="pane-c-body">
        <div class="pane-c-view active" id="pc-transcript">${transcriptHtml(conversation.messages)}</div>
        <div class="pane-c-view" id="pc-notes">
          <div id="pc-notes-list">${notesListHtml(notes)}</div>
          <form class="note-form" id="pc-note-form">
            <textarea id="pc-note-input" rows="2" placeholder="Add a note about this caller or call…"></textarea>
            <button type="submit">Add note</button>
          </form>
        </div>
      </div>
    `;

    document.getElementById('pane-c-back').addEventListener('click', () => setClientsStep('client'));

    paneC.querySelectorAll('.pane-c-tabs .drawer-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        paneC.querySelectorAll('.pane-c-tabs .drawer-tab').forEach((b) => b.classList.toggle('active', b === btn));
        paneC.querySelectorAll('.pane-c-view').forEach((v) => v.classList.toggle('active', v.id === btn.dataset.tab));
      });
    });

    document.getElementById('pc-notes-list').addEventListener('click', async (e) => {
      const btn = e.target.closest('.note-delete');
      if (!btn) return;
      const noteId = btn.closest('.note-item').dataset.id;
      const updated = await fetchJSON(
        `/api/conversations/${encodeURIComponent(conversationId)}/notes/${encodeURIComponent(noteId)}`,
        { method: 'DELETE' }
      );
      document.getElementById('pc-notes-list').innerHTML = notesListHtml(updated);
    });

    document.getElementById('pc-note-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = document.getElementById('pc-note-input');
      const text = input.value.trim();
      if (!text) return;
      const updated = await fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      input.value = '';
      document.getElementById('pc-notes-list').innerHTML = notesListHtml(updated);
    });
  }

  function setupClientsView() {
    document.getElementById('add-client-btn').addEventListener('click', () => {
      document.getElementById('add-client-form').hidden = false;
    });
    document.getElementById('add-client-cancel').addEventListener('click', () => {
      document.getElementById('add-client-form').hidden = true;
    });
    document.getElementById('add-client-save').addEventListener('click', async () => {
      const phone = document.getElementById('add-client-phone').value.trim();
      const name = document.getElementById('add-client-name').value.trim();
      if (!phone) return;
      await fetchJSON('/api/clients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, name, email: '', address: '' }),
      });
      document.getElementById('add-client-phone').value = '';
      document.getElementById('add-client-name').value = '';
      document.getElementById('add-client-form').hidden = true;
      await loadClientsView();
    });
  }

  // Live calls used to render in-page here (SSE client + card rendering).
  // That code now lives in src/static/live.js, served at its own /live page
  // (see live.html) so the always-open SSE connection doesn't tie up this
  // tab's loading indicator. Server side is unchanged: src/live_calls.py +
  // the hooks in src/main.py's handle_media_stream.

  // ---------- init ----------

  document.addEventListener('DOMContentLoaded', () => {
    tickClock();
    setInterval(tickClock, 1000);
    setupNav();
    setupFilters();
    setupCallsTable();
    setupDrawer();
    setupActionItems();
    setupScheduleSheet();
    setupClientsView();
    // Surface load failures instead of silently leaving an empty dashboard.
    loadConversations()
      .then(() => {
        // Cross-tab link from the standalone Live page (live.js's
        // openCallInDashboard) — open the drawer for the call it named, then
        // scrub the param so a refresh doesn't reopen it.
        const callId = new URLSearchParams(location.search).get('call');
        if (callId) {
          openDrawer(callId);
          history.replaceState(null, '', location.pathname);
        }
      })
      .catch((err) => {
        const empty = document.getElementById('calls-empty');
        empty.textContent = `Couldn't load calls: ${err.message}. Is the server running and CockroachDB reachable?`;
        empty.hidden = false;
      });
  });
})();
