(() => {
  const $ = (id) => document.getElementById(id);
  const store = {
    get: (area, k) => { try { return window[area].getItem(k) || ""; } catch (e) { return ""; } },
    set: (area, k, v) => { try { window[area].setItem(k, v); } catch (e) {} },
    del: (area, k) => { try { window[area].removeItem(k); } catch (e) {} }
  };
  const form = $("studio-form");
  const apiInput = $("api-base");
  const tokenInput = $("token");
  const duration = $("duration");
  const MAX_POLL_ERRORS = 4;
  let pollTimer = null;
  let polling = false;
  let pollErrors = 0;

  apiInput.value = store.get("localStorage", "zi_api_base");
  tokenInput.value = store.get("sessionStorage", "zi_token");
  duration.addEventListener("input", () => $("duration-value").textContent = duration.value);
  apiInput.addEventListener("change", () => store.set("localStorage", "zi_api_base", apiInput.value.trim()));
  tokenInput.addEventListener("change", () => store.set("sessionStorage", "zi_token", tokenInput.value));

  function setNotice(message, error = false) {
    $("notice").textContent = message;
    $("notice").style.color = error ? "#ff9b9b" : "";
  }
  function setStatus(value) { $("status").textContent = String(value || "UNKNOWN").toUpperCase(); }
  function apiUrl(path) {
    const base = apiInput.value.trim().replace(/\/$/, "");
    if (!base) throw new Error("Enter your deployed FastAPI backend URL first.");
    return base + path;
  }
  // FastAPI returns a string for HTTPException and an array of objects for validation errors.
  function errorText(data, status) {
    const d = data && (data.detail || data.error);
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((e) => (e.msg || "Invalid value").replace(/^Value error, /, "")).join(" ");
    return "Backend request failed (" + status + ").";
  }
  async function request(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (tokenInput.value) headers.Authorization = "Bearer " + tokenInput.value;
    const response = await fetch(apiUrl(path), { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorText(data, response.status));
    return data;
  }
  function stopPolling() { clearInterval(pollTimer); pollTimer = null; $("generate").disabled = false; }

  function showResult(job) {
    const audioPath = typeof job.audio_url === "string" &&
      /^\/api\/generations\/[A-Za-z0-9_-]{4,64}\/audio$/.test(job.audio_url)
      ? job.audio_url : null;
    const audioUrl = audioPath ? apiUrl(audioPath) : null;
    if (!audioUrl) throw new Error("The job finished but the backend returned no audio URL.");
    $("player").src = audioUrl;
    $("player").hidden = false;
    $("download").href = audioUrl;
    $("download").hidden = false;
    if ($("to-release")) {
      $("to-release").href = "releases.html?job=" + encodeURIComponent(job.id);
      $("to-release").hidden = false;
    }
    $("job-id").textContent = job.id;
    $("result-title").textContent = job.track_name || "Your generated track";
    const mins = job.duration ? " (" + Math.floor(job.duration / 60) + ":" + String(job.duration % 60).padStart(2, "0") + ")" : "";
    $("result-description").textContent = "Your track is ready" + mins + ". Listen to the whole thing before releasing: sections are generated separately.";
    setNotice("Generation complete.");
  }

  async function poll(jobId) {
    if (polling) return;
    polling = true;
    try {
      const job = await request("/api/generations/" + encodeURIComponent(jobId));
      pollErrors = 0;
      setStatus(job.status);
      if (job.status === "succeeded") {
        stopPolling();
        store.del("localStorage", "zi_last_job");
        showResult(job);
      } else if (job.status === "failed" || job.status === "canceled") {
        stopPolling();
        store.del("localStorage", "zi_last_job");
        $("result-title").textContent = "Generation did not complete";
        setNotice(job.error || "Generation did not complete.", true);
      } else {
        setNotice("Generating sections: " + (job.segments_done || 0) + "/" + (job.segments_total || "?") + " done. This takes a few minutes; you can leave this page and come back.");
      }
    } catch (error) {
      // A single network blip should not abandon a paid job: retry a few times, then stop.
      pollErrors += 1;
      if (/not found/i.test(error.message) || pollErrors >= MAX_POLL_ERRORS) {
        stopPolling();
        setNotice(error.message + " (job " + jobId + ")", true);
      } else {
        setNotice("Connection hiccup, retrying… (" + pollErrors + "/" + MAX_POLL_ERRORS + ")", true);
      }
    } finally {
      polling = false;
    }
  }

  function startPolling(jobId) {
    clearInterval(pollTimer);
    pollErrors = 0;
    $("generate").disabled = true;
    $("job-id").textContent = jobId;
    store.set("localStorage", "zi_last_job", jobId);
    pollTimer = setInterval(() => poll(jobId), 8000);
    return poll(jobId);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearInterval(pollTimer);
    $("generate").disabled = true;
    $("player").hidden = true;
    $("download").hidden = true;
    if ($("to-release")) $("to-release").hidden = true;
    $("result-title").textContent = "Creating your track…";
    $("result-description").textContent = "Your request is being sent to the backend.";
    setStatus("QUEUED");
    setNotice("Connecting to Zi backend…");
    try {
      const health = await request("/api/health");
      if (health.status !== "ok") throw new Error("The backend health check did not pass.");
      $("engine").textContent = "Replicate · " + health.model;
      if (!health.provider_configured) throw new Error("The backend has no REPLICATE_API_TOKEN set.");
      if (!health.ffmpeg) throw new Error("The backend has no ffmpeg installed.");
      if (health.auth_required && !tokenInput.value) throw new Error("This backend requires an admin token. Enter it below and try again.");
      if (!health.license_commercial_confirmed) $("result-description").textContent = "Note: the model licence is not cleared for commercial use, so RouteNote packaging will stay blocked.";
      const payload = {
        track_name: $("track-name").value.trim() || "Untitled track",
        prompt: [
          $("prompt").value.trim(),
          "Genre: " + $("genre").value,
          "Mood: " + $("mood").value,
          "Lead instruments: " + $("instruments").value,
          "Energy: " + $("energy").value
        ].join(". "),
        duration: Number(duration.value)
      };
      const job = await request("/api/generations", { method: "POST", body: JSON.stringify(payload) });
      setStatus(job.status);
      setNotice("Generation started. Checking progress…");
      await startPolling(job.id);
    } catch (error) {
      setStatus("ERROR");
      setNotice(error.message, true);
      $("result-title").textContent = "Could not start generation";
      $("generate").disabled = false;
    }
  });

  // Resume a job that was running when the page was closed or reloaded.
  const last = store.get("localStorage", "zi_last_job");
  if (last && apiInput.value.trim()) {
    setStatus("RESUMING");
    $("result-title").textContent = "Resuming your last track…";
    setNotice("Checking on your previous generation…");
    startPolling(last);
  }
})();
