"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (p) => (p == null ? "–" : Math.round(p * 100) + " %");
const pClass = (p) => (p >= 0.8 ? "hi" : p >= 0.5 ? "mid" : "lo");
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("cs-CZ") : "");
const fmtDT = (s) => (s ? new Date(s).toLocaleString("cs-CZ", { dateStyle: "short", timeStyle: "short" }) : "");

const state = { me: null, meta: null, center: null, results: [], nace: new Set(), map: null, layer: null, circle: null, centerMarker: null, selected: null, job: null };

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    credentials: "same-origin",
  });
  if (res.status === 401 && !path.includes("/login")) { showLogin(); throw new Error("Nepřihlášen"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Chyba ${res.status}`);
  return data;
}

function toast(msg, ms = 3200) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}

// ------------------------------------------------------------------ přihlášení
function showLogin() { $("#app").classList.add("hidden"); $("#login").classList.remove("hidden"); }

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/login", { body: { username: f.get("username"), password: f.get("password") } });
    $("#login-error").textContent = "";
    boot();
  } catch (err) { $("#login-error").textContent = err.message; }
});
$("#logout").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }); location.reload(); });

async function boot() {
  try { state.me = await api("/api/me"); } catch { return showLogin(); }
  $("#login").classList.add("hidden"); $("#app").classList.remove("hidden");
  $("#user-name").textContent = state.me.display_name + (state.me.is_admin ? " · admin" : "");
  $("#admin-panel").classList.toggle("hidden", !state.me.is_admin);
  $("#products-panel").classList.toggle("hidden", !state.me.is_admin);
  $("#brand-panel").classList.toggle("hidden", !state.me.is_admin);
  state.meta = await api("/api/meta");
  $("#demo-badge").classList.toggle("hidden", !state.meta.demo);
  showImport(state.meta.import);
  setInqCount(state.meta.inquiries_new);
  if (location.hash === "#poptavky") $('.tab[data-view="inquiries"]').click();
  $("#data-info").textContent = `${state.meta.firms.toLocaleString("cs-CZ")} firem s polohou · data RES: ${state.meta.res_imported_at || "neimportováno"}` +
    (state.meta.google ? "" : " · Google Places není nastaven");
  $("#enrich-n").max = state.meta.enrich_max;
  renderForms(); renderNace(); initMap(); restoreFilters();
}

// ------------------------------------------------------------------ filtry
function renderForms() {
  $("#forms").innerHTML = state.meta.forms.map((f) =>
    `<label class="check"><input type="checkbox" name="form" value="${esc(f.key)}" checked> ${esc(f.label)}</label>`).join("");
}
function renderNace() {
  $("#nace-list").innerHTML = state.meta.nace.map((n) =>
    `<label class="check" data-label="${esc(n.label.toLowerCase())} ${n.code}"><input type="checkbox" value="${n.code}"> <span class="mono muted">${n.code}</span> ${esc(n.label)}</label>`).join("");
  $("#nace-list").addEventListener("change", (e) => {
    if (e.target.checked) state.nace.add(e.target.value); else state.nace.delete(e.target.value);
    updateNaceCount();
  });
}
function setNace(codes) {
  state.nace = new Set(codes);
  $$("#nace-list input").forEach((i) => (i.checked = state.nace.has(i.value)));
  updateNaceCount();
}
function updateNaceCount() {
  const v = state.meta.preset_venues;
  const isVenues = state.nace.size === v.length && v.every((c) => state.nace.has(c));
  $("#nace-count").textContent = isVenues ? "kadeřnictví, kavárny, restaurace" : state.nace.size ? `vybráno ${state.nace.size}` : "všechny";
}
$("#preset-local").addEventListener("click", () => setNace(state.meta.preset_local));
$("#preset-venues").addEventListener("click", () => setNace(state.meta.preset_venues));
$("#preset-all").addEventListener("click", () => setNace([]));
$("#nace-filter").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  $$("#nace-list .check").forEach((l) => l.classList.toggle("hidden", q && !l.dataset.label.includes(q)));
});
$("#radius").addEventListener("input", (e) => { $("#radius-out").textContent = e.target.value + " km"; drawCircle(); });
$("#minp").addEventListener("input", (e) => { $("#minp-out").textContent = e.target.value + " %"; });

function filtersFromForm() {
  const [minS, maxS] = $("#staff").value.split("-").map(Number);
  return {
    lat: state.center?.lat, lon: state.center?.lon, center_name: state.center?.name,
    radius_km: Number($("#radius").value),
    forms: $$('#forms input:checked').map((i) => i.value),
    nace: [...state.nace],
    min_staff: minS, max_staff: maxS,
    min_p_noweb: Number($("#minp").value) / 100,
    hide_worked: $("#hide-worked").checked,
    only_enriched: $("#only-enriched").checked,
    staff_value: $("#staff").value,
  };
}
function saveFilters(f) { try { localStorage.setItem("lf-filters", JSON.stringify(f)); } catch {} }
function restoreFilters() {
  let f = null;
  try { f = JSON.parse(localStorage.getItem("lf-filters") || "null"); } catch {}
  if (!f) return;
  if (f.lat) setCenter({ lat: f.lat, lon: f.lon, name: f.center_name }, false);
  $("#radius").value = f.radius_km; $("#radius-out").textContent = f.radius_km + " km";
  $$("#forms input").forEach((i) => (i.checked = f.forms.includes(i.value)));
  setNace(f.nace || []);
  if (f.staff_value) $("#staff").value = f.staff_value;
  $("#minp").value = Math.round((f.min_p_noweb || 0) * 100); $("#minp-out").textContent = $("#minp").value + " %";
  $("#hide-worked").checked = f.hide_worked; $("#only-enriched").checked = f.only_enriched;
  drawCircle();
  if (f.lat) runSearch();
}

// obec – našeptávač
let acTimer;
$("#obec").addEventListener("input", (e) => {
  clearTimeout(acTimer);
  const q = e.target.value.trim();
  if (q.length < 2) return $("#obec-list").classList.add("hidden");
  acTimer = setTimeout(async () => {
    const items = await api("/api/obce?q=" + encodeURIComponent(q));
    const ul = $("#obec-list");
    ul.innerHTML = items.map((o, i) => `<li data-i="${i}"><span>${esc(o.name)}</span><span class="muted tiny">${o.n} firem</span></li>`).join("") ||
      '<li class="muted">Nic nenalezeno</li>';
    ul.classList.remove("hidden");
    ul.onclick = (ev) => {
      const li = ev.target.closest("li[data-i]"); if (!li) return;
      const o = items[li.dataset.i];
      setCenter({ lat: o.lat, lon: o.lon, name: o.name });
      $("#obec").value = o.name; ul.classList.add("hidden");
    };
  }, 200);
});
document.addEventListener("click", (e) => { if (!e.target.closest(".autocomplete")) $("#obec-list").classList.add("hidden"); });

// ------------------------------------------------------------------ mapa
function initMap() {
  if (state.map) return;
  state.map = L.map("map", { preferCanvas: true }).setView([49.8, 15.5], 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(state.map);
  state.layer = L.layerGroup().addTo(state.map);
  state.map.on("click", (e) => setCenter({ lat: e.latlng.lat, lon: e.latlng.lng, name: null }));
}
function setCenter(c, fly = true) {
  state.center = c;
  $("#center-label").textContent = c.name ? `Střed: ${c.name}` : `Střed: ${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}`;
  if (c.name) $("#obec").value = c.name;
  if (state.centerMarker) state.centerMarker.remove();
  state.centerMarker = L.circleMarker([c.lat, c.lon], { radius: 6, color: "#111111", weight: 2, fillOpacity: 1, fillColor: "#FF2D2D" }).addTo(state.map);
  drawCircle();
  if (fly) state.map.fitBounds(state.circle.getBounds(), { padding: [20, 20] });
}
function drawCircle() {
  if (!state.center || !state.map) return;
  const r = Number($("#radius").value) * 1000;
  if (state.circle) state.circle.setRadius(r);
  else state.circle = L.circle([state.center.lat, state.center.lon], { radius: r, color: "#111111", weight: 1.5, dashArray: "6 5", fillOpacity: 0.03 }).addTo(state.map);
  state.circle.setLatLng([state.center.lat, state.center.lon]);
}
const markerColor = (p) => (p >= 0.8 ? "#FF2D2D" : p >= 0.5 ? "#E0A100" : "#9A9A95");

function renderMarkers() {
  state.layer.clearLayers();
  state.results.slice(0, 2000).forEach((r) => {
    const m = L.circleMarker([r.lat, r.lon], {
      radius: r.enriched ? 6 : 4.5, color: "#fff", weight: 1, fillOpacity: 0.9, fillColor: markerColor(r.p_noweb),
    });
    m.bindTooltip(`${esc(r.nazev)}<br>bez webu ${pct(r.p_noweb)} · živost ${Math.round(r.vitality)}`);
    m.on("click", () => openFirm(r.ico));
    m.addTo(state.layer);
  });
}

// ------------------------------------------------------------------ hledání
$("#search-form").addEventListener("submit", (e) => { e.preventDefault(); runSearch(); });

async function runSearch() {
  if (!state.center) return toast("Vyberte obec nebo klikněte do mapy.");
  const f = filtersFromForm();
  saveFilters(f);
  $("#result-count").textContent = "Hledám…";
  try {
    const res = await api("/api/search", { body: { ...f, limit: 3000 } });
    state.results = res.results;
    $("#result-count").textContent = `${res.total.toLocaleString("cs-CZ")} firem`;
    $("#result-note").textContent = res.total > res.results.length ? `(zobrazeno ${res.results.length} nejlepších)` : "";
    renderResults(); renderMarkers();
    $("#enrich-btn").disabled = $("#export-btn").disabled = !res.results.length;
  } catch (err) { $("#result-count").textContent = "Chyba"; toast(err.message); }
}

function statusBadge(lead) {
  if (!lead || lead.status === "new") return "";
  const who = lead.owner ? ` · ${esc(lead.owner)}` : "";
  return `<span class="badge ${esc(lead.status)} ${lead.mine ? "mine" : ""}">${esc(lead.status_label)}${who}</span>`;
}

function renderResults() {
  const tb = $("#results-body");
  if (!state.results.length) { tb.innerHTML = '<tr><td colspan="7" class="empty">Nic nenalezeno – zkuste větší okruh nebo méně filtrů.</td></tr>'; return; }
  tb.innerHTML = state.results.slice(0, 1000).map((r) => `
    <tr data-ico="${r.ico}" class="${state.selected === r.ico ? "selected" : ""}">
      <td><span class="pct">${Math.round(r.priority)}</span><div class="pbar"><span style="width:${Math.min(100, r.priority)}%"></span></div></td>
      <td><div class="firm-name">${esc(r.nazev)}</div><div class="sub">${esc(r.adresa || "")}</div></td>
      <td class="sub">${esc(r.nace_label)}<br>${esc(/\d/.test(r.staff) ? r.staff + " zam." : r.staff)}</td>
      <td class="pct">${r.dist_km.toFixed(1)} km</td>
      <td><span class="pct ${pClass(r.p_noweb)}">${pct(r.p_noweb)}</span>${r.enriched ? "" : '<div class="est">odhad</div>'}</td>
      <td class="pct">${Math.round(r.vitality)}</td>
      <td>${statusBadge(r.lead)}</td>
    </tr>`).join("");
}
$("#results-body").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-ico]"); if (tr) openFirm(tr.dataset.ico); });

// ------------------------------------------------------------------ obohacení
$("#enrich-btn").addEventListener("click", async () => {
  const n = Math.min(Number($("#enrich-n").value) || 50, state.meta.enrich_max);
  const icos = state.results.filter((r) => !r.enriched).slice(0, n).map((r) => r.ico);
  if (!icos.length) return toast("Všechny zobrazené firmy už jsou ověřené.");
  try {
    const job = await api("/api/enrich", { body: { icos } });
    pollJob(job.id);
  } catch (err) { toast(err.message); }
});

async function pollJob(id) {
  $("#job").classList.remove("hidden"); $("#enrich-btn").disabled = true;
  const tick = async () => {
    const j = await api("/api/jobs/" + id);
    $("#job .job-bar span").style.width = (100 * j.done / j.total) + "%";
    $("#job small").textContent = `Ověřuji ${j.done} / ${j.total}` + (j.error_count ? ` · ${j.error_count} chyb (${j.errors.slice(-1)[0]})` : "");
    if (j.status === "done") {
      $("#enrich-btn").disabled = false;
      toast(`Ověřeno ${j.total} firem` + (j.error_count ? `, ${j.error_count} s chybou` : ""));
      setTimeout(() => $("#job").classList.add("hidden"), 4000);
      runSearch();
    } else setTimeout(tick, 1000);
  };
  tick();
}

// ------------------------------------------------------------------ export
$("#export-btn").addEventListener("click", () => {
  const head = ["ICO", "Nazev", "Adresa", "Obec", "Obor", "Zamestnanci", "Vzdalenost_km", "P_bez_webu", "Zivost", "Priorita", "Overeno", "Stav", "Resitel"];
  const rows = state.results.map((r) => [r.ico, r.nazev, r.adresa, r.obec, r.nace_label, r.staff, r.dist_km, r.p_noweb, r.vitality, r.priority,
    r.enriched ? "ano" : "ne", r.lead?.status_label || "", r.lead?.owner || ""]);
  const csv = [head, ...rows].map((row) => row.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `firmy-bez-webu-${new Date().toISOString().slice(0, 10)}.csv`; a.click();
});

// ------------------------------------------------------------------ detail
$("#drawer-close").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
function closeDrawer() { $("#drawer").classList.add("hidden"); state.selected = null; inqOpen = null; $$("tr.selected").forEach((t) => t.classList.remove("selected")); }

async function openFirm(ico) {
  state.selected = ico;
  $$("#results-body tr").forEach((t) => t.classList.toggle("selected", t.dataset.ico === ico));
  $("#drawer").classList.remove("hidden");
  $("#drawer-content").innerHTML = '<p class="muted">Načítám…</p>';
  try { renderFirm(await api("/api/firm/" + ico)); } catch (err) { $("#drawer-content").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
}

function reasonList(reasons, kind) {
  return '<ul class="reasons">' + reasons.filter((r) => r.kind === kind).map((r) => {
    const w = r.w === 0 ? "" : (r.w > 0 ? "+" : "") + r.w;
    const cls = kind === "web" ? (r.w > 0 ? "pos" : "neg") : (r.w > 0 ? "neg" : "pos");
    return `<li><span class="w ${cls}">${w}</span><span>${esc(r.text)}</span></li>`;
  }).join("") + "</ul>";
}

function renderFirm(d) {
  const f = d.firm, s = d.score, g = d.google, lead = d.lead;
  const contactHtml = d.contacts.length ? '<ul class="contacts">' + d.contacts.map((c) => {
    const href = c.type === "phone" ? `tel:${c.value.replace(/\s/g, "")}` : c.type === "email" ? `mailto:${c.value}` : null;
    const label = { phone: "Telefon", email: "E-mail", ds: "Datová schránka" }[c.type];
    return `<li><div><div class="sub">${label} · ${esc(c.source)}</div><div class="val">${href ? `<a href="${esc(href)}">${esc(c.value)}</a>` : esc(c.value)}</div></div></li>`;
  }).join("") + "</ul>" : `<p class="muted">Zatím žádný kontakt. ${d.enriched ? "Zkuste odkazy níže (Firmy.cz, Google)." : "Klikněte na Ověřit."}</p>`;

  const webInfo = d.web ? ({
    ico: `Nalezen web s IČO firmy: <a href="${esc(d.web.url)}" target="_blank" rel="noopener">${esc(d.web.url)}</a>`,
    name: `Nalezen web odpovídající názvu: <a href="${esc(d.web.url)}" target="_blank" rel="noopener">${esc(d.web.url)}</a>`,
    parked: `Doména existuje, ale je zaparkovaná / prázdná: ${esc(d.web.url)}`,
    other: "Odhadnuté domény patří jiným subjektům.",
    none: "Žádná z odhadnutých domén neexistuje.",
  }[d.web.match] || "") : "Neověřeno.";

  const googleInfo = g ? `
    <dl class="kv">
      <dt>Název na Googlu</dt><dd>${esc(g.name)}</dd>
      <dt>Web</dt><dd>${g.website ? `<a href="${esc(g.website)}" target="_blank" rel="noopener">${esc(g.website)}</a>` : "<b>neuveden</b>"}</dd>
      <dt>Hodnocení</dt><dd>${g.rating ? `${g.rating} ★ (${g.reviews} recenzí)` : "bez recenzí"}</dd>
      <dt>Stav</dt><dd>${esc(g.status || "")}</dd>
      ${g.hours ? `<dt>Otevírací doba</dt><dd>${g.hours.map(esc).join("<br>")}</dd>` : ""}
      ${g.maps_url ? `<dt></dt><dd><a href="${esc(g.maps_url)}" target="_blank" rel="noopener">Otevřít v Google Mapách</a></dd>` : ""}
    </dl>` : `<p class="muted">${{ not_found: "Na Google Mapách nenalezeno.", matched: "Údaje z Googlu se nepodařilo načíst." + (d.google_error ? " " + esc(d.google_error) : ""), unchecked: "Neověřeno." }[d.google_status]}</p>`;

  const a = d.ares;
  const aresInfo = a ? `<dl class="kv">
      <dt>Plátce DPH</dt><dd>${a.dph ? "ano" : "ne"}${a.dic ? ` <span class="muted mono">${esc(a.dic)}</span>` : ""}</dd>
      <dt>Insolvence</dt><dd>${a.insolvence ? '<b class="error">ano</b>' : "ne"}</dd>
      ${a.likvidace ? "<dt>Likvidace</dt><dd><b class=error>v likvidaci</b></dd>" : ""}
      ${a.www ? `<dt>Web v registru</dt><dd>${esc(a.www)}</dd>` : ""}
    </dl>` : '<p class="muted">Neověřeno.</p>';

  const taken = lead.claimed && !lead.mine;
  const outcomes = Object.entries(state.meta.outcomes).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  const channels = Object.entries(state.meta.channels).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  const crm = `
    <div class="crm-box">
      <div class="crm-head">
        <div><span class="badge ${esc(lead.status)}">${esc(lead.status_label)}</span>
          ${lead.owner ? `<span class="muted"> · ${esc(lead.owner)}${lead.claimed_until && lead.claimed ? ` do ${fmtDate(lead.claimed_until)}` : ""}</span>` : ""}</div>
        <div>${lead.mine ? '<button class="btn small ghost" id="release-btn">Uvolnit</button>'
          : taken ? "" : lead.status === "do_not_contact" ? "" : '<button class="btn small primary" id="claim-btn">Rezervovat pro mě</button>'}</div>
      </div>
      ${taken ? `<div class="notice">Firmu má rozpracovanou ${esc(lead.owner)} – neoslovujte ji, prosím.</div>` : ""}
      ${lead.status === "do_not_contact" ? '<div class="notice">Firma si nepřeje být kontaktována.</div>' : ""}
      ${!taken && lead.status !== "do_not_contact" ? `
      <form id="activity-form">
        <div class="grid2">
          <label>Kanál<select name="channel">${channels}</select></label>
          <label>Výsledek<select name="outcome">${outcomes}</select></label>
        </div>
        <label>Poznámka<textarea name="note" placeholder="Co jste domluvili, s kým jste mluvili…"></textarea></label>
        <div class="grid2">
          <label>Další krok<input type="date" name="next_action" value="${esc(lead.next_action || "")}"></label>
          <div class="row" style="align-items:flex-end"><button class="btn primary wide" type="submit">Zapsat oslovení</button></div>
        </div>
      </form>
      <label style="margin-top:10px">Získané kontakty (jméno, mobil, e-mail)
        <textarea id="contact-note" placeholder="např. jednatel p. Novák, 777 123 456">${esc(lead.contact_note || "")}</textarea></label>
      <button class="btn small" id="save-contact">Uložit kontakty</button>` : ""}
      ${lead.activities.length ? '<ul class="timeline">' + lead.activities.map((x) => `
        <li><b>${esc(x.outcome_label)}</b> · ${esc(x.channel_label)} · ${esc(x.user)} <span class="muted">${fmtDT(x.ts)}</span>
        ${x.note ? `<div>${esc(x.note)}</div>` : ""}</li>`).join("") + "</ul>" : ""}
    </div>`;

  $("#drawer-content").innerHTML = `
    <h2>${esc(f.nazev)}</h2>
    <div class="muted">${esc(f.adresa || "")}</div>
    <div class="scores">
      <div class="score-card"><div class="sub">Pravděpodobnost bez webu</div><div class="big ${pClass(s.p_noweb)}">${pct(s.p_noweb)}</div>${reasonList(s.reasons, "web")}</div>
      <div class="score-card"><div class="sub">Živost (0–100)</div><div class="big">${Math.round(s.vitality)}</div>${reasonList(s.reasons, "vital")}</div>
    </div>
    <div class="row gap" style="margin-top:12px"><button class="btn primary small" id="make-site">Připravit web</button></div>
    ${d.enriched ? "" : `<p class="notice">Zatím jen odhad z registru. <button class="btn small" id="enrich-one">Ověřit tuto firmu</button></p>`}

    <h3>Kontakty</h3>${contactHtml}
    <h3>Oslovení</h3>${crm}
    <h3>Web</h3><p>${webInfo}</p>
    <h3>Google</h3>${googleInfo}
    <h3>Registry</h3>
    <dl class="kv">
      <dt>IČO</dt><dd class="mono">${esc(f.ico)}</dd>
      <dt>Právní forma</dt><dd>${esc(f.forma_label)}</dd>
      <dt>Obor</dt><dd>${esc(f.nace_label)} <span class="muted mono">${esc(f.nace || "")}</span></dd>
      <dt>Zaměstnanci</dt><dd>${esc(f.staff)}</dd>
      <dt>Vznik</dt><dd>${fmtDate(f.datum_vzniku)}</dd>
      <dt>Firem na adrese</dt><dd>${f.addr_count}</dd>
    </dl>
    ${aresInfo}
    <h3>Odkazy</h3>
    <div class="links">
      <a href="${esc(d.links.ares)}" target="_blank" rel="noopener">ARES</a>
      <a href="${esc(d.links.justice)}" target="_blank" rel="noopener">Justice.cz (závěrky)</a>
      <a href="${esc(d.links.firmy)}" target="_blank" rel="noopener">Firmy.cz</a>
      <a href="${esc(d.links.google)}" target="_blank" rel="noopener">Google</a>
      <a href="${esc(d.links.mapy)}" target="_blank" rel="noopener">Mapy.com</a>
    </div>`;

  const ico = f.ico;
  $("#claim-btn")?.addEventListener("click", () => leadAction(ico, "claim"));
  $("#make-site")?.addEventListener("click", () => startSite(ico));
  $("#release-btn")?.addEventListener("click", () => leadAction(ico, "release"));
  $("#enrich-one")?.addEventListener("click", async () => {
    const job = await api("/api/enrich", { body: { icos: [ico] } });
    const wait = async () => { const j = await api("/api/jobs/" + job.id); if (j.status === "done") { if (j.error_count) toast(j.errors[0]); openFirm(ico); } else setTimeout(wait, 700); };
    wait();
  });
  $("#activity-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api(`/api/leads/${ico}/activity`, { body: { channel: fd.get("channel"), outcome: fd.get("outcome"), note: fd.get("note"), next_action: fd.get("next_action") || null } });
      toast("Zapsáno"); openFirm(ico); refreshRow(ico);
    } catch (err) { toast(err.message); }
  });
  $("#save-contact")?.addEventListener("click", async () => {
    try { await api(`/api/leads/${ico}/contact-note`, { body: { contact_note: $("#contact-note").value } }); toast("Kontakty uloženy"); }
    catch (err) { toast(err.message); }
  });
}

async function leadAction(ico, action) {
  try { await api(`/api/leads/${ico}/${action}`, { method: "POST" }); openFirm(ico); refreshRow(ico); }
  catch (err) { toast(err.message); }
}
function refreshRow() { if (state.center) runSearch(); }

// ------------------------------------------------------------------ přehledy
$$(".tab").forEach((t) => t.addEventListener("click", () => {
  $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + t.dataset.view).classList.remove("hidden");
  if (t.dataset.view === "inquiries") loadInquiries();
  if (t.dataset.view === "mine") loadList("mine", "#mine-body");
  if (t.dataset.view === "team") { loadList("all", "#team-body"); loadStats(); if (state.me.is_admin) { loadUsers(); loadProducts(); loadBrand(); } }
  if (t.dataset.view === "checklist") loadChecklist();
  if (t.dataset.view === "sites") loadSites();
  if (t.dataset.view === "search") setTimeout(() => state.map?.invalidateSize(), 50);
}));

async function loadList(scope, sel) {
  const rows = await api("/api/my?scope=" + scope);
  const today = new Date().toISOString().slice(0, 10);
  $(sel).innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr><th>Firma</th><th>Stav</th><th>Řeší</th><th>Další krok</th><th>Poslední kontakt</th><th>Počet</th></tr></thead><tbody>` +
    rows.map((r) => `<tr data-ico="${r.ico}">
      <td><div class="firm-name">${esc(r.nazev)}</div><div class="sub">${esc(r.adresa || "")}</div></td>
      <td><span class="badge ${esc(r.status)}">${esc(r.status_label)}</span></td>
      <td>${esc(r.owner_name || "")}</td>
      <td class="${r.next_action && r.next_action <= today ? "error" : ""}">${fmtDate(r.next_action)}</td>
      <td class="sub">${fmtDT(r.last_ts)}</td><td class="pct">${r.n_act}</td></tr>`).join("") + "</tbody></table></div>"
    : '<p class="muted">Zatím nic. Rezervujte si firmu v detailu nebo zapište první oslovení.</p>';
  $(sel).onclick = (e) => { const tr = e.target.closest("tr[data-ico]"); if (tr) openFirm(tr.dataset.ico); };
}

async function loadStats() {
  const rows = await api("/api/stats");
  const per = {};
  rows.forEach((r) => { per[r.display_name] = per[r.display_name] || { total: 0 }; per[r.display_name][r.status] = r.n; per[r.display_name].total += r.n; });
  $("#team-stats").innerHTML = Object.entries(per).map(([name, s]) =>
    `<div class="stat"><span class="muted">${esc(name)}</span><b>${s.total}</b><span class="tiny muted">zájem ${(s.interested || 0) + (s.meeting || 0)} · zakázky ${s.won || 0}</span></div>`).join("");
}

// ------------------------------------------------------------------ správa uživatelů
function genPassword() {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const buf = new Uint32Array(12); crypto.getRandomValues(buf);
  return [...buf].map((n) => chars[n % chars.length]).join("");
}

function renderUsers(users) {
  $("#users-body").innerHTML = `<div class="table-wrap"><table><thead><tr>
      <th>Jméno</th><th>Přihlášení</th><th>Role</th><th>Rozpracováno</th><th>Oslovení</th><th>Naposledy</th><th></th></tr></thead><tbody>` +
    users.map((u) => `<tr data-id="${u.id}" class="${u.active ? "" : "inactive"}">
      <td class="firm-name">${esc(u.display_name)}${u.id === state.me.id ? ' <span class="muted">(vy)</span>' : ""}</td>
      <td class="mono">${esc(u.username)}</td>
      <td>${u.active ? (u.is_admin ? '<span class="badge interested">admin</span>' : '<span class="badge">člen</span>') : '<span class="badge lost">deaktivován</span>'}</td>
      <td class="pct">${u.open_leads}</td><td class="pct">${u.n_act}</td><td class="sub">${fmtDT(u.last_ts)}</td>
      <td><div class="actions">
        <button class="btn small ghost" data-act="rename">Přejmenovat</button>
        <button class="btn small ghost" data-act="password">Nové heslo</button>
        ${u.id === state.me.id ? "" : u.active ? `
          <button class="btn small ghost" data-act="admin">${u.is_admin ? "Odebrat admina" : "Udělat adminem"}</button>
          <button class="btn small ghost danger" data-act="deactivate">Deaktivovat</button>`
          : '<button class="btn small" data-act="activate">Znovu aktivovat</button>'}
      </div></td></tr>`).join("") + "</tbody></table></div>";
}

async function loadUsers() {
  try { renderUsers(await api("/api/admin/users")); } catch (err) { toast(err.message); }
}

async function patchUser(id, body, msg) {
  try { renderUsers(await api("/api/admin/users/" + id, { method: "PATCH", body })); toast(msg); }
  catch (err) { toast(err.message, 5000); }
}

$("#users-body").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]"); if (!btn) return;
  const tr = btn.closest("tr"); const id = Number(tr.dataset.id);
  const name = tr.querySelector(".firm-name").firstChild.textContent;
  const act = btn.dataset.act;
  if (act === "rename") {
    const v = prompt("Nové jméno:", name); if (v && v.trim()) patchUser(id, { display_name: v.trim() }, "Jméno změněno");
  } else if (act === "password") {
    const pw = genPassword();
    const v = prompt(`Nové heslo pro ${name} (min. 8 znaků). Pošlete mu ho bezpečnou cestou:`, pw);
    if (v) patchUser(id, { password: v }, "Heslo nastaveno – nezapomeňte ho předat");
  } else if (act === "admin") {
    const make = btn.textContent.startsWith("Udělat");
    patchUser(id, { is_admin: make }, make ? `${name} je admin` : `${name} už není admin`);
  } else if (act === "deactivate") {
    if (confirm(`Deaktivovat ${name}? Nebude se moct přihlásit a jeho rozpracované firmy se uvolní ostatním. Historie oslovení zůstane.`))
      patchUser(id, { active: false }, `${name} deaktivován`);
  } else if (act === "activate") {
    patchUser(id, { active: true }, `${name} znovu aktivní`);
  }
});

