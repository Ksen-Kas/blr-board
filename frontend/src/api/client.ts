import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
  headers: import.meta.env.VITE_INTERNAL_API_KEY
    ? { "X-App-Key": import.meta.env.VITE_INTERNAL_API_KEY }
    : undefined,
});

export default api;
