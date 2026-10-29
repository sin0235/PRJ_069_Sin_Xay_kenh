export interface ParsedFlowApiError {
  errorCode: string;
  message: string;
}

export class FlowSessionApiError extends Error {
  readonly errorCode: string;
  readonly status: number;

  constructor(errorCode: string, message: string, status: number) {
    super(message);
    this.name = "FlowSessionApiError";
    this.errorCode = errorCode;
    this.status = status;
  }
}

export function parseFlowApiError(value: unknown, fallback: string): ParsedFlowApiError {
  const body = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const detail = body.detail && typeof body.detail === "object"
    ? body.detail as Record<string, unknown>
    : {};
  const errorCode = [body.error_code, detail.error_code].find(
    (candidate): candidate is string => typeof candidate === "string" && candidate.trim().length > 0,
  ) || "HTTP_ERROR";
  const message = [detail.message, body.message_safe, detail.message_safe, body.message].find(
    (candidate): candidate is string => typeof candidate === "string" && candidate.trim().length > 0,
  ) || fallback;
  return { errorCode, message };
}