$("#gen-pw").addEventListener("click", () => { $("#add-user-form [name=password]").value = genPassword(); });

$("#add-user-form [name=display_name]").addEventListener("input", (e) => {
  const u = $("#add-user-form [name=username]");
  if (u.dataset.touched) return;
  u.value = e.target.value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().split(/\s+/)[0].replace(/[^a-z0-9._-]/g, "");
});
$("#add-user-form [name=username]").addEventListener("input", (e) => { e.target.dataset.touched = "1"; });

$("#add-user-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, fd = new FormData(f);
  const submitBtn = f.querySelector("button[type=submit]");
  if (submitBtn.disabled) return;
  submitBtn.disabled = true;
  const body = { display_name: fd.get("display_name"), username: fd.get("username"), password: fd.get("password"), is_admin: fd.get("is_admin") === "on" };
  try {
    renderUsers(await api("/api/admin/users", { body }));
    toast(`Přidán ${body.display_name}. Přihlášení: ${body.username} / ${body.password}`, 10000);
    f.reset(); delete f.username.dataset.touched;
    state.meta = await api("/api/meta");
  } catch (err) { toast(err.message, 5000); }
  finally { submitBtn.disabled = false; }
});

// změna vlastního hesla
$("#pw-btn").addEventListener("click", () => { $("#pw-error").textContent = ""; $("#pw-form").reset(); $("#pw-dialog").showModal(); });
$("#pw-form").addEventListener("submit", async (e) => {
  if (e.submitter?.value === "cancel") return;
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/api/me/password", { body: { old_password: fd.get("old_password"), new_password: fd.get("new_password") } });
    $("#pw-dialog").close(); toast("Heslo změněno");
  } catch (err) { $("#pw-error").textContent = err.message; }
});

