import { api, getUser } from "../api.js";
import { $, bannerHtml, showMessage, guard, options, GOALS, MUSCLES } from "../ui.js";
import { planCard } from "./plans.js";

export async function community(root) {
  root.innerHTML = `
    <h1>Community</h1>
    ${bannerHtml}
    <form class="card" id="form">
      <div class="row">
        <div class="grow"><label for="goal">Goal</label><select id="goal"><option value="">Any goal</option>${options(GOALS)}</select></div>
        <div class="grow"><label for="muscle">Muscle group</label><select id="muscle"><option value="">Any muscle group</option>${options(MUSCLES.map((m) => [m, m]))}</select></div>
        <button type="submit">Browse plans</button>
        <button type="button" class="outline" id="recommend">Recommend for me</button>
      </div>
      <p class="hint">"Recommend for me" needs a goal or a muscle group.</p>
    </form>
    <div id="list"></div>`;

  const msg = $("#msg", root);
  const filters = () => ({ goal: $("#goal", root).value, muscle_group: $("#muscle", root).value });
  let saved = new Set();

  function draw(list, heading) {
    $("#list", root).innerHTML = list.length
      ? `<p class="count-line">${heading}: ${list.length} ${list.length === 1 ? "plan" : "plans"}</p>` +
        list.map((p) => planCard(p, !p.is_public || p.user_id === getUser()?.id
          ? '<span class="muted small-text">Your plan</span>' // only other people\'s public plans can be saved
          : saved.has(p.id)
            ? '<button class="outline small unsave" type="button">Saved ✓ (remove)</button>'
            : '<button class="small save" type="button">Save plan</button>')).join("")
      : '<p class="count-line">No plans found</p>';
  }

  async function refreshSaved() {
    saved = new Set((await api.savedPlans()).plans.map((p) => p.id));
  }

  let last = { fn: () => api.communityPlans(filters()), heading: "Community plans" };
  async function run(fn, heading) {
    last = { fn, heading };
    await refreshSaved();
    draw((await fn()).plans, heading);
  }

  $("#form", root).addEventListener("submit", guard(msg, () => run(() => api.communityPlans(filters()), "Community plans")));
  $("#recommend", root).addEventListener("click", guard(msg, () => run(() => api.recommendations(filters()), "Recommended")));

  $("#list", root).addEventListener("click", guard(msg, async (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    if (e.target.closest(".save")) await api.savePlan(card.dataset.id);
    else if (e.target.closest(".unsave")) await api.unsavePlan(card.dataset.id);
    else return;
    await run(last.fn, last.heading);
  }));

  try { await run(last.fn, last.heading); } catch (err) { showMessage(msg, err.message); }
}
