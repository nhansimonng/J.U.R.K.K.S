import { api, requireLogin, renderNavbar, el, showError, showSuccess, clearMessage, withBusy, todayISO } from './common.js';

if (requireLogin()) {
  renderNavbar('workouts.html');
  init();
}

function init() {
  const form = document.getElementById('log-form');
  const filterForm = document.getElementById('filter-form');
  const body = document.getElementById('log-body');
  const table = document.getElementById('log-table');
  const empty = document.getElementById('empty');

  document.getElementById('log-date').value = todayISO();

  async function loadLogs() {
    try {
      const { logs } = await api.workoutLogs({
        from: document.getElementById('from').value,
        to: document.getElementById('to').value
      });
      render(logs);
    } catch (error) {
      showError(error.message);
    }
  }

  function render(logs) {
    body.replaceChildren();
    const hasLogs = logs.length > 0;
    table.hidden = !hasLogs;
    empty.hidden = hasLogs;
    empty.textContent = (document.getElementById('from').value || document.getElementById('to').value)
      ? 'No workouts in that date range.'
      : 'No workouts logged yet.';

    for (const log of logs) {
      const deleteButton = el('button', {
        class: 'btn btn-danger btn-small',
        type: 'button',
        text: 'Delete',
        'aria-label': `Delete ${log.exercise_name} on ${log.log_date}`,
        onclick: () => removeLog(log, deleteButton)
      });
      body.append(el('tr', {},
        el('td', { text: log.log_date }),
        el('td', { text: log.exercise_name }),
        el('td', { text: `${log.sets} × ${log.reps}` }),
        el('td', { text: `${log.weight} ${log.weight_unit}` }),
        el('td', {}, deleteButton)));
    }
  }

  async function removeLog(log, button) {
    if (!window.confirm(`Delete ${log.exercise_name} (${log.log_date})?`)) return;
    clearMessage();
    await withBusy(button, async () => {
      try {
        await api.deleteWorkoutLog(log.id);
        await loadLogs();
        showSuccess('Workout deleted.');
      } catch (error) {
        showError(error.message);
      }
    });
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();

    const exercise_name = document.getElementById('exercise').value.trim();
    const sets = Number(document.getElementById('sets').value);
    const reps = Number(document.getElementById('reps').value);
    const weightText = document.getElementById('weight').value;
    const weight = Number(weightText);
    const weight_unit = document.getElementById('weight-unit').value;
    const log_date = document.getElementById('log-date').value;

    // Quick checks for fast feedback; the backend checks again
    if (!exercise_name) return showError('Enter an exercise name.');
    if (!Number.isInteger(sets) || sets < 1 || !Number.isInteger(reps) || reps < 1) {
      return showError('Sets and reps must be positive whole numbers.');
    }
    if (weightText === '' || Number.isNaN(weight) || weight < 0) {
      return showError('Weight cannot be negative.');
    }
    if (!log_date) return showError('Pick a date.');

    const button = form.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        await api.addWorkoutLog({ exercise_name, sets, reps, weight, weight_unit, log_date });
        // Clear the exercise fields but keep date and unit for the next entry
        for (const id of ['exercise', 'sets', 'reps', 'weight']) document.getElementById(id).value = '';
        await loadLogs();
        showSuccess('Workout logged.');
      } catch (error) {
        showError(error.message); // typed values stay in the form
      }
    });
  });

  filterForm.addEventListener('submit', event => { event.preventDefault(); clearMessage(); loadLogs(); });
  document.getElementById('clear-filter').addEventListener('click', () => {
    document.getElementById('from').value = '';
    document.getElementById('to').value = '';
    clearMessage();
    loadLogs();
  });

  loadLogs();
}