// ------------------------------------------------------------------ checklisty a ceník
const kc = (n) => (n || 0).toLocaleString("cs-CZ") + " Kč";
let clData = null, clKind = "sales";
const clStoreKey = () => "rmlab-checklist-" + clKind;
function clDone() { try { return new Set(JSON.parse(localStorage.getItem(clStoreKey()) || "[]")); } catch { return new Set(); } }
function clSave(set) { try { localStorage.setItem(clStoreKey(), JSON.stringify([...set])); } catch {} }
const hl = (t) => esc(t).replace(/\[([^\]]+)\]/g, '<span class="fill">$1</span>');
const clCount = () => { $("#cl-progress").textContent = `${$$("#cl-body input:checked").length} / ${$$("#cl-body input").length}`; };

function renderChecklist() {
  const done = clDone();
  $("#cl-title").textContent = clData.title;
  $("#cl-body").innerHTML = clData.sections.map((sec, si) => `
    <section class="cl-section"><h3>${esc(sec.title)}</h3>
      ${sec.items.map((it, ii) => {
        const id = `${si}:${ii}:${it.text.slice(0, 40)}`;
        const on = done.has(id);
        return `<label class="cl-item ${on ? "done" : ""}"><input type="checkbox" data-id="${esc(id)}" ${on ? "checked" : ""}>
          <span class="t">${hl(it.text)}</span>${it.tip ? `<span class="tip">${hl(it.tip)}</span>` : ""}</label>`;
      }).join("")}
    </section>`).join("");
  clCount();
  $("#cl-meta").textContent = clData.is_default ? "Výchozí verze" :
    `Upraveno ${fmtDT(clData.updated_at)}${clData.updated_by ? " · " + clData.updated_by : ""}`;
  $("#cl-edit").classList.toggle("hidden", !state.me.is_admin);
}

