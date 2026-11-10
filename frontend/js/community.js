import { api, requireLogin, renderNavbar, el, showError, showSuccess, clearMessage, withBusy } from './common.js?v=merged-5';

const PAGE_SIZE = 20;

if (requireLogin()) {
  renderNavbar('community.html');
  init();
}

function init() {
  const plansBox = document.getElementById('plans');
  const empty = document.getElementById('empty');
  const loadMore = document.getElementById('load-more');
  const filterForm = document.getElementById('filter-form');
  const tabBrowse = document.getElementById('tab-browse');
  const tabSaved = document.getElementById('tab-saved');

  const tabRecommended = document.getElementById('tab-recommended');
  let requestVersion = 0;
  let view = 'browse';
  let offset = 0;
  const savedIds = new Set();

  function setView(next) {
    view = next;
    for (const [button, mode] of [[tabBrowse, 'browse'], [tabSaved, 'saved'], [tabRecommended, 'recommended']]) {
      button.setAttribute('aria-pressed', String(view === mode));
      button.className = view === mode ? 'btn' : 'btn btn-secondary';
    }
    filterForm.hidden = view === 'saved';
    document.getElementById('recommendation-hint').hidden = view !== 'recommended';
    clearMessage();
    reload();
  }

  tabRecommended.addEventListener('click', () => setView('recommended'));
  tabBrowse.addEventListener('click', () => setView('browse'));
  tabSaved.addEventListener('click', () => setView('saved'));
  filterForm.addEventListener('submit', event => { event.preventDefault(); clearMessage(); reload(); });
  document.getElementById('clear-filter').addEventListener('click', () => {
    document.getElementById('goal').value = '';
    document.getElementById('muscle-group').value = '';
    clearMessage();
    reload();
  });
  loadMore.addEventListener('click', () => withBusy(loadMore, () => fetchPage(true)));

  async function loadSavedIds() {
    try {
      const { plans } = await api.savedPlans();
      savedIds.clear();
      plans.forEach(p => savedIds.add(p.id));
    } catch (error) {
      showError(error.message);
    }
  }

  async function reload() {
    const version = ++requestVersion;
    offset = 0;
    plansBox.replaceChildren();
    loadMore.hidden = true;
    empty.hidden = true;
    await loadSavedIds();
    if (version === requestVersion) await fetchPage(false);
  }

  async function fetchPage(append) {
    if (append && view !== 'browse') return;
    const version = requestVersion;
    try {
      let plans;
      if (view === 'saved') {
        ({ plans } = await api.savedPlans());
        if (version !== requestVersion) return;
        empty.textContent = 'You have not saved any plans yet. Browse community plans and click Save.';
      } else if (view === 'recommended') {
        const goal = document.getElementById('goal').value;
        const muscle_group = document.getElementById('muscle-group').value.trim();
        if (!goal && !muscle_group) {
          empty.textContent = 'Choose a goal or muscle group, then click Filter.';
          empty.hidden = false;
          return;
        }
        ({ plans } = await api.recommendations({ goal, muscle_group }));
        if (version !== requestVersion) return;
        empty.textContent = 'No matching plans yet. Try another filter or create a plan in My Plans.';
      } else {
        ({ plans } = await api.publicPlans({
          goal: document.getElementById('goal').value,
          muscle_group: document.getElementById('muscle-group').value.trim(),
          limit: PAGE_SIZE,
          offset
        }));
        if (version !== requestVersion) return;
        empty.textContent = 'No community plans match those filters.';
        offset += plans.length;
        loadMore.hidden = plans.length < PAGE_SIZE;
      }
      if (!append) plansBox.replaceChildren();
      plans.forEach(plan => plansBox.append(planCard(plan)));
      empty.hidden = plansBox.children.length > 0;
    } catch (error) {
      showError(error.message);
    }
  }

  function planCard(plan) {
    const saveButton = el('button', { type: 'button' });
    const paint = () => {
      const saved = savedIds.has(plan.id);
      saveButton.className = saved ? 'btn btn-secondary btn-small' : 'btn btn-small';
      saveButton.textContent = saved ? 'Saved ✓ (click to remove)' : 'Save';
      saveButton.setAttribute('aria-label', `${saved ? 'Remove bookmark for' : 'Save'} ${plan.name}`);
    };
    paint();

    saveButton.addEventListener('click', () => withBusy(saveButton, async () => {
      clearMessage();
      try {
        if (savedIds.has(plan.id)) {
          await api.unsavePlan(plan.id);
          savedIds.delete(plan.id);
          if (view === 'saved') { card.remove(); empty.hidden = plansBox.children.length > 0; return; }
          showSuccess('Removed from saved plans.');
        } else {
          await api.savePlan(plan.id);
          savedIds.add(plan.id);
          showSuccess('Plan saved.');
        }
        paint();
      } catch (error) {
        showError(error.message);
      }
    }));

    const card = el('article', { class: 'card' },
      el('h3', { text: plan.name }),
      plan.author_username ? el('p', { class: 'muted small', text: `by ${plan.author_username}` }) : null,
      el('p', {}, plan.fitness_goal
        ? el('span', { class: 'badge', text: plan.fitness_goal.replace(/_/g, ' ') }) : null),
      el('ul', { class: 'list' }, plan.exercises.map(ex =>
        el('li', {},
          el('strong', { text: ex.name }),
          el('span', { class: 'muted', text: ` · ${ex.sets} × ${ex.reps}` }),
          ex.muscle_group ? el('span', { class: 'muted small', text: ` · ${ex.muscle_group}` }) : null,
          ex.required_equipment?.length
            ? el('div', { class: 'small muted', text: `Needs: ${ex.required_equipment.join(', ')}` }) : null))),
      plan.is_public ? el('div', { style: 'margin-top: 0.75rem;' }, saveButton)
        : el('p', { class: 'hint', text: 'Your private plan · edit it in My Plans.' }));
    return card;
  }

  reload();
}