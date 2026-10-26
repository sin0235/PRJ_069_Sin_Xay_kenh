import type { TimelineCaption } from "@/lib/api/media-studio-api";

export function taoPhuDeDeLuu(
  cues: TimelineCaption[],
  noiDungCauDau: string,
  coChu: number,
  thoiLuongMs: number,
): TimelineCaption[] {
  const captions = cues.length
    ? cues.map((cue, index) => (index === 0 ? { ...cue, text: noiDungCauDau } : cue))
    : noiDungCauDau.trim() && thoiLuongMs > 0
      ? [{ caption_id: "cap_main", text: noiDungCauDau, start_ms: 0, duration_ms: thoiLuongMs }]
      : [];

  return captions
    .filter((cue) => cue.text.trim())
    .map((cue) => ({ ...cue, font_size: coChu, safe_zone: cue.safe_zone ?? true }));
}