function renderPricelist(products) {
  if (clKind !== "sales") { $("#pricelist").innerHTML = ""; return; }
  $("#pricelist").innerHTML = products.length ? products.map((p) => `
    <div class="price-card">
      <h4>${esc(p.name)}</h4>${p.description ? `<div class="sub">${esc(p.description)}</div>` : ""}
      ${p.base_price || p.monthly_fee ? `<div class="prices">
        <div class="price"><b>${kc(p.base_price)}</b><span>jednorázově · plátci DPH ${kc(Math.round(p.base_price * 1.21))} s DPH</span></div>
        <div class="price"><b>${kc(p.monthly_fee)}</b><span>měsíčně · plátci DPH ${kc(Math.round(p.monthly_fee * 1.21))} s DPH</span></div>
      </div>` : `<div class="prices"><div class="price"><b>Dohodou</b><span>cenu řekneme po schůzce</span></div></div>`}
      ${p.includes ? "<ul>" + p.includes.split("\n").filter((l) => l.trim()).map((l) => `<li>${esc(l.replace(/^[-•]\s*/, ""))}</li>`).join("") + "</ul>" : ""}
    </div>`).join("")
    : `<div class="price-empty">Ceník zatím není vyplněný.${state.me.is_admin ? " Produkty přidáte v záložce Tým → Produkty a ceník." : " Zeptej se Lukáše."}</div>`;
}

async function loadChecklist() {
  clEditor(false);
  try {
    const [cl, products] = await Promise.all([api("/api/checklist/" + clKind), api("/api/products")]);
    clData = cl; renderChecklist(); renderPricelist(products);
  } catch (err) { toast(err.message); }
}

$("#cl-kinds").addEventListener("click", (e) => {
  const b = e.target.closest(".seg-btn"); if (!b) return;
  clKind = b.dataset.kind;
  $$("#cl-kinds .seg-btn").forEach((x) => x.classList.toggle("active", x === b));
  loadChecklist();
});
$("#cl-body").addEventListener("change", (e) => {
  const id = e.target.dataset.id; if (!id) return;
  const done = clDone(); e.target.checked ? done.add(id) : done.delete(id); clSave(done);
  e.target.closest(".cl-item").classList.toggle("done", e.target.checked);
  clCount();
});
$("#cl-reset").addEventListener("click", () => { clSave(new Set()); renderChecklist(); });

function clEditor(open) {
  $("#cl-editor").classList.toggle("hidden", !open);
  $("#cl-body").classList.toggle("hidden", open);
  $("#cl-edit").classList.toggle("hidden", open || !state.me?.is_admin);
  $("#cl-reset").classList.toggle("hidden", open);
  if (open) $("#cl-text").value = clData.text || "";
}
$("#cl-edit").addEventListener("click", () => clEditor(true));
$("#cl-cancel").addEventListener("click", () => clEditor(false));
$("#cl-save").addEventListener("click", async () => {
  try { clData = await api("/api/checklist/" + clKind, { method: "PUT", body: { text: $("#cl-text").value } }); clEditor(false); renderChecklist(); toast("Checklist uložen"); }
  catch (err) { toast(err.message, 5000); }
});
$("#cl-default").addEventListener("click", async () => {
  if (!confirm("Vrátit checklist do výchozí podoby? Vaše úpravy se ztratí.")) return;
  try { clData = await api("/api/checklist/" + clKind, { method: "PUT", body: { text: null } }); clEditor(false); renderChecklist(); toast("Obnoveno"); }
  catch (err) { toast(err.message); }
});

// oficiální loga pro hodnocení (admin)
function renderBrand(files) {
  $$(".brand-slot").forEach((el) => {
    const f = files[el.dataset.key];
    el.querySelector(".bprev").innerHTML = f ? `<img src="/brand/${f}?t=${Date.now()}" alt="">` : "zatím nenahráno";
  });
}
async function loadBrand() { try { renderBrand(await api("/api/brand")); } catch (err) { toast(err.message); } }
$("#brand-panel").addEventListener("change", async (e) => {
  const inp = e.target, file = inp.files && inp.files[0]; if (!file) return;
  try {
    const res = await fetch("/api/brand/" + inp.dataset.brand, { method: "POST", headers: { "Content-Type": file.type }, body: file, credentials: "same-origin" });
    const r = await res.json(); if (!res.ok) throw new Error(r.detail || "Nahrání se nepovedlo");
    renderBrand(r); toast("Logo nahráno");
  } catch (err) { toast(err.message, 5000); }
  inp.value = "";
});

// produkty (admin)
let productsCache = [];
function renderProducts(list) {
  productsCache = list;
  $("#products-body").innerHTML = list.length ? `<div class="table-wrap"><table><thead><tr>
      <th>Produkt</th><th>Základní cena</th><th>Měsíčně</th><th>Stav</th><th></th></tr></thead><tbody>` +
    list.map((p) => `<tr data-id="${p.id}" class="${p.active ? "" : "inactive"}">
      <td><div class="firm-name">${esc(p.name)}</div><div class="sub">${esc(p.description || "")}</div></td>
      <td class="pct">${kc(p.base_price)}</td><td class="pct">${kc(p.monthly_fee)}</td>
      <td>${p.active ? '<span class="badge interested">aktivní</span>' : '<span class="badge">skrytý</span>'}</td>
      <td><div class="actions"><button class="btn small ghost" data-act="edit">Upravit</button>
        <button class="btn small ghost" data-act="toggle">${p.active ? "Skrýt" : "Zobrazit"}</button></div></td></tr>`).join("") +
    "</tbody></table></div>" : '<p class="muted">Zatím žádné produkty – přidejte první níže.</p>';
}
async function loadProducts() { try { renderProducts(await api("/api/products?all=true")); } catch (err) { toast(err.message); } }

