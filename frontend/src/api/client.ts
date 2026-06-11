import axios from 'axios';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

export const api = axios.create({ baseURL: BASE });

// Anonymous named-identity: send the name the user typed as X-User on every
// request. The backend scopes the dataset library / sessions to this name, so
// the same name on any device sees the same history. No password/token —
// access control is the deployment's network perimeter.
api.interceptors.request.use(config => {
  const identity = localStorage.getItem('identity');
  if (identity) config.headers['X-User'] = identity;
  return config;
});
