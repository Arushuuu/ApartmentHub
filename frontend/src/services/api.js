// In development, Vite forwards /api requests to FastAPI. This avoids CORS
// issues while keeping VITE_API_URL available for a deployed backend.
const API_URL = import.meta.env.VITE_API_URL ?? '/api';

export async function request(path, options = {}) {
  const token = localStorage.getItem('apartmenthub_token');
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? 'Something went wrong. Please try again.');
  }
  return response.status === 204 ? null : response.json();
}

export { API_URL };