function productForm(p) {
  const f = $("#product-form");
  f.id.value = p?.id || ""; f.name.value = p?.name || ""; f.base_price.value = p?.base_price ?? "";
  f.monthly_fee.value = p?.monthly_fee ?? ""; f.description.value = p?.description || "";
  f.includes.value = p?.includes || ""; f.sort.value = p?.sort ?? 0; f.active.checked = p ? !!p.active : true;
  $("#product-form-title").textContent = p ? `Upravit: ${p.name}` : "Přidat produkt";
  $("#product-cancel").classList.toggle("hidden", !p);
}
const productBody = (f, overrides = {}) => ({
  name: f.name.value, base_price: Number(f.base_price.value || 0), monthly_fee: Number(f.monthly_fee.value || 0),
  description: f.description.value, includes: f.includes.value, sort: Number(f.sort.value || 0), active: f.active.checked, ...overrides,
});
$("#product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, id = f.id.value;
  try {
    renderProducts(await api(id ? `/api/products/${id}` : "/api/products", { method: id ? "PUT" : "POST", body: productBody(f) }));
    toast(id ? "Produkt upraven" : "Produkt přidán"); productForm(null);
  } catch (err) { toast(err.message, 5000); }
});
$("#product-cancel").addEventListener("click", () => productForm(null));
$("#products-body").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]"); if (!btn) return;
  const p = productsCache.find((x) => x.id === Number(btn.closest("tr").dataset.id));
  if (btn.dataset.act === "edit") { productForm(p); $("#product-form").scrollIntoView({ behavior: "smooth", block: "center" }); }
  else {
    try { renderProducts(await api(`/api/products/${p.id}`, { method: "PUT", body: { ...p, active: !p.active } })); }
    catch (err) { toast(err.message); }
  }
});

// ------------------------------------------------------------------ weby pro klienty
const ICON_LABELS = { scissors: "Nůžky", cup: "Šálek", plate: "Příbor", leaf: "List", star: "Hvězda" };
const ed = { site: null, timer: null, saving: false, dirty: false };

