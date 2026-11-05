import {
  api, requireLogin, renderNavbar, el,
  showError, showSuccess, clearMessage, withBusy
} from './common.js';
import { compressImage } from './image-utils.js';

const gymId = new URLSearchParams(window.location.search).get('id');
const PAGE_SIZE = 20;

if (requireLogin()) {
  renderNavbar('gyms.html');
  if (gymId) start();
  else showError('No gym selected. Go back to the search page and pick one.');
}

function stars(rating) {
  return '★'.repeat(rating) + '☆'.repeat(5 - rating);
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function availabilityClass(availability) {
  if (availability === 'available') return 'badge badge-ok';
  if (availability === 'unavailable') return 'badge badge-bad';
  return 'badge';
}

function start() {
  const nameEl = document.getElementById('gym-name');
  const addressEl = document.getElementById('gym-address');
  const ratingEl = document.getElementById('gym-rating');
  const equipmentList = document.getElementById('equipment-list');
  const busyList = document.getElementById('busy-list');
  const reviewsEl = document.getElementById('reviews');
  const reviewCount = document.getElementById('review-count');
  const loadMore = document.getElementById('load-more');
  const form = document.getElementById('review-form');
  const textInput = document.getElementById('review-text');
  const busyInput = document.getElementById('busy-hours');
  const charCount = document.getElementById('char-count');
  const dialog = document.getElementById('report-dialog');
  const reportForm = document.getElementById('report-form');
  const reportReason = document.getElementById('report-reason');
  const reportError = document.getElementById('report-error');

    const photoInput = document.getElementById('photo');
  const photoStatus = document.getElementById('photo-status');
  const photoPreview = document.getElementById('photo-preview');
  const photoRemove = document.getElementById('photo-remove');
  const PHOTO_HINT = 'JPG or PNG. It is shrunk to under 500 KB before upload.';

  let preparedPhoto = null; // the shrunken file, ready to upload
  let uploadedPath = null;  // set after upload, so a retry never uploads twice
  let previewUrl = null;

  function clearPhoto() {
    preparedPhoto = null;
    uploadedPath = null;
    photoInput.value = '';
    photoPreview.hidden = true;
    photoPreview.removeAttribute('src');
    photoRemove.hidden = true;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
    photoStatus.textContent = PHOTO_HINT;
  }

  photoInput.addEventListener('change', async () => {
    clearMessage();
    const file = photoInput.files[0];
    if (!file) {
      clearPhoto();
      return;
    }
    photoStatus.textContent = 'Preparing photo…';
    try {
      const prepared = await compressImage(file);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      preparedPhoto = prepared;
      uploadedPath = null;
      previewUrl = URL.createObjectURL(prepared);
      photoPreview.src = previewUrl;
      photoPreview.hidden = false;
      photoRemove.hidden = false;
      photoStatus.textContent = `Photo ready (${Math.round(prepared.size / 1024)} KB).`;
    } catch (error) {
      clearPhoto();
      showError(error.message);
    }
  });

  photoRemove.addEventListener('click', clearPhoto);

  let loaded = 0;
  let reportingId = null;

  async function loadGym() {
    const gym = await api.gym(gymId);
    document.title = `${gym.name} · Pump Check`;
    nameEl.textContent = gym.name;
    addressEl.textContent = gym.address || 'Address not listed';

    if (gym.average_rating === null || gym.average_rating === undefined) {
      ratingEl.replaceChildren(el('span', { class: 'muted', text: 'No reviews yet' }));
    } else {
      const rounded = Math.round(gym.average_rating);
      ratingEl.replaceChildren(
        el('span', {
          class: 'stars', role: 'img',
          'aria-label': `Rated ${gym.average_rating.toFixed(1)} out of 5`,
          text: `${stars(rounded)} ${gym.average_rating.toFixed(1)}`
        }),
        el('span', {
          class: 'muted small',
          text: ` (${gym.review_count} review${gym.review_count === 1 ? '' : 's'})`
        }));
    }

    equipmentList.replaceChildren(...(gym.equipment.length
      ? gym.equipment.map(item => el('li', {},
          el('strong', { text: item.name }), ' ',
          el('span', { class: availabilityClass(item.availability), text: item.availability }), ' ',
          item.condition && el('span', {
            class: item.condition === 'broken' ? 'badge badge-bad' : 'badge',
            text: `${item.condition} condition`
          })))
      : [el('li', { class: 'muted', text: 'No equipment reported yet.' })]));

    busyList.replaceChildren(...(gym.busy_hours.length
      ? gym.busy_hours.map(hour => el('li', {},
          el('strong', { text: hour.label }),
          el('span', {
            class: 'muted small',
            text: ` · ${hour.mentions} mention${hour.mentions === 1 ? '' : 's'}`
          })))
      : [el('li', { class: 'muted', text: 'No busy-hour reports yet.' })]));
  }

  function reviewCard(review) {
    return el('article', { class: 'card' },
      el('div', { class: 'row', style: 'justify-content: space-between; align-items: center;' },
        el('span', {
          class: 'stars', role: 'img',
          'aria-label': `${review.rating} out of 5 stars`,
          text: stars(review.rating)
        }),
        el('span', { class: 'muted small', text: `${review.username} · ${formatDate(review.created_at)}` })),
      review.review_text && el('p', {
        text: review.review_text, style: 'white-space: pre-wrap; margin-top: 0.5rem;'
      }),
      review.busy_hour_info && el('p', { class: 'muted small', text: `Busy: ${review.busy_hour_info}` }),
      review.photo_url && el('img', {
        class: 'review-photo', src: review.photo_url,
        alt: 'Photo shared with this review', loading: 'lazy'
      }),
      el('div', { style: 'margin-top: 0.5rem;' },
        el('button', {
          class: 'btn btn-secondary btn-small', type: 'button', text: 'Report',
          onclick: () => openReport(review.id)
        })));
  }

  async function loadReviews(reset) {
    if (reset) {
      loaded = 0;
      reviewsEl.replaceChildren();
    }
    const data = await api.reviews(gymId, { limit: PAGE_SIZE, offset: loaded });
    data.reviews.forEach(review => reviewsEl.append(reviewCard(review)));
    loaded += data.reviews.length;
    loadMore.hidden = loaded >= data.total;
    reviewCount.textContent = data.total
      ? `${data.total} review${data.total === 1 ? '' : 's'}`
      : 'No reviews yet. Be the first to write one.';
  }

  function openReport(reviewId) {
    reportingId = reviewId;
    reportReason.value = '';
    reportError.hidden = true;
    dialog.showModal();
    reportReason.focus();
  }

  textInput.addEventListener('input', () => {
    charCount.textContent = `${textInput.value.length} / 1000`;
  });

  loadMore.addEventListener('click', () => {
    withBusy(loadMore, async () => {
      try { await loadReviews(false); } catch (error) { showError(error.message); }
    });
  });

    form.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();

    const chosen = form.querySelector('input[name="rating"]:checked');
    if (!chosen) {
      showError('Choose a rating from 1 to 5.');
      return;
    }
    const text = textInput.value.trim();
    if (text.length > 1000) {
      showError('Reviews can be at most 1,000 characters.');
      return;
    }

    const button = form.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        // Upload the photo first, then attach its path to the review
        if (preparedPhoto && !uploadedPath) {
          const uploaded = await api.uploadPhoto(preparedPhoto);
          uploadedPath = uploaded.photo_path;
        }
        await api.addReview(gymId, {
          rating: Number(chosen.value),
          review_text: text || null,
          busy_hour_info: busyInput.value.trim() || null,
          photo_path: uploadedPath
        });
        form.reset();
        clearPhoto();
        charCount.textContent = '0 / 1000';
        await Promise.all([loadGym(), loadReviews(true)]);
        showSuccess('Review posted. Thanks for sharing.');
      } catch (error) {
        // The form is not cleared, so nothing the user typed is lost
        showError(error.message);
      }
    });
  });

  document.getElementById('report-cancel').addEventListener('click', () => dialog.close());

  reportForm.addEventListener('submit', async event => {
    event.preventDefault();
    const reason = reportReason.value.trim();
    if (!reason) {
      reportError.textContent = 'Tell us why you are reporting this review.';
      reportError.hidden = false;
      return;
    }
    const button = reportForm.querySelector('button[type="submit"]');
    await withBusy(button, async () => {
      try {
        await api.reportReview(reportingId, reason);
        dialog.close();
        showSuccess('Thanks. The review was reported.');
      } catch (error) {
        reportError.textContent = error.message;
        reportError.hidden = false;
      }
    });
  });

  (async () => {
    try {
      await Promise.all([loadGym(), loadReviews(true)]);
    } catch (error) {
      showError(error.status === 404 ? 'Gym not found.' : error.message);
    }
  })();
}