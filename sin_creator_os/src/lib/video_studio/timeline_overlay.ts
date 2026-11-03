import type { TimelineOverlay } from "@/lib/api/media-studio-api";

type ThayDoiHinhHocOverlay = Partial<
  Pick<TimelineOverlay, "x" | "y" | "width" | "height" | "start_ms" | "duration_ms">
>;

export function capNhatHinhHocOverlay(
  overlay: TimelineOverlay,
  changes: ThayDoiHinhHocOverlay,
  timelineDurationMs = Number.POSITIVE_INFINITY,
): TimelineOverlay {
  const width = Math.min(1080, Math.max(1, Math.round(changes.width ?? overlay.width)));
  const height = Math.min(1920, Math.max(1, Math.round(changes.height ?? overlay.height)));
  const x = Math.min(1080 - width, Math.max(0, Math.round(changes.x ?? overlay.x)));
  const y = Math.min(1920 - height, Math.max(0, Math.round(changes.y ?? overlay.y)));
  const maxTimelineMs = Number.isFinite(timelineDurationMs) ? Math.max(1, Math.round(timelineDurationMs)) : Infinity;
  const start_ms = Math.min(maxTimelineMs - 1, Math.max(0, Math.round(changes.start_ms ?? overlay.start_ms)));
  return {
    ...overlay,
    ...changes,
    x,
    y,
    width,
    height,
    start_ms,
    duration_ms: Math.min(
      maxTimelineMs - start_ms,
      Math.max(1, Math.round(changes.duration_ms ?? overlay.duration_ms)),
    ),
  };
}
