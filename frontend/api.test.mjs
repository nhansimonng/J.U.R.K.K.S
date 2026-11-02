import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('./api.js', import.meta.url), 'utf8');
const { createApi } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
function fixture() {
  const values = new Map();
  const storage = { getItem: k => values.get(k), setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
  const state = { status: 200, body: {}, calls: [], unauthorized: 0 };
  const api = createApi({ storage, onUnauthorized: () => state.unauthorized++, fetchImpl: async (url, options) => {
    state.calls.push({ url, ...options });
    return { status: state.status, ok: state.status < 400, json: async () => state.body };
  }});
  return { api, state, values };
}
test('login stores token and protected calls attach it', async () => {
  const { api, state } = fixture();
  state.body = { access_token: 'token' };
  await api.login({ email: 'a@example.com', password: 'example' });
  await api.me();
  assert.equal(state.calls[1].headers.Authorization, 'Bearer token');
});
test('401 clears token and calls redirect hook', async () => {
  const { api, state, values } = fixture();
  values.set('pump_check_access_token', 'old');
  state.status = 401; state.body = { error: 'Authentication required' };
  await assert.rejects(api.me(), /Authentication required/);
  assert.equal(values.size, 0); assert.equal(state.unauthorized, 1);
});
test('logout clears browser token even on provider failure', async () => {
  const { api, state, values } = fixture();
  values.set('pump_check_access_token', 'old');
  state.status = 503; state.body = { error: 'Unavailable' };
  await assert.rejects(api.logout(), /Unavailable/);
  assert.equal(values.size, 0);
});
test('204 is handled without JSON parsing', async () => {
  const { api, state } = fixture(); state.status = 204;
  assert.equal(await api.deletePlan('id'), null);
  assert.equal(state.calls[0].method, 'DELETE');
});
test('query parameters are URL-encoded and empty filters omitted', async () => {
  const { api, state } = fixture();
  await api.gyms({ query: 'A&B', lat: 0, equipment: '' });
  assert.equal(state.calls[0].url, 'http://127.0.0.1:8000/api/gyms?query=A%26B&lat=0');
});
test('confirmation response does not retain a previous account token', async () => {
  const { api, state, values } = fixture();
  values.set('pump_check_access_token', 'old'); state.body = { confirmation_required: true };
  await api.register({}); assert.equal(values.size, 0);
});
test('photo upload leaves multipart boundary to the browser', async () => {
  const { api, state } = fixture();
  await api.uploadPhoto(new Blob(['image'], { type: 'image/png' }));
  assert.ok(state.calls[0].body instanceof FormData);
  assert.equal(state.calls[0].headers['Content-Type'], undefined);
});