async function loadSites() {
  const rows = await api("/api/sites");
  $("#sites-body").innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr>
      <th>Web</th><th>Typ</th><th>Stav</th><th>Kontrola</th><th>Naposledy upravil</th></tr></thead><tbody>` +
    rows.map((r) => `<tr data-site="${r.id}">
      <td class="firm-name">${esc(r.name)}</td><td class="sub">${esc(r.type)}</td>
      <td><span class="badge ${siteBadge(r.status)}">${esc(r.status_label)}</span></td>
      <td>${r.summary.ready ? '<span class="badge interested">vše povinné splněno</span>' : `<span class="badge warn">chybí ${r.summary.errors}</span>`}</td>
      <td class="sub">${esc(r.author || "")} ${fmtDT(r.updated_at)}</td></tr>`).join("") + "</tbody></table></div>"
    : '<p class="muted">Zatím žádný web. Otevřete firmu ve vyhledávání a klikněte na „Připravit web“.</p>';
}
const siteBadge = (s) => ({ draft: "", review: "claimed", approved: "interested", published: "won" }[s] || "");
$("#sites-body").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-site]"); if (tr) openSite(Number(tr.dataset.site)); });

function showView(name) {
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + name).classList.remove("hidden");
  $$(".tab").forEach((x) => x.classList.toggle("active", x.dataset.view === (name === "editor" ? "sites" : name)));
}

async function startSite(ico) {
  try { const s = await api("/api/sites", { body: { ico } }); closeDrawer(); openSite(s.id, s); }
  catch (err) { toast(err.message); }
}

async function openSite(id, payload) {
  ed.site = payload || await api("/api/sites/" + id);
  showView("editor");
  renderEditor();
  refreshPreview();
}
$("#ed-back").addEventListener("click", async () => { await flushSave(); showView("sites"); loadSites(); });

// --- pomocníci pro formulář
const getPath = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function setPath(o, p, v) { const ks = p.split("."); const last = ks.pop(); const t = ks.reduce((a, k) => a[k], o); t[last] = v; }
const inp = (path, label, attrs = "") => {
  const v = getPath(ed.site.data, path) ?? "";
  return `<label>${label}<input data-path="${path}" value="${esc(v)}" ${attrs}></label>`;
};
const area = (path, label, attrs = "") => `<label>${label}<textarea data-path="${path}" ${attrs}>${esc(getPath(ed.site.data, path) ?? "")}</textarea></label>`;
const counted = (path, label, min, max) => {
  const v = getPath(ed.site.data, path) || "";
  const bad = v.length < min || v.length > max;
  return `<label>${label} <span class="counter ${bad ? "bad" : ""}" data-count="${path}" data-min="${min}" data-max="${max}">${v.length} / ${min}–${max}</span>
    ${max > 80 ? `<textarea data-path="${path}" rows="3">${esc(v)}</textarea>` : `<input data-path="${path}" value="${esc(v)}">`}</label>`;
};
const imgUrl = (f) => f ? `/api/sites/${ed.site.id}/img/${f}` : "";
function qualBadge(file, minSide = 900) {
  const q = (ed.site.data.images || {})[file]; if (!q) return "";
  const probs = [];
  if (q.w && Math.max(q.w, q.h || 0) < minSide) probs.push("malá");
  if (q.bright != null && q.bright < 70) probs.push("tmavá");
  if (q.bright != null && q.bright > 215) probs.push("přesvícená");
  if (q.sharp != null && q.sharp < 60) probs.push("rozmazaná");
  return probs.length ? `<span class="badge warn q">${probs.join(", ")}</span>` : `<span class="badge interested q">OK</span>`;
}
const imgOne = (path, altPath, label) => {
  const f = getPath(ed.site.data, path);
  return `<label>${label}</label><div class="img-one">${f ? `<img src="${imgUrl(f)}" alt="">` : ""}
    <label class="btn small upload">${f ? "Vyměnit" : "Nahrát fotku"}<input type="file" accept="image/*" data-upload="${path}"></label>
    ${f ? qualBadge(f, path === "hero.image" ? 1200 : path === "contact.photo" ? 300 : 900) : ""}</div>${altPath ? inp(altPath, "Popisek fotky (alt) – co na ní je") : ""}`;
};

function listRows(key, cls, fields, addLabel, example) {
  const rows = ed.site.data[key] || [];
  return rows.map((r, i) => `<div class="list-row"><div class="cols ${cls}">${fields.map(([f, ph, type]) => type === "check"
      ? `<label class="check"><input type="checkbox" data-list="${key}" data-i="${i}" data-f="${f}" ${r[f] ? "checked" : ""}> ${ph}</label>`
      : type === "area" ? `<textarea data-list="${key}" data-i="${i}" data-f="${f}" placeholder="${esc(ph)}" rows="2">${esc(r[f] || "")}</textarea>`
      : `<input data-list="${key}" data-i="${i}" data-f="${f}" placeholder="${esc(ph)}" value="${esc(r[f] || "")}">`).join("")}</div>
      <button type="button" class="del" data-del="${key}" data-i="${i}" aria-label="Smazat">×</button></div>`).join("") +
    `<div class="row gap" style="margin-top:8px"><button type="button" class="btn small" data-add="${key}">${addLabel}</button>${example || ""}</div>`;
}

function tplExtra(d) {
  const t = String(d.theme.template || "1");
  const names = { 4: "pop", 5: "luxusní", 6: "urban", 7: "štětcovou" };
  if (!names[t]) return "";
  let h = `<fieldset><legend>Navíc pro ${names[t]} šablonu</legend>`;
  if (t === "4") h += `<p class="hint">Slovo v hlavním nadpisu obalte dvěma hvězdičkami a bude zvýrazněné: <b>Burgery **na rohu** Čelákovic</b>. Výhody běží jako pruh přes stránku.</p>`;
  if (t === "6") h += `<p class="hint">Nadpis krátce, 1–2 slova velkým písmem + slovo ve hvězdičkách, které se napíše ručním písmem přes fotku: <b>Burgery **na rohu**</b>. Podnadpis se zobrazí jako velká věta pod úvodem. Výhody jsou karty s černobílými fotkami. Barva v nastavení vzhledu mění žlutou.</p>`
    + inp("extra.intro_title", "Štítek nad textem o firmě", 'placeholder="O nás"');
  if (t === "5" || t === "7") {
    h += t === "5"
      ? `<p class="hint">Hlavní nadpis krátce a úderně (např. „Káva. Pomalu.“). Výhody se zobrazí v karuselu s fotkami.</p>`
      : `<p class="hint">Úvod má barevný přechod a fotku do něj vpitou – nejlépe fotka člověka nebo detailu na světlém pozadí. U textu o firmě se použije fotka kontaktní osoby (nebo první z galerie). Barva v nastavení vzhledu mění červenou.</p>`;
    h += inp("extra.intro_title", "Nadpis nad textem o firmě", 'placeholder="Malá kavárna. Velká péče o detail."');
    h += `<label>Velká čísla (${t === "5" ? "1–4, v dlaždicích" : "2–4, pod úvodem"})</label>
      <p class="hint">Krátké číslo + popisek, např. „15“ – „let praxe“, „4,9 ★“ – „na Googlu“, „30“ – „míst na zahrádce“. Když nic nevyplníte, použije se hodnocení a čas otevření.</p>`;
    const f = [["value", "Číslo (např. 30)"], ["label", "Popisek (např. míst na zahrádce)"]];
    if (t === "7") f.push(["note", "Drobný text (nepovinné)"]);
    h += listRows("stats", t === "7" ? "c3" : "c2", f, "+ Přidat číslo");
  }
  return h + "</fieldset>";
}

// stav prvního importu dat na serveru (RES + RÚIAN trvá desítky minut)
function showImport(im) {
  const b = $("#demo-badge");
  if (!im || (!im.running && !im.error)) return;
  b.classList.remove("hidden");
  b.textContent = im.error ? "Import dat selhal" : (im.step || "Importuji data…");
  b.title = im.error || "Data firem se stahují z veřejných rejstříků. Hledání bude kompletní, až import doběhne.";
  if (im.running) setTimeout(async () => {
    try { const m = await api("/api/meta"); showImport(m.import); if (!m.import.running) location.reload(); } catch {}
  }, 30000);
}

// ---------- poptávky z webu
function setInqCount(n) {
  const b = $("#inq-count"); if (!b) return;
  b.textContent = n || ""; b.classList.toggle("hidden", !n);
}
async function loadInquiries() {
  try { renderInquiries(await api("/api/inquiries")); } catch (err) { $("#inq-body").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
}
const INQ_ST = { new: ["Nová", "won"], progress: ["Řeší se", "warn"], done: ["Vyřízeno", ""] };
let inqRows = [], inqOpen = null;
function inqBadge(st) { const [t, c] = INQ_ST[st] || [st, ""]; return `<span class="badge ${c}">${t}</span>`; }
function renderInquiries(rows) {
  inqRows = rows;
  setInqCount(rows.filter((r) => r.status === "new").length);
  $("#inq-body").innerHTML = rows.length ? `<div class="table-wrap"><table><thead><tr><th>Kdy</th><th>Kdo</th><th>Kontakt</th><th>Co potřebuje</th><th>Stav</th><th>Řeší</th></tr></thead><tbody>` +
    rows.map((r) => `<tr data-inq-row="${r.id}" class="clickable ${r.status === "done" ? "inactive" : ""} ${inqOpen === r.id ? "selected" : ""}">
      <td class="sub">${fmtDT(r.created_at)}</td>
      <td><div class="firm-name">${esc(r.company)}</div><div class="sub">${esc(r.name)}</div></td>
      <td class="mono">${esc(r.contact)}</td>
      <td><b>${esc(r.need || "")}</b>${r.message ? `<div class="sub" style="white-space:pre-line;max-width:46ch;max-height:3.2em;overflow:hidden">${esc(r.message)}</div>` : ""}</td>
      <td>${inqBadge(r.status)}</td>
      <td class="sub">${esc(r.assigned_name || "—")}</td>
    </tr>`).join("") + "</tbody></table></div>"
    : '<p class="muted">Zatím žádná poptávka. Jakmile někdo vyplní formulář na webu, objeví se tady.</p>';
  if (inqOpen !== null) { const r = rows.find((x) => x.id === inqOpen); if (r) renderInqDetail(r); else closeDrawer(); }
}
function renderInqDetail(r) {
  const users = (state.meta && state.meta.users) || [];
  const isMail = /@/.test(r.contact || ""), tel = (r.contact || "").replace(/[^\d+]/g, "");
  const contactLink = isMail ? `<a href="mailto:${esc(r.contact)}">${esc(r.contact)}</a>` : (tel.length >= 9 ? `<a href="tel:${esc(tel)}">${esc(r.contact)}</a>` : esc(r.contact));
  $("#drawer-content").innerHTML = `
    <h2>${esc(r.company || r.name)}</h2>
    <p class="sub">Poptávka z webu · ${fmtDT(r.created_at)}</p>
    <div class="panel" style="margin-top:14px">
      <p><span class="sub">Jméno</span><br><b>${esc(r.name)}</b></p>
      <p><span class="sub">Kontakt</span><br>${contactLink}</p>
      <p><span class="sub">Co potřebuje</span><br><b>${esc(r.need || "—")}</b></p>
      ${r.message ? `<p><span class="sub">Zpráva</span><br><span style="white-space:pre-line">${esc(r.message)}</span></p>` : ""}
    </div>
    <h3 style="margin-top:18px">Stav</h3>
    <div class="row" style="display:flex;gap:6px;flex-wrap:wrap">
      ${Object.entries(INQ_ST).map(([k, [t]]) => `<button class="btn small ${r.status === k ? "primary" : "ghost"}" data-inq-st="${k}">${t}</button>`).join("")}
    </div>
    ${r.status === "done" && r.handled_by_name ? `<p class="sub">Vyřídil(a) ${esc(r.handled_by_name)} · ${fmtDT(r.handled_at)}</p>` : ""}
    <h3 style="margin-top:18px">Kdo to řeší</h3>
    <select id="inq-assign"><option value="">— nikdo —</option>${users.map((u) => `<option value="${u.id}" ${r.assigned_to === u.id ? "selected" : ""}>${esc(u.display_name)}</option>`).join("")}</select>
    <h3 style="margin-top:18px">Poznámka</h3>
    <textarea id="inq-note" rows="5" maxlength="2000" placeholder="Co jsme domluvili, kdy zavolat…">${esc(r.note || "")}</textarea>
    <div style="display:flex;justify-content:space-between;gap:8px;margin-top:10px">
      <button class="btn small primary" id="inq-save-note">Uložit poznámku</button>
      <button class="btn small ghost" id="inq-del" style="color:var(--rec)">Smazat poptávku</button>
    </div>`;
  const put = async (body, msg) => {
    try { renderInquiries(await api("/api/inquiries/" + r.id, { method: "PUT", body })); if (msg) toast(msg); } catch (err) { toast(err.message); }
  };
  $$("#drawer-content [data-inq-st]").forEach((b) => b.addEventListener("click", () => put({ status: b.dataset.inqSt })));
  $("#inq-assign").addEventListener("change", (e) => put(e.target.value ? { assigned_to: +e.target.value } : { unassign: true }, "Přiřazeno"));
  $("#inq-save-note").addEventListener("click", () => put({ note: $("#inq-note").value }, "Poznámka uložena"));
  $("#inq-del").addEventListener("click", async () => {
    if (!confirm(`Opravdu smazat poptávku od ${r.company || r.name}? Nejde to vrátit.`)) return;
    try { const rows = await api("/api/inquiries/" + r.id, { method: "DELETE" }); inqOpen = null; closeDrawer(); renderInquiries(rows); toast("Poptávka smazána"); }
    catch (err) { toast(err.message); }
  });
}
$("#inq-body").addEventListener("click", (e) => {
  if (e.target.closest("a")) return;
  const tr = e.target.closest("tr[data-inq-row]"); if (!tr) return;
  const r = inqRows.find((x) => x.id === +tr.dataset.inqRow); if (!r) return;
  inqOpen = r.id;
  $$("#inq-body tr").forEach((t) => t.classList.toggle("selected", t === tr));
  $("#drawer").classList.remove("hidden");
  renderInqDetail(r);
});

function renderEditor() {
  const s = ed.site, d = s.data;
  ed.renderedType = d.type;
  $("#ed-title").textContent = d.name || "Nový web";
  const types = Object.entries(s.types).map(([k, v]) => `<option value="${k}" ${d.type === k ? "selected" : ""}>${esc(v)}</option>`).join("");
  const icons = Object.entries(ICON_LABELS).map(([k, v]) => `<option value="${k}" ${d.logo.icon === k ? "selected" : ""}>${v}</option>`).join("");
  $("#ed").innerHTML = `
  <fieldset><legend>Typ a vzhled</legend>
    <div class="f2">
      <label>Šablona<select data-path="theme.template">${Object.entries(s.templates || { 1: "Šablona 1", 2: "Šablona 2" }).map(([k, v]) => `<option value="${k}" ${String(d.theme.template || "1") === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
      <label>Typ provozovny<select data-path="type">${types}</select></label>
      ${inp("name", "Název provozovny")}
      ${inp("logo.text", "Text loga")}
      <label>Ikona v logu<select data-path="logo.icon">${icons}</select></label>
      <label>Barva (nepovinné)<input type="color" data-path="theme.accent" value="${esc(d.theme.accent || "#6b2d5c")}"></label>
      <div class="row" style="align-items:flex-end"><button type="button" class="btn small ghost" id="ed-color-reset">Výchozí barva šablony</button></div>
      <label>Písmo nadpisů (Google Fonts)<input data-path="theme.font_display" list="gfonts" placeholder="výchozí šablony" value="${esc(d.theme.font_display || "")}"></label>
      <label>Tloušťka nadpisů<select data-path="theme.font_display_w">${["", "300", "400", "500", "600", "700", "800", "900"].map((w) => `<option value="${w}" ${String(d.theme.font_display_w || "") === w ? "selected" : ""}>${w || "výchozí"}</option>`).join("")}</select></label>
      <label>Písmo textu (Google Fonts)<input data-path="theme.font_body" list="gfonts" placeholder="výchozí šablony" value="${esc(d.theme.font_body || "")}"></label>
      <div class="row" style="align-items:flex-end"><a class="btn small ghost" href="https://fonts.google.com/" target="_blank" rel="noopener">Procházet Google Fonts</a></div>
    </div>
    <datalist id="gfonts">${GFONTS.map((n) => `<option value="${n}">`).join("")}</datalist>
    <p class="hint">Název napište přesně jako na fonts.google.com. Když písmo danou tloušťku nemá, použije se nejbližší.</p>
  </fieldset>

  <div class="ai-box">
    <strong>Texty webu</strong>
    <p class="small-text muted">Napište, co o firmě víte (z hovoru, z Googlu, od majitele). ${s.ai ? "AI z toho navrhne" : "Systém předvyplní"} nadpis, text o firmě, výhody a SEO. Co neví, označí [doplnit].</p>
    <textarea data-path="notes" placeholder="Např.: majitelka Jana, 15 let praxe, stříhá i děti, bez objednání v úterý a čtvrtek, parkování u obchodu…">${esc(d.notes || "")}</textarea>
    <button type="button" class="btn primary small" id="ed-ai">${s.ai ? "Navrhnout texty (AI)" : "Předvyplnit texty"}</button>
  </div>

  <fieldset><legend>Úvod</legend>
    ${counted("hero.title", "Hlavní nadpis (H1)", 10, 70)}
    ${inp("hero.subtitle", "Podnadpis – čím jste jiní")}
    ${imgOne("hero.image", "hero.alt", "Hlavní fotka (ideálně na šířku) – u videa slouží jako náhled")}
    <label>Video v úvodu (nepovinné)</label>
    <div class="img-one">
      ${d.hero.video ? `<span class="badge interested">video nahráno ${(((d.images || {})[d.hero.video] || {}).size / 1048576 || 0).toFixed(1)} MB</span>` : ""}
      <label class="btn small upload">${d.hero.video ? "Vyměnit video" : "Nahrát video (MP4)"}<input type="file" accept="video/mp4,video/webm" data-video="1"></label>
      ${d.hero.video ? '<button type="button" class="btn small ghost" id="ed-video-del">Odebrat video</button>' : ""}
    </div>
    <p class="hint">10–20 s, na šířku, bez zvuku (přehrává se ztlumené), ideálně do 15 MB. Telefon: natočte, v Galerii zkraťte a pošlete.</p>
  </fieldset>

  ${tplExtra(d)}

  <fieldset><legend>O nás</legend>
    <p class="hint">Odstavce oddělte prázdným řádkem. **tučně**, odrážky začínají „- “, podnadpis „### “.</p>
    ${area("about", "", 'rows="9"')}
  </fieldset>

  <fieldset><legend>Čím se liší (výhody)</legend>
    <p class="hint">3–5 věcí, kvůli kterým zákazník přijde právě sem. Např. stříhání bez objednání, max. 30 minut čekání.</p>
    ${listRows("usps", "c2", [["title", "Výhoda"], ["text", "Jedna věta navíc (nepovinné)"]], "+ Přidat výhodu")}
  </fieldset>

  <fieldset><legend>${esc(d.offer_title || "Nabídka")}</legend>
    ${inp("offer_title", "Nadpis sekce")}
    <p class="hint">Skupina (např. Dámy / Páni / Snídaně) seskupí položky do záložek.</p>
    ${listRows("offer", "c4", [["group", "Skupina"], ["name", "Položka"], ["desc", "Popis"], ["price", "Cena"]], "+ Přidat položku",
      '<button type="button" class="btn small ghost" id="ed-offer-ex">Vložit příklad</button>')}
  </fieldset>

  <fieldset><legend>Fotky a video</legend>
    <p class="hint">Vlastní fotky provozovny, týmu a práce – na výšku 4:5 nebo čtverec (jako na Instagram). Každá potřebuje popisek. Fotky se automaticky zmenší.</p>
    <div class="imgs">${d.gallery.map((g, i) => `<div class="img-tile"><img src="${imgUrl(g.file)}" alt="">${qualBadge(g.file)}
      <button type="button" class="del" data-del="gallery" data-i="${i}" aria-label="Odebrat">×</button>
      <input data-list="gallery" data-i="${i}" data-f="alt" placeholder="Popisek: co je na fotce" value="${esc(g.alt || "")}"></div>`).join("")}</div>
    <label class="btn small upload" style="margin-top:10px">+ Přidat fotky<input type="file" accept="image/*" multiple data-upload="gallery"></label>
    ${inp("video", "Video – odkaz na YouTube (nepovinné)", 'placeholder="https://youtu.be/…"')}
  </fieldset>

  <fieldset><legend>Recenze</legend>
    <p class="hint">Jen se souhlasem zákazníka. Texty z Google recenzí nekopírujte – vložte odkaz níže.</p>
    ${listRows("reviews", "", [["text", "Text recenze", "area"], ["author", "Jméno (např. Petra K.)"], ["source", "Odkud (např. Google)"], ["consent", "Zákazník souhlasí se zveřejněním", "check"]], "+ Přidat recenzi")}
    ${inp("reviews_link", "Odkaz na recenze na Googlu")}
  </fieldset>

  <fieldset><legend>Kontakt</legend>
    <div class="f2">${inp("contact.person", "Kontaktní osoba")}${inp("contact.role", "Role (např. majitelka)")}
      ${inp("contact.phone", "Telefon")}${inp("contact.email", "E-mail")}</div>
    ${inp("contact.address", "Adresa")}
    ${imgOne("contact.photo", "contact.photo_alt", "Fotka kontaktní osoby")}
  </fieldset>

  <fieldset><legend>Otevírací doba</legend>
    <div class="f2">${d.hours.map((h, i) => `<label>${esc(h.day)}<input data-list="hours" data-i="${i}" data-f="value" placeholder="9:00–18:00 nebo Zavřeno" value="${esc(h.value)}"></label>`).join("")}</div>
    ${inp("hours_note", "Poznámka (svátky, dovolená)")}
    ${inp("booking_note", "Jak se objednat / rezervovat")}
  </fieldset>

  <fieldset><legend>Vyhledávače (SEO)</legend>
    ${counted("seo.title", "SEO titulek", 30, 60)}
    ${counted("seo.description", "SEO popisek", 70, 160)}
    ${inp("domain", "Doména (až bude)", 'placeholder="kadernictvi-fiala.cz"')}
  </fieldset>

  <fieldset><legend>Hodnocení (hvězdičky)</legend>
    <p class="hint">Opište aktuální hodnocení z profilu firmy. Zobrazí se v úvodu webu a u recenzí.</p>
    <div class="f3">${inp("ratings.google.value", "Google – hodnocení", 'placeholder="4,8"')}${inp("ratings.google.count", "Počet recenzí (text)", 'placeholder="127 nebo přes 100 recenzí"')}${inp("ratings.google.url", "Odkaz na recenze")}</div>
    <div class="f3">${inp("ratings.facebook.value", "Facebook – hodnocení", 'placeholder="4,9"')}${inp("ratings.facebook.count", "Počet recenzí (text)", 'placeholder="58 nebo přes 50 recenzí"')}${inp("ratings.facebook.url", "Odkaz na Facebook recenze")}</div>
  </fieldset>

  <fieldset><legend>Sociální sítě a firma</legend>
    <div class="f3">${inp("social.facebook", "Facebook", 'placeholder="https://facebook.com/…"')}${inp("social.instagram", "Instagram", 'placeholder="https://instagram.com/…"')}${inp("social.tiktok", "TikTok", 'placeholder="https://tiktok.com/@…"')}</div>
    <div class="f2">
      ${inp("company.ico", "IČO")}${inp("company.legal_name", "Obchodní jméno")}</div>
    ${inp("company.address", "Sídlo")}
  </fieldset>`;
  renderChecks();
  renderStatus();
}

function renderChecks() {
  const s = ed.site, sm = s.summary;
  $("#ed-score").textContent = sm.ready ? `Povinné splněno · ${sm.warnings} doporučení` : `Chybí ${sm.errors} povinných · ${sm.warnings} doporučení`;
  let last = "";
  $("#ed-checklist").innerHTML = s.checks.map((c) => {
    const head = c.group !== last ? `<div class="chk-group">${esc(c.group)}</div>` : ""; last = c.group;
    const cls = c.ok ? "ok" : c.level === "error" ? "err" : "warn";
    return head + `<div class="chk ${cls}"><span class="m">${c.ok ? "✓" : c.level === "error" ? "✕" : "!"}</span>
      <span>${esc(c.label)}${!c.ok && c.hint ? ` <small>(${esc(c.hint)})</small>` : ""}</span></div>`;
  }).join("");
}

function renderStatus() {
  const s = ed.site, admin = state.me.is_admin, ready = s.summary.ready;
  const btn = (st, label, cls = "") => `<button type="button" class="btn small ${cls}" data-status="${st}" ${["review", "approved", "published"].includes(st) && !ready ? "disabled title='Nejdřív splňte povinná pravidla'" : ""}>${label}</button>`;
  let html = `<span class="badge ${siteBadge(s.status)}">${esc(s.status_label)}</span>`;
  if (s.status === "draft") html += btn("review", "Odeslat ke schválení", "primary");
  if (s.status === "review" && admin) html += btn("approved", "Schválit", "primary") + btn("draft", "Vrátit k úpravám");
  if (s.status === "approved" && admin) html += btn("published", "Označit jako spuštěný") + btn("draft", "Vrátit k úpravám");
  if (admin) html += `<a class="btn small ghost" href="/api/sites/${s.id}/export">Stáhnout web (ZIP)</a>`;
  html += `<span class="muted small-text">${s.updated_by ? "upravil " + esc(s.updated_by) : ""}</span>`;
  $("#ed-status").innerHTML = html;
  const url = `${location.origin}/p/${s.token}/`;
  $("#ed-open").href = url;
}

$("#ed-status").addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-status]"); if (!b) return;
  await flushSave();
  try { ed.site = await api(`/api/sites/${ed.site.id}/status`, { body: { status: b.dataset.status } }); renderStatus(); renderChecks(); toast(ed.site.status_label); }
  catch (err) { toast(err.message, 5000); }
});
$("#ed-copy").addEventListener("click", async () => {
  const url = `${location.origin}/p/${ed.site.token}/`;
  try { await navigator.clipboard.writeText(url); toast("Odkaz zkopírován. Klientovi půjde otevřít, až aplikace poběží na internetu."); }
  catch { prompt("Odkaz na náhled:", url); }
});
$$("[data-dev]").forEach((b) => b.addEventListener("click", () => {
  $$("[data-dev]").forEach((x) => x.classList.toggle("active", x === b));
  $("#frame-wrap").classList.toggle("desktop", b.dataset.dev === "desktop");
}));

