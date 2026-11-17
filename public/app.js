// Obsidian-style map of PSE coffee chats: a d3-force layout drawn on canvas, with a pledge-class timeline to replay it.
(async function () {
  const params = new URLSearchParams(location.search);
  // ?capture renders the square light GIF frames for the deck; ?og renders the 1200x630 link-preview card
  const OG = params.has('og');
  const CAPTURE = params.has('capture') || OG;
  if (CAPTURE) document.body.classList.add('capture');

  // The site is dark; the recording for the slide is light and uses the deck's colours
  const THEMES = {
    dark: { bg: null, link: '#a18d7c', linkA: 0.15, dimA: 0.04, chi: '#2ebbb2', psi: '#a68cf4', omega: '#f08e4e', brother: '#d9cbb8', grad: '#6b5d51', glow: true, halo: 'rgba(21,16,12,.88)', label: '#e4d6c2', ring: '#fff' },
    light: { bg: '#ffffff', link: '#8f8178', linkA: 0.16, dimA: 0.05, chi: '#00918c', psi: '#7350b5', omega: '#c2571a', brother: '#3b2a21', grad: '#a3958a', glow: false, halo: 'rgba(255,255,255,.9)', label: '#241712', ring: '#241712' },
  };
  const T = OG ? { ...THEMES.dark, bg: '#15100c' } : THEMES[CAPTURE ? 'light' : 'dark'];
  const CLASS_COL = { Chi: T.chi, Psi: T.psi, Omega: T.omega };
  const NEW_CLASSES = ['Chi', 'Psi', 'Omega'];

  const data = await (await fetch('data.json')).json();
  const DAY = 864e5;
  const toDay = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / DAY;
  const day0 = toDay(data.chats[0][2]);
  const asDate = d => new Date((d + day0) * DAY);
  const fmtDay = d => asDate(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  const fmtShort = d => { const t = asDate(d); return t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }) + " '" + String(t.getUTCFullYear()).slice(2); };
  const fmtMonth = d => asDate(d).toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' });

  // ---------- model ----------
  const nodes = data.nodes.map((n, i) => ({ ...n, id: i, sent: [], recv: [], deg: 0, vdeg: 0 }));
  const color = n => CLASS_COL[n.cls] || (n.current ? T.brother : T.grad);
  const pairs = new Map();
  data.chats.forEach((c, i) => {
    c.i = i;
    const [s, t, , cls] = c;
    const d = (c.d = toDay(c[2]) - day0);
    nodes[s].sent.push({ other: t, d, cls });
    nodes[t].recv.push({ other: s, d, cls });
    const key = s + '-' + t;
    if (!pairs.has(key)) pairs.set(key, { source: s, target: t, cls, first: d, firstIdx: i });
  });
  const links = [...pairs.values()];
  links.forEach(l => { nodes[l.source].deg++; nodes[l.target].deg++; });
  const adj = nodes.map(() => new Set());
  links.forEach(l => { adj[l.source].add(l.target); adj[l.target].add(l.source); });

  // ---------- pledge-class timeline with the months between classes removed ----------
  const segs = NEW_CLASSES.map(cls => {
    const ds = data.chats.filter(c => c[3] === cls).map(c => c.d);
    return { cls, start: Math.min(...ds), end: Math.max(...ds) };
  });
  let off = 0;
  segs.forEach(s => { s.len = s.end - s.start + 1; s.off = off; off += s.len; });
  const TOTAL = off;
  const toC = d => { for (const s of segs) { if (d < s.start) return s.off; if (d <= s.end) return s.off + d - s.start; } return TOTAL - 1; };
  // Replays give each pledge class the same screen time and add a steady number of chats per frame,
  // so a class with a short semester (Omega) still grows smoothly instead of appearing in a burst
  const range = Object.fromEntries(NEW_CLASSES.map(cls => {
    const idx = data.chats.filter(c => c[3] === cls).map(c => c.i);
    return [cls, { a: Math.min(...idx), b: Math.max(...idx), fresh: Math.max(8, Math.round(idx.length * 0.05)) }];
  }));
  const kAt = p => {
    const i = Math.max(0, Math.min(NEW_CLASSES.length - 1, Math.floor(p * NEW_CLASSES.length)));
    const r = range[NEW_CLASSES[i]], f = Math.min(1, p * NEW_CLASSES.length - i);
    return Math.round(r.a + f * (r.b - r.a));
  };
  const pAt = k => {
    const i = NEW_CLASSES.indexOf(data.chats[k][3]), r = range[NEW_CLASSES[i]];
    return (i + (k - r.a) / Math.max(1, r.b - r.a)) / NEW_CLASSES.length;
  };
  const lastIdxOn = d => { let k = 0; for (const c of data.chats) if (c.d <= d) k = c.i; return k; };
  const fromC = c => { const s = segs.find(s => c < s.off + s.len) || segs[segs.length - 1]; return s.start + Math.min(s.len - 1, Math.max(0, c - s.off)); };

  const dl = document.getElementById('names');
  [...nodes].sort((a, b) => a.name.localeCompare(b.name)).forEach(n => dl.append(new Option(n.name)));

  // ---------- state ----------
  const state = { k: null, c: TOTAL - 1, day: segs[segs.length - 1].end, on: { Chi: true, Psi: true, Omega: true }, hover: null, sel: null, labels: false, playing: false, chats: 0, people: 0 };
  const rad = n => 2 + Math.sqrt(n.vdeg) * 0.8;

  function recount() {
    nodes.forEach(n => (n.vdeg = 0));
    links.forEach(l => {
      l.vis = (state.k != null ? l.firstIdx <= state.k : l.first <= state.day) && state.on[l.cls];
      if (l.vis) { l.source.vdeg++; l.target.vdeg++; }
    });
    state.chats = data.chats.reduce((a, c) => a + (state.on[c[3]] && (state.k != null ? c.i <= state.k : c.d <= state.day)), 0);
    state.people = nodes.filter(n => n.vdeg > 0).length;
    const st = document.getElementById('status');
    if (st) st.innerHTML = `${fmtDay(state.day)}: <b>${state.chats.toLocaleString()}</b> chats among <b>${state.people}</b> members`;
  }

  // ---------- layout ----------
  const canvas = document.getElementById('graph');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = 1;
  function resize() {
    if (CAPTURE) {
      W = OG ? 1200 : +(params.get('size') || 1080); H = OG ? 630 : W; dpr = OG ? 2 : 1;
      canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    } else {
      dpr = window.devicePixelRatio || 1; W = canvas.clientWidth; H = canvas.clientHeight;
    }
    canvas.width = W * dpr; canvas.height = H * dpr;
    drawSpark();
    draw();
  }

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(60).strength(0.06))
    .force('charge', d3.forceManyBody().strength(-140).distanceMax(600))
    .force('collide', d3.forceCollide(n => 2 + Math.sqrt(n.deg) * 0.8 + 4))
    .force('x', d3.forceX(0).strength(0.035))
    .force('y', d3.forceY(0).strength(0.035))
    .stop();
  for (let i = 0; i < 320; i++) sim.tick();
  if (!CAPTURE) sim.alpha(0.02).alphaDecay(0.03).on('tick', draw).restart();

  let transform = d3.zoomIdentity;
  const zoom = d3.zoom().scaleExtent([0.25, 8])
    .filter(e => e.type === 'wheel' || (!e.button && !(e.type === 'mousedown' && pick(e))))
    .on('zoom', e => { transform = e.transform; draw(); });
  const sel = d3.select(canvas).call(zoom).on('dblclick.zoom', null);

  const narrow = () => W <= 760;
  function fitView(ns, duration = 0) {
    // on the whole graph, fit the core and let a few far-flung dots fall off screen
    const xs = ns.map(n => n.x).sort(d3.ascending), ys = ns.map(n => n.y).sort(d3.ascending);
    const q = ns.length > 50 ? (CAPTURE ? 0.02 : 0.04) : 0;
    const [x0, x1, y0, y1] = [d3.quantile(xs, q), d3.quantile(xs, 1 - q), d3.quantile(ys, q), d3.quantile(ys, 1 - q)];
    const left = OG ? 600 : CAPTURE ? 50 : narrow() ? 16 : 60;
    const right = OG ? 20 : CAPTURE ? 50 : narrow() ? 16 : 390;
    const top = OG ? 20 : CAPTURE ? 130 : narrow() ? 130 : 150, bottom = OG ? 20 : CAPTURE ? 40 : narrow() ? 250 : 200;
    const k = Math.min(4, (W - left - right) / Math.max(40, x1 - x0), (H - top - bottom) / Math.max(40, y1 - y0));
    const t = d3.zoomIdentity.translate(left + (W - left - right) / 2, top + (H - top - bottom) / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    (duration ? sel.transition().duration(duration) : sel).call(zoom.transform, t);
  }

  // ---------- drawing ----------
  function focusSet(f) {
    if (f == null) return null;
    const s = new Set([f]);
    links.forEach(l => { if (l.vis && (l.source.id === f || l.target.id === f)) { s.add(l.source.id); s.add(l.target.id); } });
    return s;
  }
  const line = l => { ctx.beginPath(); ctx.moveTo(l.source.x, l.source.y); ctx.lineTo(l.target.x, l.target.y); ctx.stroke(); };

  function draw() {
    if (!W) return;
    const f = state.hover ?? state.sel;
    const focus = focusSet(f);
    const k = transform.k;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (T.bg) { ctx.fillStyle = T.bg; ctx.fillRect(0, 0, W, H); } else ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(k, k);

    // links: a quiet base layer, then chats from the last few days in their class colour, then the focused person's chats
    ctx.lineWidth = (CAPTURE ? 1.1 : 0.8) / Math.sqrt(k);
    ctx.strokeStyle = T.link;
    ctx.globalAlpha = focus ? T.dimA : T.linkA;
    // age runs 0 (just happened) to 1 (no longer new)
    const age = l => state.k != null ? (state.k - l.firstIdx) / range[l.cls].fresh : (state.day - l.first) / 6;
    const fresh = l => state.playing && age(l) < 1;
    for (const l of links) if (l.vis && !(focus && (l.source.id === f || l.target.id === f)) && !fresh(l)) line(l);
    if (state.playing) {
      ctx.lineWidth = (CAPTURE ? 1.8 : 1.2) / Math.sqrt(k);
      for (const l of links) {
        if (!l.vis || !fresh(l)) continue;
        ctx.globalAlpha = 0.95 - age(l) * 0.65;
        ctx.strokeStyle = CLASS_COL[l.cls];
        line(l);
      }
    }
    if (focus) {
      ctx.lineWidth = 1.6 / Math.sqrt(k);
      ctx.globalAlpha = 0.9;
      for (const l of links) if (l.vis && (l.source.id === f || l.target.id === f)) { ctx.strokeStyle = CLASS_COL[l.cls]; line(l); }
    }

    // nodes: new member classes glow softly on the dark site
    for (const n of nodes) {
      if (n.vdeg === 0 && n.id !== state.sel) continue;
      const r = rad(n);
      const dim = focus && !focus.has(n.id);
      ctx.globalAlpha = dim ? 0.12 : 1;
      ctx.fillStyle = color(n);
      if (T.glow && !dim && CLASS_COL[n.cls]) { ctx.shadowColor = color(n); ctx.shadowBlur = 10 * Math.min(1.5, k); }
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
      if (n.id === state.sel || n.id === state.hover) {
        ctx.globalAlpha = 1; ctx.lineWidth = 2 / k; ctx.strokeStyle = T.ring;
        ctx.beginPath(); ctx.arc(n.x, n.y, r + 3 / k, 0, Math.PI * 2); ctx.stroke();
      }
    }
    ctx.restore();

    // labels in screen space so text stays crisp at every zoom level
    ctx.globalAlpha = 1;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const minDeg = state.labels ? 0 : k > 3 ? 0 : k > 1.8 ? 18 : Infinity;
    for (const n of nodes) {
      if (n.vdeg === 0 || CAPTURE) continue;
      const inFocus = focus && focus.has(n.id);
      if (focus ? !inFocus || (focus.size > 40 && n.id !== f && k < 1.4) : n.vdeg < minDeg) continue;
      const [sx, sy] = transform.apply([n.x, n.y]);
      if (sx < -80 || sx > W + 80 || sy < -20 || sy > H + 20) continue;
      const main = n.id === f;
      ctx.font = `${main ? 650 : 500} ${main ? 15 : 12.5}px "Bricolage Grotesque", system-ui, sans-serif`;
      ctx.lineWidth = 3; ctx.strokeStyle = T.halo;
      ctx.strokeText(n.name, sx, sy + rad(n) * k + 4);
      ctx.fillStyle = main ? T.ring : T.label;
      ctx.fillText(n.name, sx, sy + rad(n) * k + 4);
    }
    if (OG) drawCard(); else if (CAPTURE) drawCaption();
  }

  // link-preview card: the title set like the site's masthead, with the finished network on the right
  function drawCard() {
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#eee1cd';
    ctx.font = '780 92px "Bricolage Grotesque", sans-serif';
    ['Who coffee', 'chats whom'].forEach((t, i) => ctx.fillText(t, 64, 210 + i * 86));
    ctx.fillStyle = '#a18d7c';
    ctx.font = '500 30px "Bricolage Grotesque", sans-serif';
    ['2,301 coffee chats among 166', 'members of PSE at the University', 'of Michigan, mapped one by one.'].forEach((t, i) => ctx.fillText(t, 66, 370 + i * 42));
    const dots = [['Chi', T.chi], ['Psi', T.psi], ['Omega', T.omega]];
    let x = 66;
    ctx.font = '600 26px "Bricolage Grotesque", sans-serif';
    dots.forEach(([t, c]) => {
      ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x + 8, 552, 8, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#eee1cd'; ctx.fillText(t, x + 26, 561);
      x += 26 + ctx.measureText(t).width + 30;
    });
  }

  // the recording carries its own caption: which pledge class is chatting, the date, and the running total
  function drawCaption() {
    const seg = segs.find(s => state.day >= s.start && state.day <= s.end) || segs[segs.length - 1];
    const s = W / 1080;
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = CLASS_COL[seg.cls];
    ctx.font = `760 ${56 * s}px "Bricolage Grotesque", sans-serif`;
    ctx.fillText(seg.cls, 46 * s, 86 * s);
    const w = ctx.measureText(seg.cls).width;
    ctx.fillStyle = T.label;
    ctx.font = `500 ${30 * s}px "Bricolage Grotesque", sans-serif`;
    ctx.fillText(fmtDay(state.day), 46 * s + w + 18 * s, 84 * s);
    ctx.textAlign = 'right';
    ctx.font = `650 ${30 * s}px "Bricolage Grotesque", sans-serif`;
    ctx.fillText(`${state.chats.toLocaleString()} chats`, W - 46 * s, 84 * s);
  }

  // ---------- pointer ----------
  const graphPoint = e => transform.invert(d3.pointer(e, canvas));
  function pick(e) {
    const [x, y] = graphPoint(e);
    let best = null, bd = Infinity;
    for (const n of nodes) {
      if (n.vdeg === 0) continue;
      const d = Math.hypot(n.x - x, n.y - y);
      if (d < rad(n) + 6 / transform.k && d < bd) { best = n; bd = d; }
    }
    return best;
  }
  canvas.addEventListener('mousemove', e => {
    const n = pick(e);
    canvas.classList.toggle('pointing', !!n);
    const id = n ? n.id : null;
    if (id !== state.hover) { state.hover = id; draw(); }
  });
  canvas.addEventListener('mouseleave', () => { state.hover = null; draw(); });
  canvas.addEventListener('click', e => { if (!e.defaultPrevented) { const n = pick(e); select(n ? n.id : null); } });
  sel.call(d3.drag()
    .container(canvas)
    .filter(e => !e.button && pick(e))
    .subject(e => pick(e))
    .on('start', e => { sim.alphaTarget(0.25).restart(); e.subject.fx = e.subject.x; e.subject.fy = e.subject.y; })
    .on('drag', e => { const [x, y] = graphPoint(e.sourceEvent); e.subject.fx = x; e.subject.fy = y; })
    .on('end', e => { sim.alphaTarget(0); e.subject.fx = null; e.subject.fy = null; }));

  // ---------- side panel ----------
  const panel = document.getElementById('panel');
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const rowList = (items, label) => items.length ? `<h3>${label}</h3><ul class="rows">${items
    .sort((a, b) => a.d - b.d)
    .map(c => `<li class="${c.d > state.day || !state.on[c.cls] ? 'later' : ''}"><i style="--c:${CLASS_COL[c.cls]}"></i><button data-id="${c.other}">${esc(nodes[c.other].name)}</button><time>${fmtShort(c.d)}</time></li>`)
    .join('')}</ul>` : '';

  function overview() {
    panel.classList.add('overview');
    panel.innerHTML = `
      <p class="lede">Hover a dot to see who that person met, and click to keep them selected. Drag to move dots and scroll to zoom.</p>
      <ul class="tries">
        <li><button data-act="replay">Replay the year</button><p>Watch Chi, then Psi, then Omega build the network one chat at a time.</p></li>
        <li><button data-act="psi">Show only Psi</button><p>Each class leans toward the class two above it. For Psi, that's Phi.</p></li>
        <li><button data-act="boyle">Find Mikaela B.</button><p>The president met 48 of 59 new members, nine more than anyone else.</p></li>
        <li><button data-act="omega">Show only Omega</button><p>Omega reached 88 of 102 current brothers through November 7.</p></li>
      </ul>`;
  }

  function details(n) {
    panel.classList.remove('overview');
    const met = new Set(n.sent.map(c => c.other)).size;
    const by = new Set(n.recv.map(c => c.other)).size;
    const tag = n.current ? `${n.cls}${n.grade ? ', ' + n.grade.toLowerCase() : ''}` : 'Graduated';
    const parts = [];
    if (met) parts.push(`met <b>${met}</b> brothers as a new member`);
    if (by) parts.push(`${met ? 'has since met' : 'met'} <b>${by}</b> new members`);
    panel.innerHTML = `
      <button class="close" aria-label="Close">×</button>
      <h2>${esc(n.name)}</h2>
      <p class="who"><i style="--c:${color(n)}"></i>${tag}</p>
      <p class="summary">${esc(n.name.split(' ')[0])} ${parts.join(' and ')}.</p>
      ${rowList(n.sent.slice(), `Brothers met as a new member`)}
      ${rowList(n.recv.slice(), `New members who chatted with ${esc(n.name.split(' ')[0])}`)}`;
  }

  function select(id, zoomTo = false) {
    state.sel = id;
    if (id == null) overview(); else details(nodes[id]);
    if (id != null && zoomTo) fitView([...adj[id]].map(i => nodes[i]).concat(nodes[id]), 700);
    draw();
  }

  panel.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.classList.contains('close')) return select(null);
    if (b.dataset.id) return select(+b.dataset.id, true);
    const act = b.dataset.act;
    if (act === 'replay') { setClasses(NEW_CLASSES); setC(0); play(true); }
    if (act === 'psi') { setClasses(['Psi']); setC(TOTAL - 1); }
    if (act === 'omega') { setClasses(['Omega']); setC(TOTAL - 1); }
    if (act === 'boyle') { setClasses(NEW_CLASSES); setC(TOTAL - 1); const n = nodes.find(n => n.name === 'Mikaela B.'); if (n) select(n.id, true); }
  });
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !document.querySelector('dialog[open]')) select(null);
    if (e.key === ' ' && e.target === document.body) { e.preventDefault(); play(!state.playing); }
  });

  // ---------- search ----------
  const search = document.getElementById('search');
  search.addEventListener('change', () => {
    const q = search.value.trim().toLowerCase();
    if (!q) return;
    const n = nodes.find(n => n.name.toLowerCase() === q) || nodes.find(n => n.name.toLowerCase().includes(q));
    if (!n) return;
    if (n.vdeg === 0) { setClasses(NEW_CLASSES); setC(TOTAL - 1); }
    select(n.id, true);
    search.blur();
  });

  // ---------- filters ----------
  const keys = [...document.querySelectorAll('.key[data-cls]')];
  function setClasses(list) {
    NEW_CLASSES.forEach(c => (state.on[c] = list.includes(c)));
    keys.forEach(b => { b.classList.toggle('on', state.on[b.dataset.cls]); b.setAttribute('aria-pressed', state.on[b.dataset.cls]); });
    recount(); drawSpark(); draw();
    if (state.sel != null) details(nodes[state.sel]);
  }
  keys.forEach(b => b.addEventListener('click', () => {
    const c = b.dataset.cls;
    const next = NEW_CLASSES.filter(x => (x === c ? !state.on[x] : state.on[x]));
    setClasses(next.length ? next : [c]);
  }));
  const labelsBtn = document.getElementById('labels');
  labelsBtn.addEventListener('click', () => { state.labels = !state.labels; labelsBtn.setAttribute('aria-pressed', state.labels); draw(); });
  const about = document.getElementById('about');
  document.getElementById('about-btn').addEventListener('click', () => about.showModal());

  // ---------- timeline ----------
  const slider = document.getElementById('day');
  slider.max = TOTAL - 1;
  slider.value = TOTAL - 1;
  document.getElementById('segments').innerHTML = segs.map(s =>
    `<div style="flex:${s.len}"><b>${s.cls}</b><span>${fmtMonth(s.start)} to ${fmtMonth(s.end)} ${asDate(s.end).getUTCFullYear()}</span></div>`).join('');

  function setK(k) {
    state.k = k;
    state.day = data.chats[k].d;
    state.c = toC(state.day);
    slider.value = state.c;
    recount(); drawSpark(); draw();
  }
  function setC(c) {
    state.k = null;
    state.c = Math.max(0, Math.min(TOTAL - 1, Math.round(c)));
    state.day = fromC(state.c);
    slider.value = state.c;
    recount(); drawSpark(); draw();
    if (state.sel != null && !state.playing) details(nodes[state.sel]);
  }
  slider.addEventListener('input', () => { play(false); setC(+slider.value); });

  const spark = document.getElementById('spark');
  const sctx = spark.getContext('2d');
  const bins = [];
  segs.forEach(s => { for (let w = 0; w * 7 < s.len; w++) bins.push({ cls: s.cls, c0: s.off + w * 7, c1: Math.min(s.off + s.len, s.off + w * 7 + 7), n: 0 }); });
  data.chats.forEach(c => { const cc = toC(c.d); const b = bins.find(b => cc >= b.c0 && cc < b.c1); if (b) b.n++; });
  const binMax = Math.max(...bins.map(b => b.n));
  function drawSpark() {
    const w = spark.clientWidth, h = spark.clientHeight;
    if (!w || CAPTURE) return;
    spark.width = w * dpr; spark.height = h * dpr;
    sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    sctx.clearRect(0, 0, w, h);
    const x = c => (c / TOTAL) * w;
    for (const b of bins) {
      if (!state.on[b.cls] || !b.n) continue;
      const bh = Math.max(2, (b.n / binMax) * (h - 4));
      sctx.globalAlpha = b.c0 <= state.c ? 0.95 : 0.22;
      sctx.fillStyle = CLASS_COL[b.cls];
      sctx.fillRect(x(b.c0) + 1, h - bh, Math.max(1, x(b.c1) - x(b.c0) - 2), bh);
    }
    sctx.globalAlpha = 1;
    sctx.fillStyle = '#64554a';
    segs.slice(1).forEach(s => sctx.fillRect(x(s.off) - 0.5, 0, 1, h));
    sctx.fillStyle = '#eee1cd';
    sctx.fillRect(Math.min(w - 2, x(state.c)), 0, 2, h);
  }
  const seek = e => { const r = spark.getBoundingClientRect(); play(false); setC(((e.clientX - r.left) / r.width) * TOTAL); };
  spark.addEventListener('pointerdown', e => { seek(e); spark.setPointerCapture(e.pointerId); });
  spark.addEventListener('pointermove', e => { if (e.buttons) seek(e); });

  // replay takes about 16 seconds end to end, a third per pledge class
  const playBtn = document.getElementById('play');
  const icon = document.getElementById('play-icon');
  let raf = 0;
  function play(on) {
    state.playing = on;
    icon.setAttribute('d', on ? 'M7 5h4v14H7zM13 5h4v14h-4z' : 'M8 5v14l11-7z');
    playBtn.setAttribute('aria-label', on ? 'Pause' : 'Replay the chats');
    cancelAnimationFrame(raf);
    if (!on) { draw(); if (state.sel != null) details(nodes[state.sel]); return; }
    // resume from the current point, or start over if the replay already reached the end
    let p = state.c >= TOTAL - 1 ? 0 : pAt(state.k ?? lastIdxOn(state.day));
    let shown = -1, last = performance.now();
    const step = now => {
      p += Math.max(0, Math.min(64, now - last)) / 16000; last = now;
      const k = kAt(Math.min(1, p));
      if (k !== shown) { setK(k); shown = k; }
      if (p >= 1) return play(false);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }
  playBtn.addEventListener('click', () => play(!state.playing));

  // ---------- recording hook: step the timeline and hand each frame to the local capture server ----------
  // only on a local machine, where pipeline/capture_server.py is listening
  if (['localhost', '127.0.0.1'].includes(location.hostname)) window.captureFrames = async (frames = 150, hold = 30) => {
    await document.fonts.ready;
    state.playing = true;
    const post = async i => {
      const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
      await fetch('/frame?i=' + i, { method: 'POST', body: blob });
    };
    for (let i = 0; i < frames; i++) { setK(kAt(i / (frames - 1))); await post(i); }
    state.playing = false; draw();
    for (let i = 0; i < hold; i++) await post(frames + i);
    return frames + hold;
  };

  // ---------- go ----------
  window.addEventListener('resize', () => { if (!CAPTURE) resize(); });
  recount();
  overview();
  resize();
  fitView(nodes);
  // canvas text needs the web font; redraw recordings once it has loaded
  if (CAPTURE) document.fonts.ready.then(draw);
})();
