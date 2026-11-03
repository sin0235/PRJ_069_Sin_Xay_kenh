import type { KaraokeCaptionSettings, TimelineCaption, TimelineDocument } from "@/lib/api/media-studio-api";

export const KARAOKE_CAPTION_DEFAULTS: KaraokeCaptionSettings = {
  preset: "bat_nhip",
  font_size: 56,
  layout: "center",
  accent_color: "champagne",
  outline: true,
  shadow: true,
  word_pop: true,
};

export const KARAOKE_CAPTION_COLORS: Record<KaraokeCaptionSettings["accent_color"], string> = {
  champagne: "#D9B26A",
  baha_blue: "#2457D6",
  coral: "#F07168",
};

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
    .map((cue) => ({ ...cue, font_size: cue.font_size ?? coChu, safe_zone: cue.safe_zone ?? true }));
}

export function taoThongSoPhuDeXemTruoc(
  cue: TimelineCaption | undefined,
  style: TimelineDocument["caption_style"],
  canvasHeight: number,
  defaultFontSize: number,
  karaokeSettings: KaraokeCaptionSettings = KARAOKE_CAPTION_DEFAULTS,
) {
  if (style === "vietsub_karaoke_v2") {
    return {
      fontSizePx: (karaokeSettings.font_size * canvasHeight) / 1920,
      topPercent: 73,
      visualType: cue?.visual_type,
      textAlign: karaokeSettings.layout === "left" ? "left" as const : "center" as const,
    };
  }
  if (style !== "vietsub_v1") {
    return { fontSizePx: defaultFontSize, topPercent: null, visualType: cue?.visual_type, textAlign: "center" as const };
  }
  return {
    fontSizePx: ((cue?.font_size ?? defaultFontSize) * canvasHeight) / 1920,
    topPercent: ((cue?.position_y_px ?? 1920 * 0.73) / 1920) * 100,
    visualType: cue?.visual_type,
    textAlign: "center" as const,
  };
}

export function taoNoiDungPhuDeXemTruoc(
  cue: TimelineCaption | undefined,
  currentTimeMs: number,
  settings: KaraokeCaptionSettings,
) {
  const words = cue?.words?.length
    ? cue.words
    : (cue?.text ?? "").trim().split(/\s+/).filter(Boolean).map((text) => ({ text, start_ms: -1, end_ms: -1 }));
  const breakAfter = settings.layout === "two_line" ? timViTriNgatDong(words.map((word) => word.text)) : null;
  return {
    words: words.map((word) => ({
      text: word.text,
      active: currentTimeMs >= word.start_ms && currentTimeMs < word.end_ms,
    })),
    breakAfter,
  };
}

function timViTriNgatDong(words: string[]): number | null {
  if (words.length < 2) return null;
  const total = words.join(" ").length;
  let running = 0;
  let best = 1;
  let distance = Number.POSITIVE_INFINITY;
  for (let index = 1; index < words.length; index += 1) {
    running += words[index - 1].length + 1;
    const nextDistance = Math.abs(running - (total - running));
    if (nextDistance < distance) {
      best = index;
      distance = nextDistance;
    }
  }
  return best;
}
