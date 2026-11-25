(() => {
  const $ = (id) => document.getElementById(id);
  $("api-base").value = localStorage.getItem("zi_api_base") || "";
  $("token").value = sessionStorage.getItem("zi_token") || "";
  const q = new URLSearchParams(location.search);
  if (q.get("job")) $("job-id").value = q.get("job");
  const base = () => $("api-base").value.trim().replace(/\/$/, "");
  const note = (m, err = false) => { $("notice").textContent = m; $("notice").style.color = err ? "#ff9b9b" : ""; };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(path, opts = {}) {
    if (!base()) throw new Error("Enter your backend URL first.");
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    if ($("token").value) headers.Authorization = "Bearer " + $("token").value;
    const r = await fetch(base() + path, { ...opts, headers });
    if (opts.raw && r.ok) return r;
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Request failed (" + r.status + ").");
    return d;
  }
  function brief() {
    return { title: $("title").value.trim(), prompt: $("prompt").value.trim() || $("title").value.trim(),
      artist: $("artist").value.trim(), genre: $("genre").value.trim(), label: $("label").value.trim() };
  }
  function metadata() {
    const b = brief(), y = new Date().getFullYear(), label = b.label || "Zi";
    return { title: b.title, primary_artist: b.artist, label, genre: b.genre || "Electronic",
      release_date: $("release-date").value || null, c_line: y + " " + label, p_line: y + " " + label,
      prompt: b.prompt, tracks: [{ title: b.title, artist: b.artist }] };
  }
  async function download(id) {
    try {
      const r = await api("/api/releases/" + id + "/package", { raw: true });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob()); a.download = "routenote-" + id + ".zip"; a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { note(e.message, true); }
  }
  async function markSubmitted(id) {
    const ref = prompt("Paste the RouteNote release URL or UPC:");
    if (!ref) return;
    try { await api("/api/releases/" + id + "/submitted", { method: "POST", body: JSON.stringify({ routenote_ref: ref }) }); refresh(); }
    catch (e) { note(e.message, true); }
  }
  async function refresh() {
    try {
      const [rels, queue, h] = await Promise.all([api("/api/releases"), api("/api/bot/queue"), api("/api/health")]);
      $("health-note").textContent = h.license_commercial_confirmed
        ? "Model " + h.model + ": commercial licence confirmed by operator. AI disclosure is included; AI music is excluded from Content ID."
        : "Model " + h.model + " is NOT cleared for commercial distribution (MusicGen weights are non-commercial). Packaging is blocked until the operator confirms a commercial licence.";
      $("list").innerHTML = rels.length ? "" : "Nothing yet.";
      for (const r of rels) {
        const d = document.createElement("div"); d.className = "job-meta";
        d.innerHTML = "<span>" + esc(r.status).toUpperCase() + "</span><strong>" + esc(r.metadata?.title || r.id) + "</strong>";
        if (r.package_path) { const b = document.createElement("button"); b.className = "download"; b.textContent = "Package ↓"; b.onclick = () => download(r.id); d.append(b); }
        if (r.status === "ready") { const b = document.createElement("button"); b.className = "download"; b.textContent = "Mark submitted"; b.onclick = () => markSubmitted(r.id); d.append(b); }
        if (r.error) d.append(Object.assign(document.createElement("small"), { textContent: r.error }));
        $("list").append(d);
      }
      $("queue").innerHTML = queue.map((i) => "<div class='job-meta'><span>" + esc(i.status).toUpperCase() + "</span><strong>" + esc(i.brief?.title) + "</strong></div>").join("") || "Queue is empty.";
    } catch (e) { note(e.message, true); }
  }
  $("api-base").addEventListener("change", () => localStorage.setItem("zi_api_base", $("api-base").value.trim()));
  $("token").addEventListener("change", () => sessionStorage.setItem("zi_token", $("token").value));
  $("refresh").onclick = refresh;
  $("queue-add").onclick = async () => {
    try { await api("/api/bot/queue", { method: "POST", body: JSON.stringify(brief()) }); note("Brief queued for the bot."); refresh(); }
    catch (e) { note(e.message, true); }
  };
  $("rel-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      note("Building package (download, convert, artwork)…");
      const body = JSON.stringify({ job_id: $("job-id").value.trim(), connector: "routenote", metadata: metadata() });
      const rel = await api("/api/releases", { method: "POST", body });
      const v = rel.validation || {};
      note(rel.status === "ready" ? "Package ready. " + (v.warnings || []).join(" ") : "Needs fixes: " + (v.errors || [rel.error]).join(" "), rel.status !== "ready");
      refresh();
    } catch (e) { note(e.message, true); }
  });
  if (base()) refresh();
})();
