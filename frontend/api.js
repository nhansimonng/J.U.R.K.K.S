/** Pump Check API client. Import with <script type="module">; no service keys here. */
export function createApi({ baseUrl = 'http://127.0.0.1:8000', storage = globalThis.sessionStorage,
                            fetchImpl = globalThis.fetch, onUnauthorized = () => {} } = {}) {
  const key = 'pump_check_access_token';
  async function request(path, { method = 'GET', body } = {}) {
    const headers = {};
    const token = storage.getItem(key);
    if (token) headers.Authorization = `Bearer ${token}`;
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
    const response = await fetchImpl(baseUrl.replace(/\/$/, '') + path, {
      method, headers, body: body === undefined ? undefined : isForm ? body : JSON.stringify(body)
    });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) {
      if (response.status === 401) { storage.removeItem(key); onUnauthorized(); }
      const error = new Error(data?.error || 'Request failed');
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function authenticate(path, body) {
    const data = await request(path, { method: 'POST', body });
    storage.removeItem(key);
    if (data.access_token) storage.setItem(key, data.access_token);
    return data;
  }
  function query(values = {}) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    }
    return params.size ? '?' + params.toString() : '';
  }
  const id = encodeURIComponent;
  return {
    request,
    register: body => authenticate('/api/auth/register', body),
    login: body => authenticate('/api/auth/login', body),
    async logout() {
      try { return await request('/api/auth/logout', { method: 'POST' }); }
      finally { storage.removeItem(key); }
    },
    me: () => request('/api/users/me'),
    gyms: filters => request('/api/gyms' + query(filters)),
    gym: gymId => request(`/api/gyms/${id(gymId)}`),
    equipment: gymId => request(`/api/gyms/${id(gymId)}/equipment`),
    updateEquipment: (gymId, body) => request(`/api/gyms/${id(gymId)}/equipment`, { method: 'POST', body }),
    reviews: (gymId, filters) => request(`/api/gyms/${id(gymId)}/reviews` + query(filters)),
    addReview: (gymId, body) => request(`/api/gyms/${id(gymId)}/reviews`, { method: 'POST', body }),
    reportReview: (reviewId, reason) => request(`/api/reviews/${id(reviewId)}/reports`, { method: 'POST', body: { reason } }),
    uploadPhoto: file => { const body = new FormData(); body.append('file', file); return request('/api/reviews/photo', { method: 'POST', body }); },
    workoutLogs: filters => request('/api/users/me/workout-logs' + query(filters)),
    addWorkoutLog: body => request('/api/workout-logs', { method: 'POST', body }),
    deleteWorkoutLog: logId => request(`/api/workout-logs/${id(logId)}`, { method: 'DELETE' }),
    myPlans: () => request('/api/users/me/workout-plans'),
    publicPlans: filters => request('/api/workout-plans' + query(filters)),
    plan: planId => request(`/api/workout-plans/${id(planId)}`),
    createPlan: body => request('/api/workout-plans', { method: 'POST', body }),
    updatePlan: (planId, body) => request(`/api/workout-plans/${id(planId)}`, { method: 'PUT', body }),
    deletePlan: planId => request(`/api/workout-plans/${id(planId)}`, { method: 'DELETE' }),
    savePlan: planId => request(`/api/workout-plans/${id(planId)}/save`, { method: 'POST' }),
    unsavePlan: planId => request(`/api/workout-plans/${id(planId)}/save`, { method: 'DELETE' }),
    savedPlans: () => request('/api/users/me/saved-plans'),
    recommendations: filters => request('/api/recommendations' + query(filters)),
    compatibility: (gymId, planId) => request(`/api/gyms/${id(gymId)}/compatibility` + query({ plan_id: planId })),
    foods: text => request('/api/foods/search' + query({ query: text })),
    calorieLogs: date => request('/api/calorie-logs' + query({ date })),
    addCalorieLog: body => request('/api/calorie-logs', { method: 'POST', body }),
    deleteCalorieLog: entryId => request(`/api/calorie-logs/${id(entryId)}`, { method: 'DELETE' })
  };
}
