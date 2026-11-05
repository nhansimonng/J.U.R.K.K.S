import { api } from "../api.js";
import { $, esc, bannerHtml, showMessage, guard, kmToMi, miToKm } from "../ui.js";

export function gyms(root) {
  root.innerHTML = `
    <h1>Find a gym</h1>
    <form class="card" id="form">
      <div class="row">
        <div class="grow"><label for="query">Gym name or location</label><input id="query" type="search" placeholder="Planet Fitness, San Jose..."></div>
        <button type="submit">Search</button>
      </div>
      <div class="row" style="margin-top:1rem">
        <div class="grow"><label for="equipment">Equipment (optional)</label><input id="equipment" placeholder="squat rack, leg press"></div>
        <div><label for="radius">Distance</label>
          <select id="radius"><option value="5">5 miles</option><option value="10" selected>10 miles</option><option value="20">20 miles</option><option value="30">30 miles</option></select></div>
        <button type="button" class="outline" id="locate">Use my location</button>
      </div>
      <p class="hint">Separate equipment with commas. Only gyms that have all of it are shown.</p>
    </form>
    ${bannerHtml}
    <div id="results"></div>`;

  const msg = $("#msg", root);
  const results = $("#results", root);
  let coords = null; // set by "Use my location"

  function draw(list) {
    if (!list.length) { results.innerHTML = '<p class="count-line">No gyms found</p>'; return; }
    results.innerHTML = `<p class="count-line">${list.length} ${list.length === 1 ? "gym" : "gyms"} found</p>
      <div class="grid">${list.map((g) => `
        <div class="card">
          <a class="gym-name" href="#/gyms/${encodeURIComponent(g.id)}">${esc(g.name)}</a>
          <div class="muted">${esc(g.address)}${g.distance_km != null ? ` · ${kmToMi(g.distance_km)} mi` : ""}</div>
          <div>${g.average_rating == null
            ? '<span class="muted">No reviews yet</span>'
            : `<span class="stars">★★★★★</span><span class="rating-num">${g.average_rating}</span><span class="muted small-text">(${g.review_count} ${g.review_count === 1 ? "review" : "reviews"})</span>`}</div>
          <div class="spacer"></div>
          <div><a class="btn outline small" href="#/gyms/${encodeURIComponent(g.id)}">View gym</a></div>
        </div>`).join("")}</div>`;
  }

  async function search() {
    const miles = Number($("#radius", root).value);
    const { gyms: list } = await api.searchGyms({
      query: $("#query", root).value.trim(),
      equipment: $("#equipment", root).value.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean).join(","),
      lat: coords?.lat, lng: coords?.lng, radius_km: Math.round(miToKm(miles) * 10) / 10
    });
    draw(list);
  }

  $("#form", root).addEventListener("submit", guard(msg, search));
  $("#locate", root).addEventListener("click", guard(msg, () => new Promise((resolve) => {
    if (!navigator.geolocation) { showMessage(msg, "Location is not available in this browser"); return resolve(); }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        try { await search(); } catch (err) { showMessage(msg, err.message); }
        resolve();
      },
      () => { showMessage(msg, "Could not get your location. Search by name instead."); resolve(); }
    );
  })));
}
