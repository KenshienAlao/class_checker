import { API_ROUTES } from "@/config/api-routes";
import { ROUTES } from "@/config/routes.config";
import axios, { type AxiosError, type AxiosRequestConfig } from "axios";

export class SessionExpiredError extends Error {
  constructor() {
    super("Session expired");
    this.name = "SessionExpiredError";
  }
}

type RetriableConfig = AxiosRequestConfig & { _retry?: boolean };

type ErrorDetail = string | { msg?: string }[];

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

const NO_REFRESH = new Set<string>([
  API_ROUTES.AUTH.SIGNUP,
  API_ROUTES.AUTH.SIGNIN,
  API_ROUTES.AUTH.REFRESH,
  API_ROUTES.AUTH.LOGOUT,
]);

function readCsrfCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const match = document.cookie.match(/(?:^|;\s*)csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function extractErrorMessage(error: AxiosError<{ detail?: ErrorDetail }>): string {
  const detail = error.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail[0].msg;
  }

  return error.message;
}

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  withCredentials: true,
  headers: {
    Accept: "application/json",
  },
});

api.interceptors.request.use((config) => {
  const method = (config.method ?? "get").toLowerCase();

  // The backend enforces CSRF on any unsafe request that carries the session
  // cookie, regardless of endpoint. Echo the readable `csrf` cookie whenever
  // it exists; before login there is no cookie, so nothing is sent.
  if (UNSAFE_METHODS.has(method)) {
    const token = readCsrfCookie();
    if (token) {
      config.headers.set("X-CSRF-Token", token);
    }
  }

  return config;
});

// Single-flight: concurrent 401s await the same refresh instead of issuing
// several rotations, and every waiter retries its own request at most once.
let refreshPromise: Promise<void> | null = null;

function refreshSession(): Promise<void> {
  refreshPromise ??= api
    .post(API_ROUTES.AUTH.REFRESH)
    .then(() => undefined)
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

let isRedirecting = false;

function clearSession(): void {
  if (typeof window === "undefined" || isRedirecting) {
    return;
  }

  const { pathname } = window.location;
  if (pathname === ROUTES.AUTH.SIGNIN || pathname === ROUTES.AUTH.SIGNUP) {
    // Already on an auth page: reloading it would loop. State is discarded by
    // the query layer instead.
    return;
  }

  isRedirecting = true;
  window.location.replace(`${ROUTES.AUTH.SIGNIN}?clear_session=true`);
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError<{ detail?: ErrorDetail }>) => {
    const config = error.config as RetriableConfig | undefined;
    const status = error.response?.status;

    if (
      status === 401 &&
      config &&
      !config._retry &&
      !NO_REFRESH.has(config.url ?? "")
    ) {
      config._retry = true;

      try {
        await refreshSession();
        return api(config);
      } catch {
        clearSession();
        throw new SessionExpiredError();
      }
    }

    throw new Error(extractErrorMessage(error));
  },
);

export async function request<TData = void>(
  config: AxiosRequestConfig,
): Promise<TData> {
  const res = await api.request<TData>(config);
  return res.data;
}

export const http = {
  get: <TData = void>(url: string, config?: AxiosRequestConfig) =>
    request<TData>({ ...config, method: "get", url }),
  post: <TData = void>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TData>({ ...config, method: "post", url, data }),
  put: <TData = void>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TData>({ ...config, method: "put", url, data }),
  patch: <TData = void>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig,
  ) => request<TData>({ ...config, method: "patch", url, data }),
  delete: <TData = void>(url: string, config?: AxiosRequestConfig) =>
    request<TData>({ ...config, method: "delete", url }),
};

export default api;
