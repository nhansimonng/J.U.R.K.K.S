import { api, requireLogin, renderNavbar, el, showError, showSuccess, clearMessage, withBusy, todayISO } from './common.js';

if (requireLogin()) {
  renderNavbar('calories.html');
  init();
}

function init() {
  const dateInput = document.getElementById('log-date');
  const totalBox = document.getElementById('daily-total');
  const table = document.getElementById('entries-table');
  const body = document.getElementById('entries-body');
  const empty = document.getElementById('empty');
  const searchForm = document.getElementById('search-form');
  const results = document.getElementById('food-results');
  const status = document.getElementById('search-status');
  const banner = document.getElementById('cache-banner');
  const logForm = document.getElementById('log-form');
  let selected = null;

  dateInput.value = todayISO();

  const fmt = n => Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 });

  // ---------- Daily log ----------
  async function loadDay() {
    if (!dateInput.value) return;
    try {
      const day = await api.calorieLogs(dateInput.value);
      totalBox.textContent = fmt(day.daily_total);
      body.replaceChildren();
      table.hidden = day.entries.length === 0;
      empty.hidden = day.entries.length > 0;

      for (const entry of day.entries) {
        const del = el('button', {
          class: 'btn btn-danger btn-small', type: 'button', text: 'Delete',
          'aria-label': `Delete ${entry.food_name}`,
          onclick: () => removeEntry(entry, del)
        });
        body.append(el('tr', {},
          el('td', { text: entry.food_name }),
          el('td', { text: `${fmt(entry.portion)} ${entry.portion_unit || ''}`.trim() }),
          el('td', { text: `${fmt(entry.calories)} kcal` }),
          el('td', {}, del)));
      }
    } catch (error) {
      showError(error.message);
    }
  }

  async function removeEntry(entry, button) {
    clearMessage();
    await withBusy(button, async () => {
      try {
        await api.deleteCalorieLog(entry.id);
        await loadDay();
        showSuccess('Entry deleted.');
      } catch (error) {
        showError(error.message);
      }
    });
  }

  dateInput.addEventListener('change', () => { clearMessage(); loadDay(); });

  // ---------- Food search ----------
  searchForm.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();
    banner.hidden = true;

    const text = document.getElementById('food-query').value.trim();
    if (!text) return showError('Enter a food name.');

    const button = searchForm.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        const data = await api.foods(text);
        banner.hidden = !data.cached_only;
        status.textContent = data.foods.length ? `${data.foods.length} result(s)` : 'No foods found.';
        results.replaceChildren(...data.foods.map(food =>
          el('li', { class: 'row', style: 'justify-content: space-between; align-items: center;' },
            el('span', {},
              el('strong', { text: food.name }),
              el('span', { class: 'muted small', text: ` · ${fmt(food.reference_calories)} kcal per ${food.reference_portion} ${food.reference_unit}` })),
            el('button', { class: 'btn btn-secondary btn-small', type: 'button', text: 'Select',
              'aria-label': `Select ${food.name}`, onclick: () => selectFood(food) }))));
      } catch (error) {
        showError(error.message);
      }
    });
  });

  function selectFood(food) {
    selected = food;
    document.getElementById('selected-food').textContent = food.name;
    document.getElementById('selected-ref').textContent =
      `${fmt(food.reference_calories)} kcal per ${food.reference_portion} ${food.reference_unit}`;
    logForm.hidden = false;
    document.getElementById('portion').focus();
  }

  document.getElementById('cancel-food').addEventListener('click', () => { selected = null; logForm.hidden = true; });

  // ---------- Log a food ----------
  logForm.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();
    if (!selected) return showError('Pick a food first.');

    const portion = Number(document.getElementById('portion').value);
    if (!(portion > 0)) return showError('Portion must be greater than 0.');
    if (!dateInput.value) return showError('Pick a date.');

    const button = logForm.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        await api.addCalorieLog({
          food_id: selected.food_id,
          food_name: selected.name,
          portion,
          portion_unit: document.getElementById('portion-unit').value,
          log_date: dateInput.value
        });
        logForm.hidden = true;
        selected = null;
        document.getElementById('portion').value = '';
        await loadDay();
        showSuccess('Food logged.');
      } catch (error) {
        showError(error.message); // portion stays in the form
      }
    });
  });

  loadDay();
}