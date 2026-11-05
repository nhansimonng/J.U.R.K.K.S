import { api, requireLogin, renderNavbar, el, showError, showSuccess, clearMessage, withBusy } from './common.js';

if (requireLogin()) {
  renderNavbar('community.html');
  init();
}

const PAGE_SIZE = 20;

function init() {
  const plansBox = document.getElementById('plans');
  const empty = document.getElementById('empty');
  const loadMore = document.getElementById('load-more');
  const filterForm = document.getElementById('filter-form');
  const tabBrowse = document.getElementById('tab-browse');
  const tabSaved = document.getElementById('tab-saved');

  let view = 'browse';
  let offset = 0;
  const savedIds = new Set();

  function setView(next) {
    view = next;
    const browsing = view === 'browse';
    tabBrowse.setAttribute('aria-pressed', String(browsing));
    tabSaved.setAttribute('aria-pressed', String(!browsing));
    tabBrowse.className = browsing ? 'btn' : 'btn btn-secondary';
    tabSaved.className = browsing ? 'btn btn-secondary' : 'btn';
    filterForm.hidden = !browsing;
    clearMessage();
    reload();
  }

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
    offset = 0;
    plansBox.replaceChildren();
    loadMore.hidden = true;
    empty.hidden = true;
    await loadSavedIds();
    await fetchPage(false);
  }

  async function fetchPage(append) {
    try {
      let plans;
      if (view === 'saved') {
        ({ plans } = await api.savedPlans());
        empty.textContent = 'You have not saved any plans yet. Browse community plans and click Save.';
      } else {
        ({ plans } = await api.publicPlans({
          goal: document.getElementById('goal').value,
          muscle_group: document.getElementById('muscle-group').value.trim(),
          limit: PAGE_SIZE,
          offset
        }));
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
      el('div', { style: 'margin-top: 0.75rem;' }, saveButton));
    return card;
  }

  reload();
}