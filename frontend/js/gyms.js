import {
  api, requireLogin, renderNavbar, el,
  showError, clearMessage, withBusy, starText
} from './common.js?v=account-1';

if (requireLogin()) {
  renderNavbar('gyms.html');
  start();
}

function start() {
  const form = document.getElementById('search-form');
  const queryInput = document.getElementById('query');
  const equipmentInput = document.getElementById('equipment');
  const radiusSelect = document.getElementById('radius');
  const nearMeButton = document.getElementById('near-me');
  const locationStatus = document.getElementById('location-status');
  const results = document.getElementById('results');
  const count = document.getElementById('result-count');

  let coords = null; // set when the user shares their location

  function gymLink(gym) {
    return `gym-detail.html?id=${encodeURIComponent(gym.id)}`;
  }

  function gymCard(gym) {
    const rating = gym.average_rating;
    const reviews = gym.review_count;

    const ratingLine = rating === null || rating === undefined
      ? el('p', { class: 'muted', text: 'No reviews yet' })
      : el('p', {},
          el('span', {
            class: 'stars', role: 'img',
            'aria-label': `Rated ${Number(rating).toFixed(1)} out of 5`,
            text: starText(rating)
          }),
          el('span', {
            class: 'muted small',
            text: ` (${reviews} review${reviews === 1 ? '' : 's'})`
          }));

    return el('article', { class: 'card' },
      el('h3', {}, el('a', { href: gymLink(gym), text: gym.name })),
      el('p', { class: 'muted small', text: gym.address || 'Address not listed' }),
      ratingLine,
      gym.distance_km != null &&
        el('p', { class: 'small', text: `${(gym.distance_km * 0.621371).toFixed(1)} miles away` }),
      el('a', { class: 'btn btn-secondary btn-small', href: gymLink(gym), text: 'View gym' }));
  }

  function renderGyms(gyms) {
    results.replaceChildren();
    if (!gyms.length) {
      count.textContent = '';
      results.append(el('p', { class: 'muted', text: 'No gyms found. Try a different name or area.' }));
      return;
    }
    count.textContent = `${gyms.length} gym${gyms.length === 1 ? '' : 's'} found`;
    gyms.forEach(gym => results.append(gymCard(gym)));
  }

  nearMeButton.addEventListener('click', () => {
    // Second click clears the saved location
    if (coords) {
      coords = null;
      nearMeButton.textContent = 'Use my location';
      locationStatus.textContent = '';
      return;
    }
    if (!navigator.geolocation) {
      locationStatus.textContent = 'Your browser cannot share your location.';
      return;
    }
    locationStatus.textContent = 'Finding your location…';
    navigator.geolocation.getCurrentPosition(
      position => {
        coords = { lat: position.coords.latitude, lng: position.coords.longitude };
        nearMeButton.textContent = 'Clear location';
        locationStatus.textContent = 'Using your location. Press Search.';
      },
      () => {
        locationStatus.textContent = 'Could not get your location. You can still search by name.';
      },
      { timeout: 10000 }
    );
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();

    const query = queryInput.value.trim();
    const equipment = equipmentInput.value.trim();
    if (!query && !equipment && !coords) {
      showError('Enter a gym name or location, or use your location.');
      return;
    }

    const filters = { query, equipment };
    if (coords) {
      filters.lat = coords.lat;
      filters.lng = coords.lng;
      filters.radius_km = radiusSelect.value;
    }

    const button = form.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      count.textContent = 'Searching…';
      try {
        const data = await api.gyms(filters);
        renderGyms(data.gyms);
      } catch (error) {
        count.textContent = '';
        showError(error.message);
      }
    });
  });
}