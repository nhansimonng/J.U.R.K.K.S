import { api, isLoggedIn, showError, showSuccess, clearMessage, withBusy } from './common.js?v=account-1';

const HOME_PAGE = 'index.html';

// Already logged in? Skip this page.
if (isLoggedIn()) window.location.href = HOME_PAGE;

const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const showLoginButton = document.getElementById('show-login');
const showRegisterButton = document.getElementById('show-register');

function showForm(which) {
  const loginActive = which === 'login';
  loginForm.hidden = !loginActive;
  registerForm.hidden = loginActive;
  showLoginButton.setAttribute('aria-pressed', String(loginActive));
  showRegisterButton.setAttribute('aria-pressed', String(!loginActive));
  showLoginButton.className = loginActive ? 'btn' : 'btn btn-secondary';
  showRegisterButton.className = loginActive ? 'btn btn-secondary' : 'btn';
  clearMessage();
}

showLoginButton.addEventListener('click', () => showForm('login'));
showRegisterButton.addEventListener('click', () => showForm('register'));

loginForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearMessage();

  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  if (!email || !password) {
    showError('Enter your email and password.');
    return;
  }

  const button = loginForm.querySelector('button[type="submit"]');
  await withBusy(button, async () => {
    try {
      await api.login({ email, password });
      window.location.href = HOME_PAGE;
    } catch (error) {
      showError(error.message);
    }
  });
});

registerForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearMessage();

  const email = document.getElementById('register-email').value.trim();
  const username = document.getElementById('register-username').value.trim();
  const password = document.getElementById('register-password').value;

  if (!email || !username || !password) {
    showError('Fill in every field.');
    return;
  }
  if (password.length < 8) {
    showError('Password must be at least 8 characters.');
    return;
  }

  const button = registerForm.querySelector('button[type="submit"]');
  await withBusy(button, async () => {
    try {
      const result = await api.register({ email, username, password });
      if (result.access_token) {
        window.location.href = HOME_PAGE;
      } else {
        // Email confirmation is turned on in Supabase
        showForm('login');
        showSuccess(result.message || 'Check your email to confirm your account, then log in.');
      }
    } catch (error) {
      showError(error.message);
    }
  });
});