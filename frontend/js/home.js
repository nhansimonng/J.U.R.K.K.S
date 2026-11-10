import { api, requireLogin, renderNavbar } from './common.js?v=merged-5';
if (requireLogin()) {
  renderNavbar('index.html');
  api.me().then(user => {
    document.getElementById('welcome').textContent = 'Welcome, ' + user.username;
  }).catch(() => {});
}
