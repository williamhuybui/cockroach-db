(() => {
  const state = {
    conversations: [],
    currentId: null,
    currentCallerNumber: null,
    callerNames: {},
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
    const needsFollowUp = convos.filter((c) => c._todoCount > 0).length;

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
    tbody.innerHTML = rows.map((c) => `
      <tr data-id="${escapeHtml(c.id)}">
        <td class="num">${formatTimestamp(c.start_time)}</td>
        <td class="caller">${formatCallerCell(c.caller_number)}</td>
        <td class="num">${c.message_count}</td>
        <td class="num">${formatDuration(c.duration_seconds)}</td>
        <td class="topics">${renderTopicChips(c.topics)}</td>
      </tr>
    `).join('');
    tbody.querySelectorAll('tr').forEach((tr) => {
      tr.addEventListener('click', () => openDrawer(tr.dataset.id));
    });
  }

  function applyFilters() {
    const filters = {};
    document.querySelectorAll('.filter-row input').forEach((inp) => {
      filters[inp.dataset.filter] = inp.value.trim().toLowerCase();
    });
    const filtered = state.conversations.filter((c) => {
      if (filters.time && !formatTimestamp(c.start_time).toLowerCase().includes(filters.time)) return false;
      if (filters.caller_number) {
        const hay = `${formatPhone(c.caller_number)} ${c.caller_number} ${state.callerNames[c.caller_number] || ''}`.toLowerCase();
        if (!hay.includes(filters.caller_number)) return false;
      }
      if (filters.message_count && c.message_count < Number(filters.message_count)) return false;
      if (filters.duration_seconds && c.duration_seconds < Number(filters.duration_seconds)) return false;
      if (filters.topics && !(c.topics || []).join(' ').toLowerCase().includes(filters.topics)) return false;
      return true;
    });
    renderTable(filtered);
  }

  function setupFilters() {
    document.querySelectorAll('.filter-row input').forEach((inp) => {
      inp.addEventListener('input', applyFilters);
    });
  }

  async function loadConversations() {
    const [convos, names] = await Promise.all([
      fetchJSON('/api/conversations'),
      fetchJSON('/api/callers/names'),
    ]);
    // pull todo counts in parallel so the "needs follow-up" tile and future
    // per-row indicators have the data without a second round-trip per click
    await Promise.all(convos.map(async (c) => {
      try {
        const todos = await fetchJSON(`/api/conversations/${encodeURIComponent(c.id)}/todos`);
        c._todoCount = todos.length;
      } catch {
        c._todoCount = 0;
      }
    }));
    state.conversations = convos;
    state.callerNames = names;
    renderStatTiles();
    renderTable(convos);
    renderActionItems();
  }

  // ---------- action items (to-do, lives inside the Calls tab) ----------

  async function renderActionItems() {
    const groups = await fetchJSON('/api/todos');
    const totalItems = groups.reduce((sum, g) => sum + g.todos.length, 0);
    document.getElementById('action-items-count').textContent = totalItems ? `(${totalItems})` : '';

    const list = document.getElementById('action-items-list');
    const empty = document.getElementById('action-items-empty');
    if (!groups.length) {
      list.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    list.innerHTML = groups.map((g) => `
      <div class="action-item-card" data-id="${escapeHtml(g.conversation_id)}">
        <div class="caller">${escapeHtml(formatCallerLabel(g.caller_number))}</div>
        <div class="time">${formatTimestamp(g.start_time)}</div>
        ${g.todos.map((t) => `<span class="task">${escapeHtml(t.task)}</span>`).join('')}
      </div>
    `).join('');
    list.querySelectorAll('.action-item-card').forEach((card) => {
      card.addEventListener('click', () => openDrawer(card.dataset.id));
    });
  }

  function setupActionItems() {
    document.getElementById('action-items-toggle').addEventListener('click', () => {
      document.querySelector('.action-items-card').classList.toggle('collapsed');
    });
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

    document.getElementById('caller-edit-cancel').addEventListener('click', () => {
      document.getElementById('caller-edit-form').hidden = true;
    });

    document.getElementById('caller-edit-save').addEventListener('click', saveCallerName);

    document.getElementById('caller-edit-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') saveCallerName();
      if (e.key === 'Escape') document.getElementById('caller-edit-form').hidden = true;
    });

    bindChatForm(
      document.getElementById('chat-form'),
      document.getElementById('chat-input'),
      document.getElementById('chat-thread'),
      () => state.currentId
    );

    document.getElementById('upload-btn').addEventListener('click', async () => {
      const fileInput = document.getElementById('upload-input');
      if (!fileInput.files.length || !state.currentId) return;
      const conversation = state.conversations.find((c) => c.id === state.currentId);
      const callerNumber = conversation ? conversation.caller_number : 'unknown';
      const form = new FormData();
      form.append('file', fileInput.files[0]);
      const files = await fetchJSON(`/api/uploads/${encodeURIComponent(callerNumber)}`, {
        method: 'POST',
        body: form,
      });
      fileInput.value = '';
      renderDrawerFiles(files, callerNumber);
    });

    document.getElementById('drawer-file-list').addEventListener('click', (e) => {
      const btn = e.target.closest('.file-rename-btn');
      if (!btn) return;
      const row = btn.closest('.file-row');
      startRename(row, state.drawerFilesCaller, (files) => renderDrawerFiles(files, state.drawerFilesCaller));
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
  }

  async function startRename(row, caller, onDone) {
    const oldName = row.dataset.name;

    async function refresh() {
      const files = await fetchJSON(`/api/uploads/${encodeURIComponent(caller)}`);
      onDone(files);
    }

    row.innerHTML = `
      <input type="text" class="file-rename-input" value="${escapeHtml(oldName)}" autocomplete="off">
      <button type="button" class="save-btn">Save</button>
      <button type="button" class="cancel-btn">Cancel</button>
    `;
    const input = row.querySelector('.file-rename-input');
    input.focus();
    input.select();

    async function save() {
      const newName = input.value.trim();
      if (!newName || newName === oldName) return refresh();
      try {
        const files = await fetchJSON(`/api/uploads/${encodeURIComponent(caller)}/rename`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ old_name: oldName, new_name: newName }),
        });
        onDone(files);
      } catch (err) {
        alert('Could not rename file — a file with that name may already exist.');
        refresh();
      }
    }

    row.querySelector('.save-btn').addEventListener('click', save);
    row.querySelector('.cancel-btn').addEventListener('click', refresh);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') save();
      if (e.key === 'Escape') refresh();
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
      <div class="msg ${m.speaker}">
        <div class="who">${m.speaker === 'caller' ? 'Caller' : 'Assistant'} · ${formatTimestamp(m.timestamp)}</div>
        <div class="bubble">${escapeHtml(m.text)}</div>
      </div>
    `).join('') || '<p class="chat-hint">No transcript recorded for this call.</p>';
  }

  function appendChatQuery(thread, message) {
    thread.insertAdjacentHTML('beforeend', `<div class="chat-bubble query">"${escapeHtml(message)}"</div>`);
    thread.scrollTop = thread.scrollHeight;
  }

  function appendChatReply(thread, result) {
    const matches = (result.matches || []).map((m) => `
      <div class="match">${m.speaker === 'caller' ? 'Caller' : 'Assistant'}: “${escapeHtml(m.text)}”</div>
    `).join('');
    thread.insertAdjacentHTML('beforeend', `<div class="chat-bubble">${escapeHtml(result.reply)}${matches}</div>`);
    thread.scrollTop = thread.scrollHeight;
  }

  function bindChatForm(formEl, inputEl, threadEl, getConversationId) {
    formEl.addEventListener('submit', async (e) => {
      e.preventDefault();
      const message = inputEl.value.trim();
      const conversationId = getConversationId();
      if (!message || !conversationId) return;
      appendChatQuery(threadEl, message);
      inputEl.value = '';
      const result = await fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      appendChatReply(threadEl, result);
    });
  }

  async function loadDrawerContent(id) {
    const conversation = await fetchJSON(`/api/conversations/${encodeURIComponent(id)}`);
    state.currentCallerNumber = conversation.caller_number;
    updateDrawerCallerDisplay();
    document.getElementById('drawer-time').textContent = formatTimestamp(conversation.start_time);

    document.getElementById('pane-transcript').innerHTML = transcriptHtml(conversation.messages);

    document.getElementById('chat-thread').innerHTML = '<p class="chat-hint">Search this conversation\'s transcript — e.g. try "quote" or "photo".</p>';

    const todos = await fetchJSON(`/api/conversations/${encodeURIComponent(id)}/todos`);
    document.getElementById('pane-todos').innerHTML = todos.length
      ? todos.map((t) => `
          <label class="todo-item">
            <input type="checkbox" onchange="this.closest('.todo-item').classList.toggle('done', this.checked)">
            <span><span class="task">${escapeHtml(t.task)}</span><span class="source">“${escapeHtml(t.source)}”</span></span>
          </label>
        `).join('')
      : '<p class="chat-hint">No action items detected for this call.</p>';

    const notes = await fetchJSON(`/api/conversations/${encodeURIComponent(id)}/notes`);
    renderNotes(notes);

    const files = await fetchJSON(`/api/uploads/${encodeURIComponent(conversation.caller_number)}`);
    renderDrawerFiles(files, conversation.caller_number);
  }

  function renderDrawerFiles(files, caller) {
    state.drawerFilesCaller = caller;
    const list = document.getElementById('drawer-file-list');
    list.innerHTML = files.length
      ? files.map((f) => `
          <li class="file-row" data-name="${escapeHtml(f.name)}">
            <span class="file-name">${escapeHtml(f.name)}</span>
            <span class="file-actions">
              <span class="file-meta">${Math.ceil(f.size / 1024)} KB</span>
              <button type="button" class="file-rename-btn" title="Rename">✎</button>
            </span>
          </li>
        `).join('')
      : '<li class="file-row"><span class="file-meta">No files uploaded for this caller yet.</span></li>';
  }

  // ---------- clients view (3-pane) ----------

  const clientsState = {
    clients: [],
    selectedPhone: null,
    selectedConversationId: null,
  };

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
    await loadClientProfile(phone);
  }

  async function loadClientProfile(phone) {
    const [client, uploads, conversations] = await Promise.all([
      fetchJSON(`/api/clients/${encodeURIComponent(phone)}`),
      fetchJSON(`/api/uploads/${encodeURIComponent(phone)}`),
      fetchJSON(`/api/clients/${encodeURIComponent(phone)}/conversations`),
    ]);
    renderClientProfile(client, uploads, conversations);
  }

  function renderClientProfile(client, uploads, conversations) {
    const paneB = document.getElementById('pane-b');
    paneB.innerHTML = `
      <div class="pane-header"><span>Client</span></div>
      <div class="client-profile">
        <div class="client-field"><label>Phone</label><input type="text" value="${escapeHtml(formatPhone(client.phone))}" disabled></div>
        <div class="client-field"><label>Name</label><input type="text" id="client-name" value="${escapeHtml(client.name)}" placeholder="Add a name"></div>
        <div class="client-field"><label>Email</label><input type="text" id="client-email" value="${escapeHtml(client.email)}" placeholder="Add an email"></div>
        <div class="client-field"><label>Address</label><input type="text" id="client-address" value="${escapeHtml(client.address)}" placeholder="Add an address"></div>
        <button type="button" class="save-btn" id="client-profile-save">Save</button>
      </div>
      <div class="client-section">
        <div class="client-section-title">Files</div>
        <div class="upload-box">
          <input type="file" id="client-upload-input">
          <button type="button" id="client-upload-btn">Upload</button>
        </div>
        <ul class="file-list" id="client-file-list"></ul>
      </div>
      <div class="client-section conversations-section">
        <div class="client-section-title">Conversations</div>
        <div class="client-conversations" id="client-conversations"></div>
      </div>
    `;

    renderClientFiles(uploads, client.phone);
    renderClientConversations(conversations);

    document.getElementById('client-profile-save').addEventListener('click', async () => {
      const body = {
        name: document.getElementById('client-name').value.trim(),
        email: document.getElementById('client-email').value.trim(),
        address: document.getElementById('client-address').value.trim(),
      };
      await fetchJSON(`/api/clients/${encodeURIComponent(client.phone)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      clientsState.clients = await fetchJSON('/api/clients');
      renderClientList();
      applyFilters();
      state.callerNames = await fetchJSON('/api/callers/names');
    });

    document.getElementById('client-upload-btn').addEventListener('click', async () => {
      const fileInput = document.getElementById('client-upload-input');
      if (!fileInput.files.length) return;
      const form = new FormData();
      form.append('file', fileInput.files[0]);
      const files = await fetchJSON(`/api/uploads/${encodeURIComponent(client.phone)}`, { method: 'POST', body: form });
      fileInput.value = '';
      renderClientFiles(files, client.phone);
    });

    document.getElementById('client-file-list').addEventListener('click', (e) => {
      const btn = e.target.closest('.file-rename-btn');
      if (!btn) return;
      const row = btn.closest('.file-row');
      startRename(row, client.phone, (files) => renderClientFiles(files, client.phone));
    });
  }

  function renderClientFiles(files, phone) {
    const list = document.getElementById('client-file-list');
    list.innerHTML = files.length
      ? files.map((f) => `
          <li class="file-row" data-name="${escapeHtml(f.name)}">
            <span class="file-name">${escapeHtml(f.name)}</span>
            <span class="file-actions">
              <span class="file-meta">${Math.ceil(f.size / 1024)} KB</span>
              <button type="button" class="file-rename-btn" title="Rename">✎</button>
            </span>
          </li>
        `).join('')
      : '<li class="file-row"><span class="file-meta">No files uploaded yet.</span></li>';
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

    const [conversation, notes] = await Promise.all([
      fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}`),
      fetchJSON(`/api/conversations/${encodeURIComponent(conversationId)}/notes`),
    ]);

    const paneC = document.getElementById('pane-c');
    paneC.innerHTML = `
      <div class="pane-c-header">
        <div class="conv-title">${escapeHtml(formatCallerLabel(conversation.caller_number))}</div>
        <div class="conv-sub">${formatTimestamp(conversation.start_time)} · ${formatDuration(conversation.duration_seconds)}</div>
      </div>
      <div class="pane-c-tabs">
        <button type="button" class="drawer-tab active" data-tab="pc-transcript">Transcript</button>
        <button type="button" class="drawer-tab" data-tab="pc-notes">Notes</button>
        <button type="button" class="drawer-tab" data-tab="pc-chat">Chat</button>
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
        <div class="pane-c-view" id="pc-chat">
          <div class="chat-thread" id="pc-chat-thread">
            <p class="chat-hint">Search this conversation's transcript — e.g. try "quote" or "photo".</p>
          </div>
          <form class="chat-form" id="pc-chat-form">
            <input type="text" id="pc-chat-input" placeholder="Search this conversation…" autocomplete="off">
            <button type="submit">Search</button>
          </form>
        </div>
      </div>
    `;

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

    bindChatForm(
      document.getElementById('pc-chat-form'),
      document.getElementById('pc-chat-input'),
      document.getElementById('pc-chat-thread'),
      () => conversationId
    );
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

  // ---------- init ----------

  document.addEventListener('DOMContentLoaded', () => {
    tickClock();
    setInterval(tickClock, 1000);
    setupNav();
    setupFilters();
    setupDrawer();
    setupActionItems();
    setupClientsView();
    loadConversations();
  });
})();
