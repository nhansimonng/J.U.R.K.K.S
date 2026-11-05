// Pump Check API layer — follows the API Contract (Frontend <-> Backend) v0.1.
// Mock data is only used when the page is opened with ?mock (UI work without a backend).

export const USE_MOCK = new URLSearchParams(location.search).has("mock");
// Served by the backend (http://127.0.0.1:8000/)? Use the same origin. Opened from Live Server or a file? Call the backend directly.
const BASE_URL = ["5500", "5501"].includes(location.port) || location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const TOKEN_KEY = "pump_check_access_token"; // same key as the multi-page site, so both share one login
const USER_KEY = "pc_user";

export function getToken() { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } }
export function setToken(t) { try { sessionStorage.setItem(TOKEN_KEY, t); } catch { /* storage blocked */ } }
export function getUser() { try { return JSON.parse(sessionStorage.getItem(USER_KEY)); } catch { return null; } }
export function setUser(u) { try { sessionStorage.setItem(USER_KEY, JSON.stringify(u)); } catch { /* storage blocked */ } }
export function clearSession() { try { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY); } catch { /* storage blocked */ } }

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

// ---- Real request helper (contract sections 1-3) ----
async function request(method, path, body, isForm = false) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(BASE_URL + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  } catch {
    throw new ApiError(503, "Temporarily unavailable. Please try again.");
  }
  if (res.status === 204) return null;
  let data = {};
  try { data = await res.json(); } catch { /* no body */ }
  if (res.ok) return data;
  if (res.status === 401 && token) { clearSession(); location.hash = "#/login"; }
  const defaults = { 403: "You are not allowed to do that.", 404: "Not found", 429: "Too many requests. Please wait a moment.", 500: "Something went wrong on our side." };
  if ((res.status === 502 || res.status === 503) && !data.error) throw new ApiError(res.status, "Temporarily unavailable. Please try again.");
  throw new ApiError(res.status, data.error || defaults[res.status] || "Request failed");
}

const qs = (obj) => new URLSearchParams(Object.entries(obj).filter(([, v]) => v !== "" && v != null)).toString();

// ---- Mock data ----
const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const uid = () => "m-" + Math.random().toString(36).slice(2, 9);
const wait = (v) => new Promise((r) => setTimeout(() => r(v === null ? null : structuredClone(v)), 120));
const fail = (status, msg) => Promise.reject(new ApiError(status, msg));

const mock = {
  me: { id: "u-1", email: "kristik@test.com", username: "Kristik Lal" },
  gyms: [
    { id: "g-1", name: "Test Gym Berryessa", address: "400 Test Way, San Jose, CA", latitude: 37.37, longitude: -121.86, average_rating: 4.3, review_count: 3 },
    { id: "g-2", name: "Test Gym Downtown San Jose", address: "100 Test St, San Jose, CA", latitude: 37.335, longitude: -121.89, average_rating: null, review_count: 0 },
    { id: "g-3", name: "Test Gym Santana Row", address: "300 Test Blvd, San Jose, CA", latitude: 37.32, longitude: -121.947, average_rating: null, review_count: 0 },
    { id: "g-4", name: "Test Gym Willow Glen", address: "200 Test Ave, San Jose, CA", latitude: 37.304, longitude: -121.9, average_rating: null, review_count: 0 }
  ],
  equipment: {
    "g-1": [
      { id: "e-1", name: "squat rack", availability: "available", condition: "good" },
      { id: "e-2", name: "leg press", availability: "unconfirmed", condition: "worn" },
      { id: "e-3", name: "barbell", availability: "available", condition: "good" },
      { id: "e-4", name: "bench", availability: "available", condition: "fair" }
    ]
  },
  reviews: [
    { id: "r-1", user_id: "u-2", username: "jorge", gym_id: "g-1", rating: 5, review_text: "Plenty of squat racks, packed after 5pm.", busy_hour_info: "5pm-8pm", photo_url: null, created_at: "2026-10-20T18:30:00Z" },
    { id: "r-2", user_id: "u-3", username: "umar", gym_id: "g-1", rating: 4, review_text: "Clean and quiet in the mornings.", busy_hour_info: null, photo_url: null, created_at: "2026-10-22T14:00:00Z" },
    { id: "r-3", user_id: "u-4", username: "simon", gym_id: "g-1", rating: 4, review_text: "Leg press is a bit worn.", busy_hour_info: "6pm-8pm", photo_url: null, created_at: "2026-10-25T01:10:00Z" }
  ],
  workoutLogs: [{ id: "w-1", exercise_name: "Bench Press", sets: 3, reps: 10, weight: 135, weight_unit: "lb", log_date: "2026-10-20" }],
  plans: [
    { id: "p-1", user_id: "u-1", name: "Push Day", fitness_goal: "muscle_gain", is_public: false,
      exercises: [
        { id: "x-1", name: "Bench Press", muscle_group: "chest", sets: 4, reps: 8, required_equipment: ["barbell", "bench"] },
        { id: "x-2", name: "Leg Press", muscle_group: "legs", sets: 3, reps: 12, required_equipment: ["leg press"] }
      ] },
    { id: "p-2", user_id: "u-2", author_username: "jorge", name: "Leg Day Basics", fitness_goal: "strength", is_public: true,
      exercises: [{ id: "x-3", name: "Back Squat", muscle_group: "legs", sets: 5, reps: 5, required_equipment: ["squat rack", "barbell"] }] },
    { id: "p-3", user_id: "u-3", author_username: "umar", name: "Full Body Starter", fitness_goal: "general_fitness", is_public: true,
      exercises: [{ id: "x-4", name: "Goblet Squat", muscle_group: "legs", sets: 3, reps: 10, required_equipment: ["dumbbell"] }] }
  ],
  saved: new Set(),
  foods: [
    { food_id: "170567", name: "Chicken breast, cooked", reference_portion: 100, reference_unit: "g", reference_calories: 165 },
    { food_id: "168875", name: "White rice, cooked", reference_portion: 100, reference_unit: "g", reference_calories: 130 }
  ],
  calorieLogs: []
};

