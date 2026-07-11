// MonsoonMitra.ai dashboard. Every API call carries the Firebase ID token;
// every dynamic string is escaped before DOM insertion.
import { getFirebase, escapeHtml } from "/firebase-init.js";

const LANGUAGES = [
  "English", "Hindi", "Marathi", "Bengali", "Tamil", "Telugu",
  "Kannada", "Malayalam", "Gujarati", "Odia", "Punjabi", "Urdu",
];

const fb = await getFirebase();
let currentUser = null;

fb.onAuthStateChanged(fb.auth, (user) => {
  if (!user) { window.location.replace("/login.html"); return; }
  currentUser = user;
  document.getElementById("user-email").textContent = user.email || user.displayName || "";
});

document.getElementById("signout").addEventListener("click", async () => {
  await fb.signOut(fb.auth);
  window.location.replace("/login.html");
});

// language selector
const langSel = document.getElementById("language");
langSel.innerHTML = LANGUAGES.map((l) => `<option>${l}</option>`).join("");
const lang = () => langSel.value;

// tabs
document.getElementById("tabs").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-tab]");
  if (!btn) return;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b === btn));
  ["plan", "kit", "scan", "alerts", "advisory"].forEach((t) => {
    document.getElementById(`tab-${t}`).style.display = t === btn.dataset.tab ? "" : "none";
  });
});

async function api(path, options = {}) {
  const token = await currentUser.getIdToken();
  const resp = await fetch(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) },
  });
  if (!resp.ok) {
    let detail = "Request failed.";
    try { detail = (await resp.json()).detail || detail; } catch { /* keep default */ }
    throw new Error(detail);
  }
  return resp.json();
}

function busy(el, msg) { el.innerHTML = `<div class="spinner">⏳ ${escapeHtml(msg)}</div>`; }
function fail(el, e) { el.innerHTML = `<div class="error-box">${escapeHtml(e.message || String(e))}</div>`; }

function numbersFrom(form, names) {
  const out = {};
  for (const n of names) out[n] = Number(form.elements[n].value || 0);
  return out;
}

function renderCitations(citations) {
  if (!citations?.length) return `<p class="muted" style="font-size:.8rem">No live sources returned for this query.</p>`;
  return `<p class="muted" style="font-size:.8rem;margin-bottom:2px">Sources:</p><ul class="citations">` +
    citations.map((c) =>
      `<li><a href="${escapeHtml(c.uri)}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.title || c.uri)}</a></li>`
    ).join("") + `</ul>`;
}

function renderBrief(brief, title) {
  return `<div class="card"><h4>${escapeHtml(title)}</h4>
    <pre class="brief">${escapeHtml(brief.text)}</pre>${renderCitations(brief.citations)}</div>`;
}

// ---------------- PLAN ----------------
document.getElementById("plan-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, out = document.getElementById("plan-result");
  busy(out, "Building your personalized plan + live weather brief…");
  try {
    const body = {
      city: f.elements.city.value.trim(),
      ...numbersFrom(f, ["adults", "children", "infants", "elderly", "pets"]),
      home_type: f.elements.home_type.value,
      special_needs: f.elements.special_needs.value,
      language: lang(),
    };
    const data = await api("/api/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const PHASE_ICONS = { before: "🌤️ Before", during: "⛈️ During", after: "🌈 After" };
    out.innerHTML =
      `<div class="ok-box">${escapeHtml(data.plan.summary)}</div>` +
      data.plan.sections.map((s) =>
        `<div class="card"><h4>${PHASE_ICONS[s.phase] || escapeHtml(s.phase)} — ${escapeHtml(s.title)}</h4>` +
        s.actions.map((a) =>
          `<div style="margin:8px 0"><b>${escapeHtml(a.action)}</b>
            <span class="badge ${escapeHtml(a.priority)}">${escapeHtml(a.priority)}</span>
            <div class="muted" style="font-size:.85rem">${escapeHtml(a.why_for_you)}</div></div>`
        ).join("") + `</div>`
      ).join("") +
      renderBrief(data.weather_brief, "🌦️ Live weather brief (grounded)");
  } catch (e) { fail(out, e); }
});

