import { useAuthStore } from "@/stores/auth-store";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;

  constructor(message: string, status: number, code = "API_ERROR", details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function getStoredTokens(): { accessToken: string | null; refreshToken: string | null } {
  const state = useAuthStore.getState();
  if (state.accessToken || state.refreshToken) {
    return { accessToken: state.accessToken, refreshToken: state.refreshToken };
  }
  if (typeof window === "undefined") return { accessToken: null, refreshToken: null };
  try {
    const raw = localStorage.getItem("uniforge-auth");
    if (!raw) return { accessToken: null, refreshToken: null };
    const parsed = JSON.parse(raw);
    return {
      accessToken: parsed?.state?.accessToken || null,
      refreshToken: parsed?.state?.refreshToken || null,
    };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

// Single-flight refresh lock prevents parallel 401s from double-rotating the refresh token
let inflightRefresh: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (inflightRefresh) return inflightRefresh;

  inflightRefresh = (async () => {
    const { refreshToken } = getStoredTokens();
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ refresh_token: refreshToken || undefined }),
      });
      if (!res.ok) {
        useAuthStore.getState().clearAuth();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
        return null;
      }
      const data = (await res.json()) as {
        access_token: string;
        refresh_token?: string;
      };
      const currentUser = useAuthStore.getState().user;
      if (currentUser) {
        useAuthStore
          .getState()
          .setAuth(currentUser, data.access_token, data.refresh_token || refreshToken);
      } else {
        useAuthStore.setState({
          accessToken: data.access_token,
          refreshToken: data.refresh_token || refreshToken,
        });
      }
      return data.access_token;
    } catch {
      return null;
    } finally {
      inflightRefresh = null;
    }
  })();

  return inflightRefresh;
}

const AUTH_NO_REFRESH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

async function fetchWithAutoRefresh(
  url: string,
  options: RequestInit,
  explicitToken?: string | null,
  skipRefresh = false
): Promise<Response> {
  const buildHeaders = (tok: string | null) => {
    const hdrs = new Headers(options.headers || {});
    if (!hdrs.has("Content-Type") && !(options.body instanceof FormData)) {
      hdrs.set("Content-Type", "application/json");
    }
    if (tok) {
      hdrs.set("Authorization", `Bearer ${tok}`);
    }
    return hdrs;
  };

  const initialToken =
    explicitToken !== undefined ? explicitToken : getStoredTokens().accessToken;

  let res = await fetch(url, {
    ...options,
    headers: buildHeaders(initialToken),
    credentials: "include",
  });

  if (res.status === 401 && !skipRefresh && explicitToken === undefined) {
    const renewed = await refreshAccessToken();
    if (renewed) {
      res = await fetch(url, {
        ...options,
        headers: buildHeaders(renewed),
        credentials: "include",
      });
    }
  }
  return res;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const { token, ...rest } = options;
  const skipRefresh = AUTH_NO_REFRESH_PATHS.some((p) => path.startsWith(p));
  const res = await fetchWithAutoRefresh(`${API_BASE}${path}`, rest, token, skipRefresh);

  if (!res.ok) {
    let errData: { error?: { message?: string; code?: string; details?: unknown }; detail?: string } = {};
    try {
      errData = await res.json();
    } catch {
      // non-json error body
    }
    throw new ApiError(
      errData.error?.message || errData.detail || `Request failed (${res.status})`,
      res.status,
      errData.error?.code || `HTTP_${res.status}`,
      errData.error?.details
    );
  }

  if (res.status === 204) {
    return {} as T;
  }
  return (await res.json()) as T;
}

export async function apiDownloadBlob(
  path: string,
  filename: string,
  options: RequestInit = {}
): Promise<void> {
  const url = path.startsWith("http")
    ? path
    : path.startsWith("/api/")
      ? `${API_ORIGIN}${path}`
      : `${API_BASE}${path}`;

  const res = await fetchWithAutoRefresh(url, options);
  if (!res.ok) {
    throw new ApiError(`Export failed (${res.status})`, res.status);
  }
  const blob = await res.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}
