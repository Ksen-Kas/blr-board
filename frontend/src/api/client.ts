import axios from "axios";

const encodeBasic = (value: string) => btoa(unescape(encodeURIComponent(value)));

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
});

let onUnauthorized: (() => void) | null = null;

export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler;
};

export const setBasicAuth = (username: string, password: string) => {
  const token = encodeBasic(`${username}:${password}`);
  api.defaults.headers.common.Authorization = `Basic ${token}`;
};

export const clearAuth = () => {
  delete api.defaults.headers.common.Authorization;
};

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearAuth();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

export default api;
