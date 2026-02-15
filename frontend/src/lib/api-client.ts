import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
});

let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 1. If it's a 401 and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      
      // SAFE ZONE: Don't redirect/refresh if we are already on the login page 
      // or if the request itself was the login/refresh attempt.
      const isLoginRequest = originalRequest.url?.includes('/auth/login');
      const isRefreshRequest = originalRequest.url?.includes('/auth/refresh');
      const isInitialCheck = originalRequest.url?.includes('/auth/me');

      if (isLoginRequest || isRefreshRequest) {
        return Promise.reject(error);
      }

      // If it's the initial check (/auth/me) and it fails, just stop.
      // Don't redirect to login with "session=expired" yet.
      if (isInitialCheck) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => api(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const csrfToken = document.cookie
          .split('; ')
          .find((row) => row.startsWith('ta_csrf='))
          ?.split('=')[1];

        await axios.post('/api/v1/auth/refresh', {}, {
          headers: { 'X-CSRF-Token': csrfToken || '' },
          withCredentials: true,
        });

        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        
        // Only redirect if we aren't already there!
        if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
          window.location.href = '/login?session=expired';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);