function refreshPreview() {
  const f = $("#ed-frame"), y = f.contentWindow?.scrollY || 0;
  f.onload = () => { try { f.contentWindow.scrollTo(0, y); } catch {} };
  f.src = `/p/${ed.site.token}/?t=${Date.now()}`;
}

// --- ukládání
function scheduleSave() {
  ed.dirty = true; $("#ed-saved").textContent = "Neuloženo…";
  clearTimeout(ed.timer); ed.timer = setTimeout(save, 900);
}
async function save() {
  if (!ed.dirty || ed.saving) return;
  ed.saving = true; ed.dirty = false;
  try {
    const s = await api(`/api/sites/${ed.site.id}`, { method: "PUT", body: { data: ed.site.data } });
    const typeChanged = s.data.type !== ed.renderedType;
    ed.site = { ...s, data: ed.dirty ? ed.site.data : s.data };
    $("#ed-saved").textContent = "Uloženo " + new Date().toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
    renderChecks(); renderStatus(); refreshPreview();
    if (typeChanged) renderEditor();
  } catch (err) { $("#ed-saved").textContent = "Chyba ukládání"; toast(err.message); ed.dirty = true; }
  finally { ed.saving = false; if (ed.dirty) scheduleSave(); }
}
async function flushSave() { clearTimeout(ed.timer); if (ed.dirty) await save(); }

