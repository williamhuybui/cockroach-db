(() => {
  'use strict';

  /* ---------- hero illustration: click/keyboard to "ring" ---------- */

  const heroArt = document.getElementById('hero-art');
  const heroBadge = heroArt?.querySelector('.hero-badge');
  let ringTimer = null;

  function ring() {
    if (!heroArt) return;
    heroArt.classList.add('raining', 'ringing');
    if (heroBadge) heroBadge.innerHTML = '<span class="dot"></span> Incoming call — someone answered';
    clearTimeout(ringTimer);
    ringTimer = setTimeout(() => {
      heroArt.classList.remove('raining', 'ringing');
      if (heroBadge) heroBadge.innerHTML = '<span class="dot"></span> Live &amp; answering — click the house';
    }, 3200);
  }

  heroArt?.addEventListener('click', ring);
  heroArt?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ring(); }
  });
  // Ring once on load so the page doesn't feel static.
  setTimeout(ring, 900);

  /* ---------- "how it works" step stage ---------- */

  const STAGES = [
    {
      icon: '📞',
      title: 'Answers instantly',
      body: 'No voicemail, no hold music, no missed calls at 11pm on a Saturday. The line is always picked up.',
      quote: '"Thanks for calling our roofing team. I\'m an AI assistant, and this call is recorded."',
    },
    {
      icon: '📝',
      title: 'Asks smart questions',
      body: 'It gathers exactly what a technician needs — address, what\'s going on, urgency — and stays out of the diagnosis business.',
      quote: '"What\'s going on with your roof, and what\'s the address?"',
    },
    {
      icon: '🧠',
      title: 'Remembers the caller',
      body: 'Names, addresses, and prior call history are pulled from CockroachDB the moment the caller ID comes in, so nobody repeats themselves.',
      quote: '"Hi Denise — yes, I see your call from earlier this week about the shingle damage."',
    },
    {
      icon: '🔒',
      title: 'Records & discloses',
      body: 'Every call opens with a clear, spoken disclosure: this is AI, and the call is recorded. No ambiguity for the caller.',
      quote: '"Just so you know, I\'m an AI assistant, and this call is recorded."',
    },
    {
      icon: '📬',
      title: 'Hands off cleanly',
      body: 'The conversation is summarized and handed to the owner, ready to book a technician — the loop closes back to a real human.',
      quote: '"So we\'ve got Mark Reynolds, 412 Cascade Avenue, weekday afternoons after 4."',
    },
  ];

  const stepButtons = document.querySelectorAll('.step');
  const stageCard = document.getElementById('stage-card');

  function renderStage(i) {
    const s = STAGES[i];
    if (!stageCard || !s) return;
    stageCard.style.opacity = 0;
    setTimeout(() => {
      stageCard.innerHTML = `
        <div class="stage-icon">${s.icon}</div>
        <h3>${s.title}</h3>
        <p>${s.body}</p>
        <div class="stage-quote">${s.quote}</div>
      `;
      stageCard.style.opacity = 1;
    }, 120);
  }

  stepButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      stepButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderStage(Number(btn.dataset.step));
    });
  });

  renderStage(0);

  /* ---------- live-transcript demo ---------- */

  const SCRIPT = [
    ['assistant', "Hi, thanks for calling — I'm an AI assistant, and this call is recorded. What's going on with your roof today?"],
    ['caller', "Yeah so, quick question first — is it supposed to rain again this weekend? Just trying to figure out timing."],
    ['assistant', "I'm only able to help with roofing questions here. Is there something about your roof I can help with?"],
    ['caller', "Oh, fair — I've got a leak in the attic, started after last week's storm."],
    ['assistant', "Sorry to hear that. Could I get your name and the property address?"],
    ['caller', "Mark Reynolds, 412 Cascade Avenue."],
    ['assistant', "Got it, Mark. And what time works for someone to come take a look?"],
    ['caller', "Weekday afternoons after 4 usually work best."],
    ['assistant', "Perfect — Mark Reynolds, 412 Cascade Avenue, weekday afternoons after 4. We'll be in touch to schedule."],
  ];

  const transcriptEl = document.getElementById('transcript');
  const statusEl = document.getElementById('demo-status');
  const savedBadge = document.getElementById('saved-badge');
  const replayBtn = document.getElementById('replay-btn');
  let demoRunning = false;
  let demoStarted = false;

  function wait(ms) { return new Promise((res) => setTimeout(res, ms)); }

  async function playDemo() {
    if (demoRunning || !transcriptEl) return;
    demoRunning = true;
    transcriptEl.innerHTML = '';
    savedBadge.hidden = true;
    if (statusEl) { statusEl.textContent = '● connecting…'; statusEl.style.color = 'var(--text-muted)'; }
    await wait(500);
    if (statusEl) { statusEl.textContent = '● live'; statusEl.style.color = 'var(--good)'; }

    for (const [speaker, text] of SCRIPT) {
      const typing = document.createElement('div');
      typing.className = 'typing-dots';
      typing.innerHTML = '<span></span><span></span><span></span>';
      transcriptEl.appendChild(typing);
      transcriptEl.scrollTop = transcriptEl.scrollHeight;
      await wait(500 + Math.min(text.length * 8, 900));
      typing.remove();

      const bubble = document.createElement('div');
      bubble.className = `bubble ${speaker === 'caller' ? 'caller' : 'assistant'}`;
      bubble.textContent = text;
      transcriptEl.appendChild(bubble);
      transcriptEl.scrollTop = transcriptEl.scrollHeight;
      await wait(350);
    }

    if (statusEl) { statusEl.textContent = '● call ended'; statusEl.style.color = 'var(--text-muted)'; }
    savedBadge.hidden = false;
    demoRunning = false;
  }

  replayBtn?.addEventListener('click', playDemo);

  // Auto-play once the demo section scrolls into view.
  const demoSection = document.getElementById('demo');
  if (demoSection) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !demoStarted) {
          demoStarted = true;
          playDemo();
        }
      });
    }, { threshold: 0.4 });
    io.observe(demoSection);
  }

  /* ---------- stat count-up ---------- */

  const statEls = document.querySelectorAll('.stat-num');
  const statIO = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      if (el.dataset.done) return;
      el.dataset.done = '1';
      const target = Number(el.dataset.count || 0);
      const prefix = el.dataset.prefix || '';
      const suffix = el.dataset.suffix || '';
      const duration = 900;
      const start = performance.now();
      function frame(now) {
        const progress = Math.min((now - start) / duration, 1);
        const value = Math.round(target * (1 - Math.pow(1 - progress, 3)));
        el.textContent = `${prefix}${value}${suffix}`;
        if (progress < 1) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
      statIO.unobserve(el);
    });
  }, { threshold: 0.5 });
  statEls.forEach((el) => statIO.observe(el));

  /* ---------- reveal-on-scroll for sections ---------- */

  // Hero content is above the fold and animates in via CSS on load instead
  // (see .hero-copy/.hero-art in landing.css) — only gate below-the-fold
  // sections behind the scroll observer.
  const revealTargets = document.querySelectorAll('.section');
  revealTargets.forEach((el) => el.classList.add('reveal'));
  const revealIO = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        revealIO.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });
  revealTargets.forEach((el) => revealIO.observe(el));
})();
