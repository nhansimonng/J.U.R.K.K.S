import { api, requireLogin, renderNavbar, showError, showSuccess, clearMessage, withBusy } from './common.js?v=account-1';
if (requireLogin()) {
  renderNavbar('account.html');
  init();
}
async function init() {
  const profileForm = document.getElementById('profile-form');
  const passwordForm = document.getElementById('password-form');
  const username = document.getElementById('username');
  const save = document.getElementById('save-profile');
  profileForm.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();
    if (!username.value.trim()) return showError('Enter a username.');
    await withBusy(save, async () => {
      try {
        const user = await api.updateProfile({ username: username.value.trim() });
        username.value = user.username;
        renderNavbar('account.html');
        showSuccess('Username updated.');
      } catch (error) { showError(error.message); }
    });
  });
  passwordForm.addEventListener('submit', async event => {
    event.preventDefault();
    clearMessage();
    const current_password = document.getElementById('current-password').value;
    const password = document.getElementById('new-password').value;
    if (password !== document.getElementById('confirm-password').value) return showError('New passwords do not match.');
    if (password === current_password) return showError('Choose a different password.');
    await withBusy(passwordForm.querySelector('button'), async () => {
      try {
        await api.changePassword({ current_password, password });
        passwordForm.reset();
        showSuccess('Password changed. Use your new password the next time you log in.');
      } catch (error) { showError(error.message); }
    });
  });
  try {
    const user = await api.me();
    username.value = user.username;
    document.getElementById('account-email').textContent = 'Email: ' + user.email;
    save.disabled = false;
  } catch (error) { showError(error.message); }
}
