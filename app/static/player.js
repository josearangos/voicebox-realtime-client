/* Chunk queue, playback and teleprompter. The audio element's currentTime drives the highlight. */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const audio = new Audio();
  audio.preload = "auto";
  let run = null;
  let syncQueued = false;

  const now = () => performance.now() / 1000;
  const post = (path, body) =>
    fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(body), keepalive: true }).catch(() => {});
  const event = (name) => run && post("/api/metrics", { session: run.session, event: name, t: now() });
  const action = (name) => run && post("/api/state", { session: run.session, action: name });

  function syncServerUi() {          // ask Gradio to re-read the authoritative server state
    if (syncQueued) return;
    syncQueued = true;
    setTimeout(() => { syncQueued = false; const b = $("#vb-sync"); if (b) b.click(); }, 150);
  }

  function setButtons() {
    const set = (id, on) => { const b = $(id); if (b) b.disabled = !on; };
    const active = run && !run.done && !run.stopped && !run.failed;
    set("#vb-pause", active);
    set("#vb-stop", active);
    set("#vb-restart", run && (run.done || run.stopped || run.failed));
    set("#vb-replay", run && run.done);
    set("#vb-download", run && run.done);
    const p = $("#vb-pause");
    if (p) p.textContent = run && run.paused ? "Resume" : "Pause";
  }

  function buffering(on) {
    const el = $("#vb-buffering");
    if (el) el.textContent = on ? "· buffering…" : "";
  }

  function paint(active) {            // active: global segment index, or null if unknown
    document.querySelectorAll("#vb-teleprompter .vb-seg").forEach((el) => {
      const i = Number(el.dataset.idx);
      const cls = active === null ? "upcoming" : i < active ? "done" : i === active ? "active" : "upcoming";
      if (el.className !== `vb-seg ${cls}`) el.className = `vb-seg ${cls}`;
    });
  }

  function activeSegment(chunk, t, duration) {   // same math as app/teleprompter.py
    if (!isFinite(t) || !duration || duration <= 0 || !run.lens[chunk]) return null;
    const lens = run.lens[chunk];
    const base = run.lens.slice(0, chunk).reduce((n, c) => n + c.length, 0);
    const pos = Math.min(Math.max(t / duration, 0), 1) * lens.reduce((a, b) => a + b, 0);
    let acc = 0;
    for (let i = 0; i < lens.length; i++) { acc += lens[i]; if (pos < acc) return base + i; }
    return base + lens.length - 1;
  }

  function scrollTo(idx) {
    const box = $("#vb-teleprompter");
    const el = box && box.querySelector(`.vb-seg[data-idx="${idx}"]`);
    if (el) box.scrollTop = el.offsetTop - box.clientHeight / 2 + el.clientHeight / 2;
  }

  function release() {
    if (!run) return;
    run.ctrl.abort();
    run.urls.forEach((u) => u && URL.revokeObjectURL(u));
    run.urls = [];
  }

  function fail(message) {
    if (!run || run.failed) return;
    run.failed = true;
    audio.pause(); audio.removeAttribute("src");
    release(); paint(null); buffering(false);
    setButtons(); syncServerUi();
    if (message) { const n = $("#vb-buffering"); if (n) n.textContent = ""; }
  }

  async function fetchChunk(i) {
    if (!run || run.fetching.has(i) || run.urls[i] || i >= run.count) return;
    const r = run;
    r.fetching.add(i);
    try {
      const res = await fetch("/api/chunk", { method: "POST", signal: r.ctrl.signal,
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session: r.session, index: i }) });
      if (r !== run || r.stopped) return;
      if (res.status === 409) return;
      if (!res.ok) { fail(); return; }
      const blob = await res.blob();
      if (r !== run || r.stopped) return;
      r.durations[i] = parseFloat(res.headers.get("X-Duration"));
      r.urls[i] = URL.createObjectURL(blob);
      if (i === 0 && r.current === -1) playChunk(0);
      else if (r.waiting === i) { r.waiting = null; stallEnd(); playChunk(i); }
    } catch (e) {
      if (e.name !== "AbortError") fail();
    } finally { r.fetching.delete(i); }
  }

  function stallEnd() {
    if (run.stalled) { run.stalled = false; event("stall_end"); }
    buffering(false);
  }

  function playChunk(i) {
    run.current = i;
    audio.src = run.urls[i];
    buffering(false);
    if (!run.paused) audio.play().catch(() => { run.paused = true; setButtons(); action("pause"); });
    if (i === 0 && !run.started) { run.started = true; event("play_start"); }
    fetchChunk(i + 1);                    // lets the server prefetch one chunk ahead
    setButtons(); syncServerUi();
  }

  audio.addEventListener("timeupdate", () => {
    if (!run || run.current < 0 || run.failed || run.stopped) return;
    const a = activeSegment(run.current, audio.currentTime, run.durations[run.current]);
    paint(a);
    if (a !== null && a !== run.lastActive) { run.lastActive = a; scrollTo(a); }
  });

  audio.addEventListener("ended", () => {
    if (!run || run.stopped || run.failed) return;
    const next = run.current + 1;
    if (next < run.count) {
      if (run.urls[next]) playChunk(next);
      else {                             // next chunk not ready: buffering stall
        run.waiting = next; run.stalled = true; event("stall_start"); buffering(true);
        fetchChunk(next);
      }
    } else {
      run.done = true; paint(Infinity); event("ended"); setButtons(); syncServerUi();
    }
  });

  function start(meta) {
    if (run) release();
    audio.pause(); audio.removeAttribute("src");
    const lens = [...document.querySelectorAll("#vb-teleprompter .vb-chunk")].map((c) =>
      [...c.querySelectorAll(".vb-seg")].map((s) => Number(s.dataset.len)));
    run = { token: meta.dataset.run, session: meta.dataset.session, count: Number(meta.dataset.chunks),
            lens, urls: [], durations: [], fetching: new Set(), ctrl: new AbortController(),
            current: -1, waiting: null, paused: false, stalled: false, started: false,
            done: false, stopped: false, failed: false, lastActive: null };
    paint(null); setButtons(); syncServerUi();
    fetchChunk(0);
  }

  document.addEventListener("click", async (e) => {
    const id = e.target.closest("button") && e.target.closest("button").id;
    if (!id || !run) return;
    if (id === "vb-pause") {
      if (run.paused) {
        run.paused = false; action("resume");
        if (run.waiting === null && run.current >= 0 && !run.done) audio.play().catch(() => {});
        else if (run.waiting !== null && run.urls[run.waiting]) { const w = run.waiting; run.waiting = null; stallEnd(); playChunk(w); }
      } else { run.paused = true; audio.pause(); action("pause"); }
      setButtons(); syncServerUi();
    } else if (id === "vb-stop") {
      run.stopped = true; audio.pause(); audio.removeAttribute("src");
      release(); paint(null); buffering(false);
      await post("/api/stop", { session: run.session });
      setButtons(); syncServerUi();
    } else if (id === "vb-restart" || id === "vb-replay") {
      if (run.done) {                    // completed: replay from memory, no new request
        run.done = false; run.paused = false; run.current = -1; run.lastActive = null;
        if (!run.urls.length) return;
        action("replay"); playChunk(0);
      } else { const g = $("#vb-generate"); if (g && !g.disabled) g.click(); }
    } else if (id === "vb-download") {
      const a = document.createElement("a");
      a.href = `/api/audio?session=${encodeURIComponent(run.session)}`; a.download = "speech.wav";
      document.body.appendChild(a); a.click(); a.remove();
    }
  });

  new MutationObserver(() => {
    const meta = $("#vb-meta");
    if (meta && meta.dataset.run && (!run || run.token !== meta.dataset.run)) start(meta);
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true,
                                         attributeFilter: ["data-run"] });
})();
