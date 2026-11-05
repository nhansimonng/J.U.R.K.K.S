import { api } from "../api.js";
import { $, esc, bannerHtml, showMessage, guard, today } from "../ui.js";

export async function workouts(root) {
  root.innerHTML = `
    <h1>Workouts</h1>
    ${bannerHtml}
    <form class="card" id="form">
      <h2>Log a set</h2>
      <div class="row">
        <div class="grow" style="flex:2"><label for="exercise">Exercise</label><input id="exercise" placeholder="Bench Press"></div>
        <div style="width:90px"><label for="sets">Sets</label><input id="sets" type="number" min="1" step="1"></div>
        <div style="width:90px"><label for="reps">Reps</label><input id="reps" type="number" min="1" step="1"></div>
        <div style="width:110px"><label for="weight">Weight</label><input id="weight" type="number" min="0" step="any"></div>
        <div style="width:90px"><label for="unit">Unit</label><select id="unit"><option>lb</option><option>kg</option></select></div>
        <div><label for="date">Date</label><input id="date" type="date" value="${today()}"></div>
        <button type="submit">Log</button>
      </div>
    </form>
    <div class="card"><h2>History</h2><div id="history"><p class="muted">Loading…</p></div></div>`;

  const msg = $("#msg", root);

  async function load() {
    const { logs } = await api.workoutHistory();
    $("#history", root).innerHTML = logs.length ? logs.map((l) => `
      <div class="list-item">
        <div><strong>${esc(l.exercise_name)}</strong><div class="muted small-text">${esc(l.log_date)}</div></div>
        <div>${l.sets} × ${l.reps} @ ${l.weight} ${esc(l.weight_unit)}
          <button class="danger small del" data-id="${esc(l.id)}" style="margin-left:.75rem">Delete</button></div>
      </div>`).join("") : '<p class="muted">No workouts logged yet</p>';
  }

  $("#form", root).addEventListener("submit", guard(msg, async () => {
    const name = $("#exercise", root).value.trim();
    if (!name) return showMessage(msg, "Enter an exercise name");
    await api.logWorkout({
      exercise_name: name,
      sets: Number($("#sets", root).value), reps: Number($("#reps", root).value),
      weight: Number($("#weight", root).value || 0), weight_unit: $("#unit", root).value,
      log_date: $("#date", root).value
    });
    await load();
  }));

  $("#history", root).addEventListener("click", guard(msg, async (e) => {
    const btn = e.target.closest(".del");
    if (!btn) return;
    await api.deleteWorkout(btn.dataset.id);
    await load();
  }));

  try { await load(); } catch (err) { showMessage(msg, err.message); }
}
