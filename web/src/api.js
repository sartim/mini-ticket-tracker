const API_ROOT = "/api";
let accessToken = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
}

async function refreshAccessToken() {
  const response = await fetch(`${API_ROOT}/auth/token/refresh`, {
    method: "POST",
    credentials: "same-origin",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.access) {
    clearAccessToken();
    window.dispatchEvent(new Event("ticket-desk:session-expired"));
    return null;
  }

  setAccessToken(data.access);
  return data.access;
}

export async function api(path, options = {}) {
  const isTokenRequest = path.startsWith("/auth/token");
  const send = (access) => fetch(`${API_ROOT}${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(access && !isTokenRequest ? { Authorization: `Bearer ${access}` } : {}),
      ...options.headers,
    },
  });

  let response = await send(accessToken);
  if (response.status === 401 && !isTokenRequest) {
    const newAccess = await refreshAccessToken();
    if (newAccess) response = await send(newAccess);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.error || "Request failed. Please try again.";
    throw new Error(typeof detail === "string" ? detail : Object.values(detail).flat().join(" "));
  }
  return data;
}