$("#ed").addEventListener("input", (e) => {
  const t = e.target, d = ed.site.data;
  if (t.dataset.path) {
    setPath(d, t.dataset.path, t.type === "checkbox" ? t.checked : t.value);
    if (t.dataset.path === "name") $("#ed-title").textContent = t.value;
    if (t.dataset.path === "theme.template") { renderEditor(); }
    const cnt = $(`[data-count="${t.dataset.path}"]`);
    if (cnt) { const n = t.value.length; cnt.textContent = `${n} / ${cnt.dataset.min}–${cnt.dataset.max}`; cnt.classList.toggle("bad", n < +cnt.dataset.min || n > +cnt.dataset.max); }
  } else if (t.dataset.list) {
    d[t.dataset.list][+t.dataset.i][t.dataset.f] = t.type === "checkbox" ? t.checked : t.value;
  } else return;
  scheduleSave();
});
$("#ed").addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.video) uploadVideo(t);
  if (t.dataset.upload) uploadImages(t);
});
$("#ed").addEventListener("click", async (e) => {
  const d = ed.site.data, t = e.target;
  if (t.dataset.add) {
    const blank = { stats: { value: "", label: "", note: "" }, usps: { title: "", text: "" }, offer: { group: "", name: "", desc: "", price: "" }, reviews: { text: "", author: "", source: "", consent: false } }[t.dataset.add];
    d[t.dataset.add].push(blank); renderEditor(); scheduleSave();
  } else if (t.dataset.del) {
    d[t.dataset.del].splice(+t.dataset.i, 1); renderEditor(); scheduleSave();
  } else if (t.id === "ed-offer-ex") {
    const ex = { kadernictvi: [["Dámy", "Dámský střih", "mytí, střih, foukaná", "od 450 Kč"], ["Páni", "Pánský střih", "", "300 Kč"], ["Barvení", "Barvení", "včetně střihu", "od 900 Kč"]],
      kavarna: [["Káva", "Espresso", "", "55 Kč"], ["Káva", "Cappuccino", "", "75 Kč"], ["Dezerty", "Domácí dort", "dle denní nabídky", "85 Kč"]],
      restaurace: [["Polévky", "Polévka dne", "", "55 Kč"], ["Hlavní jídla", "Svíčková na smetaně", "houskový knedlík", "189 Kč"], ["Hlavní jídla", "Smažený sýr", "hranolky, tatarka", "169 Kč"]] }[d.type];
    ex.forEach(([group, name, desc, price]) => d.offer.push({ group, name, desc, price: `[ověřit: ${price}]` }));
    renderEditor(); scheduleSave();
  } else if (t.id === "ed-video-del") {
    d.hero.video = ""; renderEditor(); scheduleSave();
  } else if (t.id === "ed-color-reset") {
    d.theme.accent = ""; renderEditor(); scheduleSave();
  } else if (t.id === "ed-ai") {
    await flushSave();
    t.disabled = true; t.textContent = "Připravuji…";
    try {
      const r = await api(`/api/sites/${ed.site.id}/ai`, { method: "POST" });
      const d = ed.site.data;   // po uložení je to nový objekt
      const filled = [d.hero.title, d.about, d.seo.title].some((x) => (x || "").trim());
      if (filled && !confirm("Přepsat nadpis, text o firmě, výhody a SEO novým návrhem?")) { renderEditor(); return; }
      d.hero.title = r.hero_title || d.hero.title; d.hero.subtitle = r.hero_subtitle || d.hero.subtitle;
      d.about = r.about || d.about; d.seo.title = r.seo_title || d.seo.title; d.seo.description = r.seo_description || d.seo.description;
      if (Array.isArray(r.usps) && r.usps.length) d.usps = r.usps.map((u) => ({ title: u.title || "", text: u.text || "" }));
      renderEditor(); scheduleSave();
      toast(r.source === "ai" ? "Texty navrženy – projděte je a doplňte [doplnit]" : "Texty předvyplněné – doplňte žlutá místa [doplnit]", 6000);
    } catch (err) { toast(err.message, 6000); renderEditor(); }
  }
});

const GFONTS = ["Inter", "Manrope", "DM Sans", "Outfit", "Sora", "Plus Jakarta Sans", "Space Grotesk", "Figtree", "Work Sans",
  "Bricolage Grotesque", "Syne", "Unbounded", "Archivo", "Montserrat", "Poppins", "Raleway", "Nunito",
  "Playfair Display", "Fraunces", "Cormorant Garamond", "DM Serif Display", "Instrument Serif", "Libre Caslon Text",
  "Lora", "Bodoni Moda", "Young Serif", "Gloock", "Abril Fatface", "Oswald", "Bebas Neue", "Anton", "Caveat"];

async function uploadVideo(input) {
  const file = input.files[0]; if (!file) return;
  if (file.size > 40 * 1024 * 1024) { toast("Video je větší než 40 MB – zkraťte ho nebo zmenšete rozlišení.", 6000); return; }
  await flushSave();
  toast(`Nahrávám video (${(file.size / 1048576).toFixed(1)} MB)…`, 60000);
  try {
    const res = await fetch(`/api/sites/${ed.site.id}/video`, { method: "POST", headers: { "Content-Type": file.type || "video/mp4" }, body: file, credentials: "same-origin" });
    const r = await res.json();
    if (!res.ok) throw new Error(r.detail || "Nahrání se nepovedlo");
    ed.site.data.images = ed.site.data.images || {}; ed.site.data.images[r.file] = r.meta; ed.site.data.hero.video = r.file;
    renderEditor(); ed.dirty = true; await save(); toast("Video nahráno");
  } catch (err) { toast(err.message, 6000); }
}

// --- nahrávání fotek: zmenšení + měření kvality v prohlížeči
async function analyze(file, maxSide) {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
  const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  cv.getContext("2d").drawImage(bmp, 0, 0, w, h);
  // jas a ostrost na zmenšené kopii (max 512 px)
  const s2 = Math.min(1, 512 / Math.max(w, h)), aw = Math.max(8, Math.round(w * s2)), ah = Math.max(8, Math.round(h * s2));
  const a = document.createElement("canvas"); a.width = aw; a.height = ah;
  const ctx = a.getContext("2d"); ctx.drawImage(cv, 0, 0, aw, ah);
  const px = ctx.getImageData(0, 0, aw, ah).data, g = new Float32Array(aw * ah);
  let sum = 0;
  for (let i = 0; i < g.length; i++) { g[i] = 0.299 * px[i * 4] + 0.587 * px[i * 4 + 1] + 0.114 * px[i * 4 + 2]; sum += g[i]; }
  let lsum = 0, lsq = 0, n = 0;
  for (let y = 1; y < ah - 1; y++) for (let x = 1; x < aw - 1; x++) {
    const i = y * aw + x, l = 4 * g[i] - g[i - 1] - g[i + 1] - g[i - aw] - g[i + aw];
    lsum += l; lsq += l * l; n++;
  }
  const mean = lsum / n;
  return { dataUrl: cv.toDataURL("image/jpeg", 0.82), w: bmp.width, h: bmp.height,
    bright: Math.round(sum / g.length), sharp: Math.round(lsq / n - mean * mean) };
}

async function uploadImages(input) {
  const target = input.dataset.upload, files = [...input.files];
  if (!files.length) return;
  await flushSave();
  toast(`Nahrávám ${files.length} ${files.length === 1 ? "fotku" : "fotky"}…`, 20000);
  for (const file of files) {
    try {
      const a = await analyze(file, target === "hero.image" ? 2000 : 1600);
      const r = await api(`/api/sites/${ed.site.id}/images`, { body: { data_url: a.dataUrl, w: a.w, h: a.h, bright: a.bright, sharp: a.sharp } });
      ed.site.data.images = ed.site.data.images || {}; ed.site.data.images[r.file] = r.meta;
      if (target === "gallery") ed.site.data.gallery.push({ file: r.file, alt: "" });
      else setPath(ed.site.data, target, r.file);
    } catch (err) { toast(`${file.name}: ${err.message}`, 6000); }
  }
  renderEditor(); ed.dirty = true; await save();
  toast("Hotovo – nezapomeňte k fotkám napsat popisky");
}

boot();
