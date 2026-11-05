import { api } from "../api.js";
import { $, esc, bannerHtml, showMessage, guard, options, GOALS, MUSCLES, goalLabel } from "../ui.js";

export const planCard = (p, actions = "") => `
  <div class="card" data-id="${esc(p.id)}">
    <div class="between">
      <h3 style="margin:0">${esc(p.name)}</h3>
      <span>${p.is_public ? '<span class="badge public">public</span> ' : ""}<span class="badge">${esc(goalLabel(p.fitness_goal))}</span></span>
    </div>
    ${p.author_username ? `<div class="muted small-text">by ${esc(p.author_username)}</div>` : ""}
    <ul class="exercise-list">${p.exercises.map((x) => `<li>${esc(x.name)} — ${x.sets} × ${x.reps} <span class="small-text">(${esc(x.muscle_group)}${(x.required_equipment || []).length ? "; " + x.required_equipment.map(esc).join(", ") : ""})</span></li>`).join("")}</ul>
    ${actions ? `<div style="margin-top:.6rem;display:flex;gap:.5rem;flex-wrap:wrap">${actions}</div>` : ""}
  </div>`;

const exerciseRow = (x = {}) => `
  <div class="exercise-row">
    <div><label>Exercise</label><input class="ex-name" value="${esc(x.name || "")}" placeholder="Bench Press"></div>
    <div><label>Muscle</label><select class="ex-muscle">${options(MUSCLES.map((m) => [m, m]), x.muscle_group)}</select></div>
    <div><label>Sets</label><input class="ex-sets" type="number" min="1" step="1" value="${x.sets ?? ""}"></div>
    <div><label>Reps</label><input class="ex-reps" type="number" min="1" step="1" value="${x.reps ?? ""}"></div>
    <div><label>Equipment</label><input class="ex-equip" value="${esc((x.required_equipment || []).join(", "))}" placeholder="barbell, bench"></div>
    <button type="button" class="danger small rm-ex" aria-label="Remove exercise">✕</button>
  </div>`;

export async function plans(root) {
  root.innerHTML = `
    <div class="between"><h1>My Plans</h1><button type="button" id="new">+ New plan</button></div>
    ${bannerHtml}
    <form class="card hidden" id="form" novalidate>
      <h2 id="form-title">New plan</h2>
      <div class="row">
        <div class="grow"><label for="name">Plan name</label><input id="name" placeholder="Push Day"></div>
        <div><label for="goal">Goal</label><select id="goal">${options(GOALS)}</select></div>
        <label class="check" style="margin-bottom:.7rem"><input type="checkbox" id="public"> Share with community</label>
      </div>
      <h3 style="margin-top:1rem">Exercises</h3>
      <div id="exercises"></div>
      <div class="row" style="margin-top:.5rem">
        <button type="button" class="outline" id="add-ex">+ Add exercise</button>
        <button type="submit">Save plan</button>
        <button type="button" class="outline" id="cancel">Cancel</button>
      </div>
    </form>
    <div class="tabs"><button type="button" class="active" data-tab="mine">My plans</button><button type="button" data-tab="saved">Saved</button></div>
    <div id="list"><p class="muted">Loading…</p></div>`;

  const msg = $("#msg", root);
  const form = $("#form", root);
  let tab = "mine", editingId = null, cache = [];

  const openForm = (plan) => {
    editingId = plan?.id || null;
    $("#form-title", root).textContent = plan ? "Edit plan" : "New plan";
    $("#name", root).value = plan?.name || "";
    $("#goal", root).value = plan?.fitness_goal || GOALS[0][0];
    $("#public", root).checked = !!plan?.is_public;
    $("#exercises", root).innerHTML = (plan?.exercises?.length ? plan.exercises : [{}]).map(exerciseRow).join("");
    form.classList.remove("hidden");
    $("#name", root).focus();
  };
  const closeForm = () => { form.classList.add("hidden"); editingId = null; };

  async function load() {
    const { plans: list } = tab === "mine" ? await api.myPlans() : await api.savedPlans();
    cache = list;
    $("#list", root).innerHTML = list.length ? list.map((p) => planCard(p, tab === "mine"
      ? `<button class="outline small edit" type="button">Edit</button><button class="danger small del" type="button">Delete</button>`
      : `<button class="outline small unsave" type="button">Remove from saved</button>`)).join("")
      : `<p class="muted">${tab === "mine" ? "You haven't built a plan yet." : "No saved plans yet. Browse the Community tab."}</p>`;
  }

  $("#new", root).addEventListener("click", () => openForm());
  $("#cancel", root).addEventListener("click", closeForm);
  $("#add-ex", root).addEventListener("click", () => $("#exercises", root).insertAdjacentHTML("beforeend", exerciseRow()));
  $("#exercises", root).addEventListener("click", (e) => { if (e.target.closest(".rm-ex")) e.target.closest(".exercise-row").remove(); });

  root.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", guard(msg, async () => {
    tab = b.dataset.tab;
    root.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
    await load();
  })));

  form.addEventListener("submit", guard(msg, async () => {
    const body = {
      name: $("#name", root).value.trim(),
      fitness_goal: $("#goal", root).value,
      is_public: $("#public", root).checked,
      exercises: [...root.querySelectorAll(".exercise-row")].map((r) => ({
        name: $(".ex-name", r).value.trim(), muscle_group: $(".ex-muscle", r).value,
        sets: Number($(".ex-sets", r).value), reps: Number($(".ex-reps", r).value),
        required_equipment: $(".ex-equip", r).value.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean)
      }))
    };
    if (!body.name) return showMessage(msg, "Plan name is required");
    if (!body.exercises.length || body.exercises.some((x) => !x.name || !(x.sets > 0) || !(x.reps > 0))) return showMessage(msg, "Each exercise needs a name, sets, and reps");
    if (editingId) await api.updatePlan(editingId, body); else await api.createPlan(body);
    closeForm();
    tab = "mine";
    root.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x.dataset.tab === "mine"));
    await load();
    showMessage(msg, "Plan saved", "ok");
  }));

  $("#list", root).addEventListener("click", guard(msg, async (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    const id = card.dataset.id;
    if (e.target.closest(".edit")) openForm(cache.find((p) => p.id === id));
    else if (e.target.closest(".del")) { await api.deletePlan(id); await load(); }
    else if (e.target.closest(".unsave")) { await api.unsavePlan(id); await load(); }
  }));

  try { await load(); } catch (err) { showMessage(msg, err.message); }
}
