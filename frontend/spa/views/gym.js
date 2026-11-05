import { api } from "../api.js";
import { $, esc, bannerHtml, showMessage, clearMessage, guard, stars, options, goalLabel } from "../ui.js";

const MAX_PHOTO_BYTES = 500 * 1024; // 500 KB, contract default (Open Items)

// Shrink the image in the browser so it fits under the upload limit.
async function compress(file) {
  if (file.size <= MAX_PHOTO_BYTES) return file;
  const bmp = await createImageBitmap(file);
  let scale = Math.min(1, 1600 / Math.max(bmp.width, bmp.height)), quality = 0.85, blob;
  for (let i = 0; i < 8; i++) {
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    blob = await new Promise((r) => c.toBlob(r, "image/jpeg", quality));
    if (blob.size <= MAX_PHOTO_BYTES) break;
    quality -= 0.1; scale *= 0.85;
  }
  return new File([blob], file.name.replace(/\.\w+$/, ".jpg"), { type: "image/jpeg" });
}

export async function gym(root, { id }) {
  root.innerHTML = `
    <p><a href="#/gyms">← Back to search</a></p>
    ${bannerHtml}
    <div id="info" class="card"><p class="muted">Loading…</p></div>

    <div class="card">
      <h2>Will my workout work here?</h2>
      <div class="row"><div class="grow"><label for="plan">Choose one of your plans</label><select id="plan"></select></div>
        <button type="button" id="check">Check</button></div>
      <div id="compat" style="margin-top:1rem"></div>
    </div>

    <div class="card">
      <h2>Equipment</h2>
      <div id="equipment"></div>
      <form id="eq-form" class="row" style="margin-top:1rem">
        <div class="grow"><label for="eq-name">Name</label><input id="eq-name" placeholder="leg press"></div>
        <div><label for="eq-avail">Availability</label><select id="eq-avail">${options(["available", "unavailable", "unconfirmed"].map((v) => [v, v]))}</select></div>
        <div><label for="eq-cond">Condition</label><select id="eq-cond">${options(["good", "fair", "worn", "broken"].map((v) => [v, v]))}</select></div>
        <button type="submit">Add</button>
      </form>
    </div>

    <div class="card">
      <h2>Write a review</h2>
      <form id="review-form">
        <div class="row">
          <div><label for="rating">Rating</label><select id="rating">${options([5, 4, 3, 2, 1].map((n) => [n, `${n} ★`]))}</select></div>
          <div class="grow"><label for="busy">Busy hours</label><input id="busy" placeholder="5pm-8pm"></div>
          <div class="grow"><label for="photo">Photo (.jpg / .png)</label><input id="photo" type="file" accept=".jpg,.jpeg,.png"></div>
        </div>
        <div class="field" style="margin-top:1rem"><label for="text">Review (max 1,000 characters)</label><textarea id="text" rows="3" maxlength="1000"></textarea></div>
        <button type="submit">Submit review</button>
      </form>
    </div>

    <div class="card"><h2>Reviews</h2><div id="reviews"></div></div>`;

  const msg = $("#msg", root);

  async function loadGym() {
    const g = await api.getGym(id);
    $("#info", root).innerHTML = `
      <h1 style="margin-bottom:.25rem">${esc(g.name)}</h1>
      <div class="muted">${esc(g.address)}</div>
      <p>${g.average_rating == null ? '<span class="muted">No reviews yet</span>'
        : `<span class="stars">${stars(g.average_rating)}</span><span class="rating-num">${g.average_rating}</span><span class="muted small-text">(${g.review_count} reviews)</span>`}</p>
      ${g.busy_hours.length ? `<p class="muted small-text">Busy: ${g.busy_hours.map((b) => `${esc(b.label)} (${b.mentions} ${b.mentions === 1 ? "mention" : "mentions"})`).join(", ")}</p>` : ""}`;
    $("#equipment", root).innerHTML = g.equipment.length ? g.equipment.map((e) => `
      <div class="list-item"><strong>${esc(e.name)}</strong>
        <span><span class="badge ${esc(e.availability)}">${esc(e.availability)}</span> <span class="badge ${esc(e.condition)}">${esc(e.condition)}</span></span>
      </div>`).join("") : '<p class="muted">No equipment info yet. Add what you see.</p>';
  }

  async function loadReviews() {
    const { reviews } = await api.listReviews(id);
    $("#reviews", root).innerHTML = reviews.length ? reviews.map((r) => `
      <div class="review" data-id="${esc(r.id)}">
        <div class="between"><strong>${esc(r.username)}</strong><span class="stars">${stars(r.rating)}</span></div>
        <div class="muted small-text">${new Date(r.created_at).toLocaleDateString()}${r.busy_hour_info ? " · busy " + esc(r.busy_hour_info) : ""}</div>
        ${r.review_text ? `<p>${esc(r.review_text)}</p>` : ""}
        ${r.photo_url ? `<img src="${esc(r.photo_url)}" alt="Review photo">` : ""}
        <button class="danger small report-btn" type="button">Report</button>
        <form class="report-form row hidden" style="margin-top:.6rem">
          <div class="grow"><input class="reason" placeholder="Why are you reporting this review?"></div>
          <button class="small" type="submit">Send report</button>
        </form>
      </div>`).join("") : '<p class="muted">No reviews yet. Be the first.</p>';
  }

  async function loadPlans() {
    const { plans } = await api.myPlans();
    $("#plan", root).innerHTML = plans.length ? options(plans.map((p) => [p.id, `${p.name} (${goalLabel(p.fitness_goal)})`]))
      : '<option value="">No plans yet — build one in My Plans</option>';
    $("#check", root).disabled = !plans.length;
  }

  $("#check", root).addEventListener("click", guard(msg, async () => {
    const out = $("#compat", root);
    const res = await api.compatibility(id, $("#plan", root).value);
    out.innerHTML = `<p><span class="badge ${res.compatible ? "compatible" : "unavailable"}">${res.compatible ? "Everything is available" : "Some exercises won't work here"}</span></p>` +
      res.results.map((r) => `
        <div class="list-item" style="display:block">
          <div class="between"><strong>${esc(r.exercise_name)}</strong><span class="badge ${esc(r.status)}">${esc(r.status)}</span></div>
          ${r.missing_equipment.length ? `<div class="muted small-text">Missing: ${r.missing_equipment.map(esc).join(", ")}</div>` : ""}
          ${r.status === "unavailable" ? (r.alternatives.length
            ? r.alternatives.map((a) => `<div class="alt">Try: ${esc(a.name)} (${esc(a.muscle_group)}, needs ${a.required_equipment.map(esc).join(", ")})</div>`).join("")
            : '<div class="alt">No alternative found</div>') : ""}
        </div>`).join("");
  }));

  $("#eq-form", root).addEventListener("submit", guard(msg, async () => {
    const name = $("#eq-name", root).value.trim().toLowerCase(); // contract: lowercase names
    if (!name) return showMessage(msg, "Enter an equipment name");
    await api.addEquipment(id, { name, availability: $("#eq-avail", root).value, condition: $("#eq-cond", root).value });
    $("#eq-name", root).value = "";
    await loadGym();
  }));

  $("#review-form", root).addEventListener("submit", guard(msg, async () => {
    let photo_path = null;
    const file = $("#photo", root).files[0];
    if (file) {
      if (!/\.(jpe?g|png)$/i.test(file.name)) throw new Error("Only .jpg and .png files are allowed");
      photo_path = (await api.uploadPhoto(await compress(file))).photo_path;
    }
    await api.submitReview(id, {
      rating: Number($("#rating", root).value),
      review_text: $("#text", root).value.trim() || null,
      busy_hour_info: $("#busy", root).value.trim() || null,
      photo_path
    });
    $("#text", root).value = ""; $("#busy", root).value = ""; $("#photo", root).value = "";
    await Promise.all([loadGym(), loadReviews()]);
    showMessage(msg, "Review posted", "ok");
  }));

  root.addEventListener("click", (e) => {
    const btn = e.target.closest(".report-btn");
    if (btn) btn.parentElement.querySelector(".report-form").classList.toggle("hidden");
  });
  root.addEventListener("submit", (e) => {
    const form = e.target.closest(".report-form");
    if (!form) return; // other forms have their own handlers
    guard(msg, async () => {
      await api.reportReview(form.closest(".review").dataset.id, form.querySelector(".reason").value);
      form.classList.add("hidden");
      showMessage(msg, "Report submitted. Thank you.", "ok");
    })(e);
  });

  try { await Promise.all([loadGym(), loadReviews(), loadPlans()]); }
  catch (err) { clearMessage(msg); showMessage(msg, err.message); }
}
