import { api, requireLogin, renderNavbar, el, showError, showSuccess, clearMessage, withBusy } from './common.js?v=account-1';

if (requireLogin()) {
  renderNavbar('plans.html');
  init();
}

function init() {
  const form = document.getElementById('plan-form');
  const rowsBox = document.getElementById('exercise-rows');
  const plansBox = document.getElementById('plans');
  const empty = document.getElementById('empty');
  let editingId = null; // null = creating a new plan

  // ---------- Exercise rows in the form ----------
  function addRow(ex = {}) {
    const row = el('div', { class: 'card exercise-row' },
      el('div', { class: 'row' },
        field('Exercise', 'ex-name', el('input', { type: 'text', maxlength: '200', value: ex.name || '', placeholder: 'Bench Press' }), true),
        field('Muscle group', 'ex-muscle', el('input', { type: 'text', maxlength: '200', value: ex.muscle_group || '', placeholder: 'chest' }), true)),
      el('div', { class: 'row', style: 'margin-top: 0.75rem;' },
        field('Sets', 'ex-sets', el('input', { type: 'number', min: '1', step: '1', value: ex.sets ?? '' })),
        field('Reps', 'ex-reps', el('input', { type: 'number', min: '1', step: '1', value: ex.reps ?? '' })),
        field('Equipment needed', 'ex-equip', el('input', { type: 'text', value: (ex.required_equipment || []).join(', '), placeholder: 'barbell, bench' }), true),
        el('button', { class: 'btn btn-danger btn-small', type: 'button', text: 'Remove', onclick: () => row.remove() })));
    rowsBox.append(row);
  }

  function field(label, cls, input, grow = false) {
    input.classList.add(cls);
    input.id = `${cls}-${Math.random().toString(36).slice(2, 8)}`;
    return el('div', { class: grow ? 'grow' : null }, el('label', { for: input.id, text: label }), input);
  }

  function readRows() {
    return [...rowsBox.querySelectorAll('.exercise-row')].map(row => ({
      name: row.querySelector('.ex-name').value.trim(),
      muscle_group: row.querySelector('.ex-muscle').value.trim() || null,
      sets: Number(row.querySelector('.ex-sets').value),
      reps: Number(row.querySelector('.ex-reps').value),
      required_equipment: row.querySelector('.ex-equip').value
        .split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
    }));
  }

  // ---------- Open / close the form ----------
  function openForm(plan = null) {
    editingId = plan ? plan.id : null;
    document.getElementById('form-title').textContent = plan ? 'Edit plan' : 'New plan';
    document.getElementById('plan-name').value = plan?.name || '';
    document.getElementById('plan-public').checked = Boolean(plan?.is_public);

    const goal = document.getElementById('plan-goal');
    if (plan?.fitness_goal && ![...goal.options].some(o => o.value === plan.fitness_goal)) {
      goal.append(el('option', { value: plan.fitness_goal, text: plan.fitness_goal }));
    }
    goal.value = plan?.fitness_goal || '';

    rowsBox.replaceChildren();
    (plan?.exercises?.length ? plan.exercises : [{}]).forEach(addRow);
    form.hidden = false;
    form.scrollIntoView({ block: 'start' });
    document.getElementById('plan-name').focus();
  }

  function closeForm() { form.hidden = true; editingId = null; }

  document.getElementById('new-plan').addEventListener('click', () => { clearMessage(); openForm(); });
  document.getElementById('add-exercise').addEventListener('click', () => addRow());
  document.getElementById('cancel-form').addEventListener('click', closeForm);

  // ---------- Save ----------
  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();

    const name = document.getElementById('plan-name').value.trim();
    const exercises = readRows();
    if (!name) return showError('Plan name is required.');
    if (exercises.length === 0) return showError('Add at least one exercise.');
    const bad = exercises.some(e => !e.name || !Number.isInteger(e.sets) || e.sets < 1 || !Number.isInteger(e.reps) || e.reps < 1);
    if (bad) return showError('Each exercise needs a name, sets, and reps (whole numbers above 0).');

    const body = {
      name,
      fitness_goal: document.getElementById('plan-goal').value || null,
      is_public: document.getElementById('plan-public').checked,
      exercises
    };

    const button = form.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        if (editingId) await api.updatePlan(editingId, body);
        else await api.createPlan(body);
        const verb = editingId ? 'updated' : 'created';
        closeForm();
        await loadPlans();
        showSuccess(`Plan ${verb}.`);
      } catch (error) {
        showError(error.message); // form stays open with what the user typed
      }
    });
  });

  // ---------- List ----------
  async function loadPlans() {
    try {
      const { plans } = await api.myPlans();
      renderPlans(plans);
    } catch (error) {
      showError(error.message);
    }
  }

  function renderPlans(plans) {
    plansBox.replaceChildren();
    empty.hidden = plans.length > 0;

    for (const plan of plans) {
      const deleteButton = el('button', {
        class: 'btn btn-danger btn-small', type: 'button', text: 'Delete',
        'aria-label': `Delete plan ${plan.name}`,
        onclick: () => removePlan(plan, deleteButton)
      });
      plansBox.append(el('article', { class: 'card' },
        el('h3', { text: plan.name }),
        el('p', {},
          plan.fitness_goal ? el('span', { class: 'badge', text: plan.fitness_goal.replace(/_/g, ' ') }) : null,
          ' ',
          el('span', { class: plan.is_public ? 'badge badge-ok' : 'badge', text: plan.is_public ? 'Public' : 'Private' })),
        el('ul', { class: 'list' }, plan.exercises.map(ex =>
          el('li', {},
            el('strong', { text: ex.name }),
            el('span', { class: 'muted', text: ` · ${ex.sets} × ${ex.reps}` }),
            ex.muscle_group ? el('span', { class: 'muted small', text: ` · ${ex.muscle_group}` }) : null,
            ex.required_equipment?.length
              ? el('div', { class: 'small muted', text: `Needs: ${ex.required_equipment.join(', ')}` }) : null))),
        el('div', { class: 'row', style: 'margin-top: 0.75rem;' },
          el('button', { class: 'btn btn-secondary btn-small', type: 'button', text: 'Edit', onclick: () => { clearMessage(); openForm(plan); } }),
          deleteButton)));
    }
  }

  async function removePlan(plan, button) {
    if (!window.confirm(`Delete "${plan.name}"? This also removes its exercises and any bookmarks.`)) return;
    clearMessage();
    await withBusy(button, async () => {
      try {
        await api.deletePlan(plan.id);
        await loadPlans();
        showSuccess('Plan deleted.');
      } catch (error) {
        showError(error.message);
      }
    });
  }

  loadPlans();
}