const KM_PER_DEG = 111;
const distanceKm = (g, lat, lng) => Math.round(Math.hypot((g.latitude - lat) * KM_PER_DEG, (g.longitude - lng) * KM_PER_DEG * Math.cos((lat * Math.PI) / 180)) * 10) / 10;
const planView = (p) => ({ ...p, author_username: p.author_username || (p.user_id === "u-1" ? "you" : "") });

// ---- Public API: one function per endpoint in the contract ----
export const api = {
  // 4. Authentication
  register(email, password, username) {
    if (!USE_MOCK) return request("POST", "/api/auth/register", { email, password, username });
    if (password.length < 8) return fail(400, "Password too weak");
    return wait({ user: { ...mock.me, email, username }, access_token: "mock-jwt", expires_at: now() });
  },
  login(email, password) {
    if (!USE_MOCK) return request("POST", "/api/auth/login", { email, password });
    if (!email || !password) return fail(401, "Invalid email or password");
    return wait({ user: { ...mock.me, email }, access_token: "mock-jwt", expires_at: now() });
  },
  logout() { return USE_MOCK ? wait(null) : request("POST", "/api/auth/logout"); },
  me() { return USE_MOCK ? wait({ ...mock.me, created_at: "2026-10-20T18:30:00Z" }) : request("GET", "/api/users/me"); },

  // 5. Gyms
  searchGyms({ query = "", equipment = "", lat, lng, radius_km }) {
    const params = { query, equipment, lat, lng, radius_km: lat != null ? radius_km : undefined };
    if (!query && !equipment && lat == null) return fail(400, "Enter a gym name or location");
    if (!USE_MOCK) return request("GET", "/api/gyms?" + qs(params));
    const text = query.toLowerCase();
    const need = equipment.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
    let gyms = mock.gyms.filter((g) => !text || (g.name + " " + g.address).toLowerCase().includes(text));
    gyms = gyms.filter((g) => need.every((n) => (mock.equipment[g.id] || []).some((e) => e.name === n && e.availability === "available")));
    if (lat != null) gyms = gyms.map((g) => ({ ...g, distance_km: distanceKm(g, lat, lng) })).filter((g) => g.distance_km <= (radius_km || 10));
    return wait({ gyms });
  },
  getGym(id) {
    if (!USE_MOCK) return request("GET", `/api/gyms/${id}`);
    const g = mock.gyms.find((x) => x.id === id);
    if (!g) return fail(404, "Gym not found");
    const reviews = mock.reviews.filter((r) => r.gym_id === id);
    const avg = reviews.length ? Math.round((reviews.reduce((s, r) => s + r.rating, 0) / reviews.length) * 10) / 10 : null;
    const busy = {};
    reviews.forEach((r) => { if (r.busy_hour_info) busy[r.busy_hour_info] = (busy[r.busy_hour_info] || 0) + 1; });
    return wait({ ...g, average_rating: avg, review_count: reviews.length, equipment: mock.equipment[id] || [], busy_hours: Object.entries(busy).map(([label, mentions]) => ({ label, mentions })) });
  },
  addEquipment(id, item) {
    if (!USE_MOCK) return request("POST", `/api/gyms/${id}/equipment`, item);
    const list = (mock.equipment[id] = mock.equipment[id] || []);
    const existing = list.find((e) => e.name === item.name);
    if (existing) { Object.assign(existing, item); return wait(existing); }
    const created = { id: uid(), ...item };
    list.push(created);
    return wait(created);
  },
  compatibility(gymId, planId) {
    if (!USE_MOCK) return request("GET", `/api/gyms/${gymId}/compatibility?plan_id=${encodeURIComponent(planId)}`);
    const plan = mock.plans.find((p) => p.id === planId);
    if (!mock.gyms.find((g) => g.id === gymId) || !plan) return fail(404, "Gym or plan not found");
    const eq = mock.equipment[gymId] || [];
    const results = plan.exercises.map((x) => {
      const states = x.required_equipment.map((n) => eq.find((e) => e.name === n));
      const missing = x.required_equipment.filter((_, i) => !states[i] || states[i].availability === "unavailable");
      const unconfirmed = states.some((s) => s && s.availability === "unconfirmed");
      const status = missing.length ? "unavailable" : unconfirmed ? "unconfirmed" : "compatible";
      return { exercise_id: x.id, exercise_name: x.name, status, missing_equipment: missing,
        alternatives: status === "unavailable" ? [{ name: "Goblet Squat", muscle_group: "legs", required_equipment: ["dumbbell"] }] : [] };
    });
    return wait({ gym_id: gymId, plan_id: planId, compatible: results.every((r) => r.status === "compatible"), results });
  },

  // 6. Reviews and photos
  listReviews(id, limit = 20, offset = 0) {
    if (!USE_MOCK) return request("GET", `/api/gyms/${id}/reviews?limit=${limit}&offset=${offset}`);
    const all = mock.reviews.filter((r) => r.gym_id === id);
    return wait({ reviews: all.slice(offset, offset + limit), total: all.length });
  },
  uploadPhoto(file) {
    if (!USE_MOCK) { const f = new FormData(); f.append("file", file); return request("POST", "/api/reviews/photo", f, true); }
    return wait({ photo_path: "reviews/" + uid() + ".jpg" });
  },
  submitReview(id, body) {
    if (!USE_MOCK) return request("POST", `/api/gyms/${id}/reviews`, body);
    if (!(body.rating >= 1 && body.rating <= 5)) return fail(400, "Rating must be between 1 and 5");
    if ((body.review_text || "").length > 1000) return fail(400, "Review text cannot exceed 1000 characters");
    const r = { id: uid(), user_id: "u-1", username: mock.me.username, gym_id: id, photo_url: null, created_at: now(), ...body };
    mock.reviews.unshift(r);
    return wait(r);
  },
  reportReview(reviewId, reason) {
    if (!USE_MOCK) return request("POST", `/api/reviews/${reviewId}/reports`, { reason });
    if (!reason.trim()) return fail(400, "A reason is required");
    return wait({ id: uid(), review_id: reviewId, status: "pending" });
  },

  // 7. Workout logs
  logWorkout(body) {
    if (!USE_MOCK) return request("POST", "/api/workout-logs", body);
    if (!Number.isInteger(body.sets) || !Number.isInteger(body.reps) || body.sets < 1 || body.reps < 1) return fail(400, "Sets and reps must be positive whole numbers");
    if (body.weight < 0) return fail(400, "Weight cannot be negative");
    const log = { id: uid(), ...body };
    mock.workoutLogs.unshift(log);
    return wait(log);
  },
  workoutHistory(from, to) {
    if (!USE_MOCK) { const q = qs({ from, to }); return request("GET", "/api/users/me/workout-logs" + (q ? "?" + q : "")); }
    return wait({ logs: mock.workoutLogs });
  },
  deleteWorkout(id) {
    if (!USE_MOCK) return request("DELETE", `/api/workout-logs/${id}`);
    mock.workoutLogs = mock.workoutLogs.filter((l) => l.id !== id);
    return wait(null);
  },

  // 8. Workout plans and community routines
  createPlan(body) {
    if (!USE_MOCK) return request("POST", "/api/workout-plans", body);
    if (!body.name) return fail(400, "Plan name is required");
    if (body.exercises.some((x) => !x.name || !(x.sets > 0) || !(x.reps > 0))) return fail(400, "Each exercise needs a name, sets, and reps");
    const plan = { id: uid(), user_id: "u-1", ...body, exercises: body.exercises.map((x) => ({ id: uid(), ...x })) };
    mock.plans.unshift(plan);
    return wait(plan);
  },
  myPlans() {
    if (!USE_MOCK) return request("GET", "/api/users/me/workout-plans");
    return wait({ plans: mock.plans.filter((p) => p.user_id === "u-1") });
  },
  communityPlans({ goal, muscle_group, limit = 20, offset = 0 } = {}) {
    if (!USE_MOCK) return request("GET", "/api/workout-plans?" + qs({ goal, muscle_group, limit, offset }));
    const list = mock.plans.filter((p) => p.is_public && (!goal || p.fitness_goal === goal) && (!muscle_group || p.exercises.some((x) => x.muscle_group === muscle_group)));
    return wait({ plans: list.map(planView) });
  },
  updatePlan(id, body) {
    if (!USE_MOCK) return request("PUT", `/api/workout-plans/${id}`, body);
    const i = mock.plans.findIndex((p) => p.id === id);
    if (i < 0) return fail(404, "Not found");
    if (!body.name) return fail(400, "Plan name is required");
    mock.plans[i] = { ...mock.plans[i], ...body, exercises: body.exercises.map((x) => ({ id: x.id || uid(), ...x })) };
    return wait(mock.plans[i]);
  },
  deletePlan(id) {
    if (!USE_MOCK) return request("DELETE", `/api/workout-plans/${id}`);
    mock.plans = mock.plans.filter((p) => p.id !== id);
    mock.saved.delete(id);
    return wait(null);
  },
  savePlan(id) { if (!USE_MOCK) return request("POST", `/api/workout-plans/${id}/save`); mock.saved.add(id); return wait({ plan_id: id }); },
  unsavePlan(id) { if (!USE_MOCK) return request("DELETE", `/api/workout-plans/${id}/save`); mock.saved.delete(id); return wait(null); },
  savedPlans() {
    if (!USE_MOCK) return request("GET", "/api/users/me/saved-plans");
    return wait({ plans: mock.plans.filter((p) => mock.saved.has(p.id)).map(planView) });
  },

  // 9. Recommendations
  recommendations({ goal, muscle_group }) {
    if (!goal && !muscle_group) return fail(400, "Provide a goal or a muscle group");
    if (!USE_MOCK) return request("GET", "/api/recommendations?" + qs({ goal, muscle_group }));
    const list = mock.plans.filter((p) => p.is_public && (!goal || p.fitness_goal === goal) && (!muscle_group || p.exercises.some((x) => x.muscle_group === muscle_group)));
    return wait({ plans: list.map(planView) });
  },

  // 11. Calorie tracker
  searchFoods(query) {
    if (!USE_MOCK) return request("GET", "/api/foods/search?query=" + encodeURIComponent(query));
    return wait({ foods: mock.foods.filter((f) => f.name.toLowerCase().includes(query.toLowerCase())), cached_only: false });
  },
  logFood(body) {
    if (!USE_MOCK) return request("POST", "/api/calorie-logs", body);
    if (!(body.portion > 0)) return fail(400, "Portion must be greater than 0");
    if (!["g", "oz", "cup", "serving"].includes(body.portion_unit)) return fail(400, "Unsupported portion unit");
    const f = mock.foods.find((x) => x.food_id === body.food_id) || mock.foods[0];
    const calories = (f.reference_calories * body.portion) / f.reference_portion;
    const entry = { id: uid(), food_name: body.food_name, portion: body.portion, portion_unit: body.portion_unit, calories, log_date: body.log_date };
    mock.calorieLogs.push(entry);
    const daily_total = mock.calorieLogs.filter((e) => e.log_date === body.log_date).reduce((s, e) => s + e.calories, 0);
    return wait({ ...entry, daily_total });
  },
  dailyCalories(date) {
    if (!USE_MOCK) return request("GET", "/api/calorie-logs?date=" + date);
    const entries = mock.calorieLogs.filter((e) => e.log_date === date);
    return wait({ date, entries, daily_total: entries.reduce((s, e) => s + e.calories, 0) });
  },
  deleteCalorie(id) {
    if (!USE_MOCK) return request("DELETE", `/api/calorie-logs/${id}`);
    mock.calorieLogs = mock.calorieLogs.filter((e) => e.id !== id);
    return wait(null);
  }
};