// ---------------- KIT ----------------
document.getElementById("kit-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, out = document.getElementById("kit-result");
  busy(out, "Asking Gemini for items, then packing them to your budget…");
  try {
    const body = {
      city: f.elements.city.value.trim(),
      budget_inr: Number(f.elements.budget_inr.value),
      ...numbersFrom(f, ["adults", "children", "infants", "elderly", "pets"]),
      notes: f.elements.notes.value,
      language: lang(),
    };
    const kit = await api("/api/kit", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const line = (i) =>
      `<div class="kit-line"><span><b>${escapeHtml(i.name)}</b> × ${i.quantity}
        <span class="badge info">${escapeHtml(i.category)}</span>
        <div class="muted" style="font-size:.8rem">${escapeHtml(i.why_for_you)}</div></span>
        <span class="cost">₹${i.unit_cost_inr * i.quantity}</span></div>`;
    out.innerHTML =
      `<div class="card"><h4>Readiness score <span class="score-ring">${kit.readiness_score}</span>/100</h4>
        <p class="muted" style="font-size:.85rem">
          ₹${kit.total_cost_inr} of ₹${kit.budget_inr} used ·
          ${kit.within_budget ? "✅ fits your budget with all essentials" : "⚠️ couldn't cover all essentials in this budget"} ·
          refined ${kit.refinement_rounds} round(s)
          ${kit.missing_essentials.length ? " · missing: " + kit.missing_essentials.map(escapeHtml).join(", ") : ""}
        </p></div>` +
      `<div class="card"><h4>🎒 Packed (${kit.packed.length})</h4>${kit.packed.map(line).join("") || '<p class="muted">Nothing fit this budget.</p>'}</div>` +
      (kit.overflow.length
        ? `<div class="card"><h4>🛒 Didn't fit — buy when you can (${kit.overflow.length})</h4>${kit.overflow.map(line).join("")}</div>`
        : "");
  } catch (e) { fail(out, e); }
});

// ---------------- SCAN ----------------
document.getElementById("scan-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, out = document.getElementById("scan-result");
  const file = f.elements.photo.files[0];
  if (!file) return;
  if (file.size > 6 * 1024 * 1024) { fail(out, new Error("Image exceeds the 6 MB limit.")); return; }
  busy(out, "Inspecting your photo for monsoon hazards…");
  try {
    const fd = new FormData();
    fd.append("photo", file);
    fd.append("language", lang());
    const report = await api("/api/hazard-scan", { method: "POST", body: fd });
    if (!report.identified) {
      out.innerHTML = `<div class="ok-box">✅ ${escapeHtml(report.overall_assessment)}</div>`;
      return;
    }
    out.innerHTML =
      report.hazards.map((h) =>
        `<div class="card"><h4>${escapeHtml(h.label)}
          <span class="badge ${escapeHtml(h.severity)}">${escapeHtml(h.severity)}</span></h4>
          <p class="muted" style="font-size:.85rem;margin:4px 0">${escapeHtml(h.why_risky)}</p>
          <p style="font-size:.9rem;margin:4px 0">🔧 <b>Fix:</b> ${escapeHtml(h.fix)}</p></div>`
      ).join("") +
      `<div class="card"><h4>Overall</h4><p style="margin:4px 0">${escapeHtml(report.overall_assessment)}</p></div>`;
  } catch (e) { fail(out, e); }
});

// ---------------- ALERTS ----------------
document.getElementById("alerts-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, out = document.getElementById("alerts-result");
  busy(out, "Checking live official alerts…");
  try {
    const data = await api("/api/alerts", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city: f.elements.city.value.trim(), language: lang() }),
    });
    out.innerHTML = renderBrief(data.brief, "🚨 Current alerts (grounded in live search)");
  } catch (e) { fail(out, e); }
});

// ---------------- ADVISORY ----------------
document.getElementById("advisory-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, out = document.getElementById("advisory-result");
  busy(out, "Checking your route…");
  try {
    const data = await api("/api/advisory", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: f.elements.origin.value.trim(),
        destination: f.elements.destination.value.trim(),
        travel_date: f.elements.travel_date.value.trim() || "today",
        mode: f.elements.mode.value,
        language: lang(),
      }),
    });
    out.innerHTML = renderBrief(data.brief, "🚆 Travel advisory (grounded in live search)");
  } catch (e) { fail(out, e); }
});
