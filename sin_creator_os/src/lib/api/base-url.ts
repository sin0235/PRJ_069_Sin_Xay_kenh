const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, "");

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") return trimTrailingSlashes(window.location.origin);
  return trimTrailingSlashes(process.env.API_INTERNAL_URL || "");
}
