// Live calls — standalone page (opened in its own tab from the dashboard's
// topbar). Split out from dashboard.js so the always-open SSE connection to
// /api/live/stream lives in a tab the user opts into, instead of tying up
// the main dashboard tab's loading indicator forever.
//
// Server side is unchanged: src/live_calls.py + the hooks in src/main.py's
// handle_media_stream.

(() => {
  const state = {
    callerNames: {}, // phone -> name, from /api/callers/names (best-effort)
  };

  const liveState = {
    calls: new Map(), // stream_sid -> call record, merged in place from events
    connected: false,
  };

  let toastTimer = null;

  const LIVE_END_REASON_LABELS = {
    disconnected: 'Caller hung up',
    duration_cutoff: 'Time limit reached',
    caller_said_goodbye: 'Caller said goodbye',
    task_completed: 'Task completed',
    abusive_or_spam: 'Ended — spam/abuse',
    no_progress: 'Ended — no progress',
    agent_end_call: 'Agent ended the call',
  };

  // ---------- helpers (mirrors dashboard.js's copies) ----------

  function parseTimestamp(iso) {
    if (!iso) return null;
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

  function tickClock() {
    const el = document.getElementById('clock');
    el.textContent = new Date().toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', second: '2-digit',
    });
  }

  // No drawer exists on this standalone page — "Open call" focuses (or
  // opens) the dashboard tab and asks it to open that call's drawer via a
  // query param dashboard.js checks for on load.
  function openCallInDashboard(callId) {
    window.open(`/dashboard?call=${encodeURIComponent(callId)}`, 'frontdesk_dashboard');
  }

  // ---------- live calls ----------

  function liveEndReasonLabel(reason) {
    return LIVE_END_REASON_LABELS[reason] || 'Call ended';
  }

  function liveCallerLabel(call) {
    return state.callerNames[call.caller_number] || call.caller_name || formatPhone(call.caller_number);
  }

  function liveSpeakerCaption(speaker) {
    if (speaker === 'caller') return 'Caller speaking…';
    if (speaker === 'assistant') return 'Assistant responding…';
    return '…listening';
  }

  function liveTurnHtml(turn) {
    return `
      <div class="msg ${turn.speaker}">
        <div class="who">${turn.speaker === 'caller' ? 'Caller' : 'Assistant'} · ${formatTimestamp(turn.at)}</div>
        <div class="bubble">${escapeHtml(turn.text)}</div>
      </div>
    `;
  }

  function liveMeterHtml(label, value, max) {
    const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
    const level = pct >= 95 ? 'critical' : pct >= 70 ? 'warn' : 'good';
    return `
      <div class="live-meter">
        <div class="live-meter-label"><span>${label}</span><span>${value}/${max}</span></div>
        <div class="live-meter-track"><div class="live-meter-fill live-meter-${level}" style="width:${pct}%"></div></div>
      </div>
    `;
  }

  function liveSummarySectionHtml(call) {
    if (call.summary_status === 'ready' && call.summary) {
      const s = call.summary;
      const urgent = s.urgency === 'High' || s.urgency === 'Emergency';
      return `
        <div class="live-summary">
          <div class="live-summary-head">
            <strong>${escapeHtml(s.problem || 'Call summary')}</strong>
            ${s.urgency ? `<span class="pill ${urgent ? 'pill-critical' : 'pill-accent'}">${escapeHtml(s.urgency)}</span>` : ''}
          </div>
          ${s.summary ? `<p>${escapeHtml(s.summary)}</p>` : ''}
          ${(s.todo_items || []).length ? `<div class="live-summary-todos">${s.todo_items.map((t) => `<span class="pill">${escapeHtml(t.description || '')}</span>`).join('')}</div>` : ''}
          ${call.call_id ? `<button type="button" class="btn btn-ghost btn-sm live-open-call" data-call-id="${escapeHtml(call.call_id)}">Open call</button>` : ''}
        </div>
      `;
    }
    if (call.summary_status === 'failed') {
      return `
        <div class="live-summary">
          <p class="chat-hint">Summary unavailable.</p>
          ${call.call_id ? `<button type="button" class="btn btn-ghost btn-sm live-open-call" data-call-id="${escapeHtml(call.call_id)}">Open call</button>` : ''}
        </div>
      `;
    }
    // "pending" — the call just ended and post-call extraction hasn't
    // finished yet.
    return `
      <div class="live-summary">
        <div class="typing-dots"><span></span><span></span><span></span></div>
        <span class="chat-hint">Summarizing…</span>
      </div>
    `;
  }

  function liveCallCardHtml(call) {
    const ended = !!call.ended;
    return `
      <article class="live-card${ended ? ' ended' : ''}" id="live-card-${call.stream_sid}">
        <header class="live-card-head">
          <span class="pill ${ended ? 'pill-muted' : 'pill-good live-onair'}">
            ${ended ? '● ' + escapeHtml(liveEndReasonLabel(call.reason)) : '● ON AIR'}
          </span>
          <div class="live-who">
            <span class="live-caller">${escapeHtml(liveCallerLabel(call))}</span>
            <span class="live-phone">${escapeHtml(formatPhone(call.caller_number))}</span>
            ${call.returning && call.caller_address ? `<span class="live-address">📍 ${escapeHtml(call.caller_address)}</span>` : ''}
          </div>
          ${call.returning ? '<span class="pill pill-roof">Returning caller</span>' : ''}
          <span class="live-duration" id="live-duration-${call.stream_sid}">${formatDuration(call.duration_seconds || 0)}</span>
        </header>

        ${!ended ? `
          <div class="live-vu-row" id="live-vu-${call.stream_sid}">
            <div class="live-vu-side">
              <div class="vu${call.speaker === 'caller' ? ' active' : ''}" data-role="caller"><i></i><i></i><i></i><i></i><i></i></div>
              <span class="live-vu-label">Caller</span>
            </div>
            <div class="live-vu-caption" id="live-caption-${call.stream_sid}">${liveSpeakerCaption(call.speaker)}</div>
            <div class="live-vu-side">
              <div class="vu${call.speaker === 'assistant' ? ' active' : ''}" data-role="assistant"><i></i><i></i><i></i><i></i><i></i></div>
              <span class="live-vu-label">Assistant</span>
            </div>
          </div>
        ` : ''}

        <div class="live-feed" id="live-feed-${call.stream_sid}">
          ${(call.turns || []).map(liveTurnHtml).join('')}
        </div>

        ${!ended ? `
          <div class="live-meters" id="live-meters-${call.stream_sid}">
            ${liveMeterHtml('Duration', call.duration_seconds || 0, 300)}
            ${liveMeterHtml('Tokens', call.total_tokens || 0, 500)}
            ${call.wrap_up ? '<span class="pill pill-roof">Wrapping up</span>' : ''}
          </div>
        ` : liveSummarySectionHtml(call)}
      </article>
    `;
  }

  function liveStandbyHtml() {
    return `
      <div class="standby">
        <div class="standby-orb"></div>
        <p class="standby-text">Line is open. No active calls.</p>
      </div>
    `;
  }

  function renderLiveView() {
    const content = document.getElementById('live-content');
    const calls = Array.from(liveState.calls.values())
      .sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));

    if (!calls.length) {
      content.innerHTML = liveStandbyHtml();
      return;
    }
    content.innerHTML = calls.map(liveCallCardHtml).join('');
    content.querySelectorAll('.live-open-call').forEach((btn) => {
      btn.addEventListener('click', () => openCallInDashboard(btn.dataset.callId));
    });
  }

  function renderLiveConnectionPill() {
    const pill = document.getElementById('live-connection-pill');
    if (!pill) return;
    pill.textContent = liveState.connected ? '● Live' : '⟳ Reconnecting…';
    pill.className = `pill ${liveState.connected ? 'pill-good' : 'pill-roof'}`;
  }

  // ---- targeted DOM updates for the two high-frequency event types ----
  //
  // speaker_changed and transcript_turn can fire many times over one call. A
  // full renderLiveView() on every one of them would reset the transcript's
  // scroll position and restart the VU/entry animations, so these patch the
  // existing card in place instead. If the card isn't mounted yet (e.g. the
  // event raced the initial render), fall back to a full render.

  function updateLiveSpeaker(sid, speaker, bargeIn) {
    const call = liveState.calls.get(sid);
    if (!call) return;
    call.speaker = speaker;

    const vuRow = document.getElementById(`live-vu-${sid}`);
    if (!vuRow) { renderLiveView(); return; }

    vuRow.querySelector('.vu[data-role="caller"]').classList.toggle('active', speaker === 'caller');
    const assistantVu = vuRow.querySelector('.vu[data-role="assistant"]');
    assistantVu.classList.toggle('active', speaker === 'assistant');
    document.getElementById(`live-caption-${sid}`).textContent = liveSpeakerCaption(speaker);

    if (bargeIn) {
      assistantVu.classList.remove('barge');
      void assistantVu.offsetWidth; // restart the animation if it's mid-flash already
      assistantVu.classList.add('barge');
    }

    // Audio starts streaming before the transcript is ready, so fill that gap
    // honestly with a typing indicator rather than leaving dead air.
    const feed = document.getElementById(`live-feed-${sid}`);
    if (feed) {
      const dots = feed.querySelector('.live-typing');
      if (speaker === 'assistant' && !dots) {
        feed.insertAdjacentHTML('beforeend', '<div class="typing-dots live-typing msg assistant"><span></span><span></span><span></span></div>');
        if (feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60) feed.scrollTop = feed.scrollHeight;
      } else if (speaker !== 'assistant' && dots) {
        dots.remove();
      }
    }
  }

  function appendLiveTurn(sid, speaker, text, at) {
    const call = liveState.calls.get(sid);
    if (!call) return;
    call.turns = call.turns || [];
    call.turns.push({ speaker, text, at });

    const feed = document.getElementById(`live-feed-${sid}`);
    if (!feed) { renderLiveView(); return; }

    const dots = feed.querySelector('.live-typing');
    if (dots) dots.remove();
    const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
    feed.insertAdjacentHTML('beforeend', liveTurnHtml({ speaker, text, at }));
    if (nearBottom) feed.scrollTop = feed.scrollHeight;
  }

  function updateLiveMetrics(sid, totalTokens, durationSeconds, wrapUp) {
    const call = liveState.calls.get(sid);
    if (!call) return;
    call.total_tokens = totalTokens;
    call.duration_seconds = durationSeconds;
    call.wrap_up = wrapUp;

    const meters = document.getElementById(`live-meters-${sid}`);
    if (!meters) { renderLiveView(); return; }
    meters.innerHTML = `
      ${liveMeterHtml('Duration', durationSeconds, 300)}
      ${liveMeterHtml('Tokens', totalTokens, 500)}
      ${wrapUp ? '<span class="pill pill-roof">Wrapping up</span>' : ''}
    `;
  }

  // A single ticker (like tickClock) recomputes each active call's duration
  // from started_at rather than incrementing a counter, so it stays correct
  // through tab throttling and SSE reconnects.
  function tickLiveDurations() {
    liveState.calls.forEach((call, sid) => {
      if (call.ended || !call.started_at) return;
      const started = parseTimestamp(call.started_at);
      if (!started) return;
      const el = document.getElementById(`live-duration-${sid}`);
      if (!el) return;
      el.textContent = formatDuration(Math.max(0, Math.round((Date.now() - started.getTime()) / 1000)));
    });
  }

  function onLiveEvent(name, data) {
    switch (name) {
      case 'snapshot':
        liveState.calls.clear();
        (data.calls || []).forEach((c) => liveState.calls.set(c.stream_sid, c));
        renderLiveView();
        break;

      case 'call_started': {
        const isNew = !liveState.calls.has(data.stream_sid);
        liveState.calls.set(data.stream_sid, data);
        renderLiveView();
        if (isNew) {
          showToast(`📞 Incoming call from ${formatPhone(data.caller_number)}`);
        }
        break;
      }

      case 'call_identified': {
        const call = liveState.calls.get(data.stream_sid);
        if (call) { Object.assign(call, data); renderLiveView(); }
        break;
      }

      case 'speaker_changed':
        updateLiveSpeaker(data.stream_sid, data.speaker, data.barge_in);
        break;

      case 'transcript_turn':
        appendLiveTurn(data.stream_sid, data.speaker, data.text, data.at);
        break;

      case 'metrics':
        updateLiveMetrics(data.stream_sid, data.total_tokens, data.duration_seconds, data.wrap_up);
        break;

      case 'call_ended': {
        const call = liveState.calls.get(data.stream_sid);
        if (call) Object.assign(call, data, { ended: true, speaker: 'idle', summary_status: 'pending' });
        renderLiveView();
        break;
      }

      case 'summary_ready': {
        const call = liveState.calls.get(data.stream_sid);
        if (call) { call.summary_status = 'ready'; call.summary = data; }
        renderLiveView();
        break;
      }

      case 'summary_failed': {
        const call = liveState.calls.get(data.stream_sid);
        if (call) call.summary_status = 'failed';
        renderLiveView();
        break;
      }

      default:
        break;
    }
  }

  const LIVE_EVENT_NAMES = [
    'snapshot', 'call_started', 'call_identified', 'speaker_changed',
    'transcript_turn', 'metrics', 'call_ended', 'summary_ready', 'summary_failed',
  ];

  function connectLive() {
    if (!('EventSource' in window)) {
      // Fallback for a browser with no EventSource support: poll instead.
      setInterval(async () => {
        try {
          const data = await fetchJSON('/api/live/calls');
          liveState.calls.clear();
          (data.calls || []).forEach((c) => liveState.calls.set(c.stream_sid, c));
          renderLiveView();
        } catch { /* try again next tick */ }
      }, 5000);
      return;
    }

    // No hand-rolled reconnect logic needed — EventSource reconnects on its
    // own honoring the server's `retry: 3000`, and every new connection gets
    // a fresh snapshot, so state resyncs for free.
    const es = new EventSource('/api/live/stream');
    LIVE_EVENT_NAMES.forEach((name) => {
      es.addEventListener(name, (e) => {
        try {
          onLiveEvent(name, JSON.parse(e.data));
        } catch (err) {
          console.error('Failed to handle live event', name, err);
        }
      });
    });
    es.onopen = () => { liveState.connected = true; renderLiveConnectionPill(); };
    es.onerror = () => { liveState.connected = false; renderLiveConnectionPill(); };
  }

  // ---------- init ----------

  document.addEventListener('DOMContentLoaded', () => {
    tickClock();
    setInterval(tickClock, 1000);
    renderLiveView();
    renderLiveConnectionPill();
    setInterval(tickLiveDurations, 500);
    connectLive();
    // Best-effort — a name manually edited in the Clients tab still shows up
    // here even though this page has no clients view of its own.
    fetchJSON('/api/callers/names').then((names) => { state.callerNames = names; renderLiveView(); }).catch(() => {});
  });
})();
