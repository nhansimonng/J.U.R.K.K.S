import { api, requireLogin, renderNavbar } from './common.js?v=account-1';
if (requireLogin()) {
  renderNavbar('index.html');
  api.me().then(user => {
    document.getElementById('welcome').textContent = 'Welcome, ' + user.username;
  }).catch(() => {});
}
