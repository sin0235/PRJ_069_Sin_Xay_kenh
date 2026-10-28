type AuthCookieEnvironment = {
  NODE_ENV?: string;
  AUTH_COOKIE_SECURE?: string;
};

export function shouldUseSecureAuthCookie(env: AuthCookieEnvironment = process.env): boolean {
  const configured = env.AUTH_COOKIE_SECURE?.trim().toLowerCase();
  if (configured === "false") return false;
  return configured === "true" || env.NODE_ENV === "production";
}
