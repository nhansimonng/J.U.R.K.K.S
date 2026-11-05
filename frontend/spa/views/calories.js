import { api } from "../api.js";
import { $, esc, bannerHtml, showMessage, clearMessage, guard, today } from "../ui.js";

export async function calories(root) {
  root.innerHTML = `
    <h1>Calories</h1>
    ${bannerHtml}
    <div class="card">
      <h2>Search foods</h2>
      <form id="food-form" class="row">
        <div class="grow"><label for="q">Food (USDA FoodData Central)</label><input id="q" type="search" placeholder="chicken"></div>
        <button type="submit">Search</button>
      </form>
      <div id="foods" style="margin-top:1rem"></div>
    </div>
    <form id="log-form" class="card hidden">
      <h2>Log: <span id="chosen"></span></h2>
      <div class="row">
        <div><label for="portion">Portion</label><input id="portion" type="number" min="0" step="any"></div>
        <div><label for="unit">Unit</label><select id="unit"><option>g</option><option>oz</option><option>cup</option><option>serving</option></select></div>
        <div><label for="date">Date</label><input id="date" type="date" value="${today()}"></div>
        <button type="submit">Add</button>
      </div>
    </form>
    <div class="card">
      <div class="between"><h2 style="margin:0">Daily total</h2><div class="total" id="total">0</div></div>
      <p class="muted" style="margin:0 0 .5rem">calories</p>
      <div id="entries"></div>
    </div>`;

  const msg = $("#msg", root);
  let chosen = null;

  async function loadDay() {
    const d = await api.dailyCalories($("#date", root).value || today());
    $("#total", root).textContent = Math.round(d.daily_total * 10) / 10;
    $("#entries", root).innerHTML = d.entries.length ? d.entries.map((e) => `
      <div class="list-item">
        <div><strong>${esc(e.food_name)}</strong><div class="muted small-text">${e.portion} ${esc(e.portion_unit)}</div></div>
        <div>${Math.round(e.calories * 10) / 10} cal <button class="danger small del" data-id="${esc(e.id)}" style="margin-left:.75rem">Delete</button></div>
      </div>`).join("") : '<p class="muted">Nothing logged for this day</p>';
  }

  $("#food-form", root).addEventListener("submit", guard(msg, async () => {
    const q = $("#q", root).value.trim();
    if (!q) return showMessage(msg, "Enter a food to search");
    const res = await api.searchFoods(q);
    if (res.cached_only) showMessage(msg, "Search temporarily unavailable; showing cached results only.", "warn");
    $("#foods", root).innerHTML = res.foods.length ? res.foods.map((f) => `
      <div class="list-item">
        <div><strong>${esc(f.name)}</strong><div class="muted small-text">${f.reference_calories} cal per ${f.reference_portion} ${esc(f.reference_unit)}</div></div>
        <button class="outline small pick" type="button" data-id="${esc(f.food_id)}" data-name="${esc(f.name)}">Select</button>
      </div>`).join("") : '<p class="muted">No foods found</p>';
  }));

  $("#foods", root).addEventListener("click", (e) => {
    const b = e.target.closest(".pick");
    if (!b) return;
    chosen = { food_id: b.dataset.id, food_name: b.dataset.name };
    $("#chosen", root).textContent = chosen.food_name;
    $("#log-form", root).classList.remove("hidden");
    $("#portion", root).focus();
  });

  $("#log-form", root).addEventListener("submit", guard(msg, async () => {
    await api.logFood({ ...chosen, portion: Number($("#portion", root).value), portion_unit: $("#unit", root).value, log_date: $("#date", root).value });
    $("#portion", root).value = "";
    await loadDay();
  }));

  $("#entries", root).addEventListener("click", guard(msg, async (e) => {
    const b = e.target.closest(".del");
    if (!b) return;
    await api.deleteCalorie(b.dataset.id);
    await loadDay();
  }));
  $("#date", root).addEventListener("change", guard(msg, loadDay));

  try { await loadDay(); } catch (err) { clearMessage(msg); showMessage(msg, err.message); }
}
