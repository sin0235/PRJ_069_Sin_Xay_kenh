import type { KaraokeCaptionSettings, TimelineCaption, TimelineDocument } from "@/lib/api/media-studio-api";

export const KARAOKE_CAPTION_DEFAULTS: KaraokeCaptionSettings = {
  preset: "da_sac_phan_tang",
  font_size: 56,
  layout: "center",
  accent_color: "champagne",
  outline: true,
  shadow: true,
  word_pop: true,
};

export const KARAOKE_CAPTION_COLORS: Record<KaraokeCaptionSettings["accent_color"], string> = {
  champagne: "#FFD54A",
  baha_blue: "#38BDF8",
  coral: "#FF4D4F",
};

export const KARAOKE_PRESETS_EXTENDED = [
  { value: "da_sac_phan_tang", label: "Đa sắc 3 tầng", accent_color: "champagne", word_pop: true, layout: "center" },
  { value: "hop_mau_dong_chinh", label: "Hộp màu nhấn", accent_color: "coral", word_pop: true, layout: "center" },
  { value: "bento_ba_tang", label: "Bento đa cỡ", accent_color: "champagne", word_pop: true, layout: "center" },
  { value: "inline_pop_trai", label: "Căn trái nội dòng", accent_color: "champagne", word_pop: true, layout: "left" },
  { value: "bat_nhip", label: "Nảy từ (cổ điển)", accent_color: "champagne", word_pop: true, layout: "center" },
  { value: "to_sac", label: "Tô sắc", accent_color: "baha_blue", word_pop: false, layout: "center" },
  { value: "hai_dong", label: "Hai dòng", accent_color: "coral", word_pop: false, layout: "two_line" },
] as const;

export type SemanticWordRole = "METRIC_GOLD" | "PAIN_CORAL" | "GROWTH_EMERALD" | "BRAND_CYAN" | "NORMAL_WHITE";

const RE_METRIC = /\b(?:\d+[\d.,]*\b|k\b|triệu\b|tỷ\b|%|\busd\b|\bđ\b|\bđồng\b|\bgiây\b|\bphút\b|\bgiờ\b|\bngày\b|\btuần\b|\btháng\b|\bnăm\b|\blần\b|x\d+\b)/i;
const PAIN_WORDS = new Set(["đừng", "cấm", "sai", "lầm", "thất", "bại", "mất", "lỗ", "nguy", "hiểm", "cảnh", "báo", "chết", "người", "hỏng", "tụt", "ế", "không", "tốn"]);
const GROWTH_WORDS = new Set(["bí", "quyết", "thành", "công", "tăng", "nhanh", "ngay", "miễn", "phí", "tự", "động", "đột", "phá", "hiệu", "quả", "chuẩn", "đỉnh", "chuyên", "nghiệp", "viral", "follow", "doanh", "thu", "giữ", "chân"]);
const BRAND_WORDS = new Set(["tiktok", "sin", "baha", "xây", "kênh", "quảng", "cáo", "bán", "hàng"]);

export function phanLoaiTuKhoaFront(text: string): SemanticWordRole {
  const clean = text.toLowerCase().replace(/[^a-z0-9àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]/g, "").trim();
  if (!clean) return "NORMAL_WHITE";
  if (RE_METRIC.test(clean) || /\d/.test(text)) return "METRIC_GOLD";
  const tokens = clean.split(/\s+/);
  for (const t of tokens) {
    if (PAIN_WORDS.has(t)) return "PAIN_CORAL";
  }
  for (const t of tokens) {
    if (GROWTH_WORDS.has(t)) return "GROWTH_EMERALD";
  }
  for (const t of tokens) {
    if (BRAND_WORDS.has(t)) return "BRAND_CYAN";
  }
  return "NORMAL_WHITE";
}

export const SEMANTIC_COLORS: Record<SemanticWordRole, string> = {
  METRIC_GOLD: "#FFD54A",
  PAIN_CORAL: "#FF4D4F",
  GROWTH_EMERALD: "#34D399",
  BRAND_CYAN: "#38BDF8",
  NORMAL_WHITE: "#FFFFFF",
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
  sourceCanvasHeight = 1920,
) {
  if (style === "vietsub_karaoke_v2") {
    return {
      fontSizePx: (karaokeSettings.font_size * canvasHeight) / sourceCanvasHeight,
      topPercent: 73,
      visualType: cue?.visual_type,
      textAlign: (karaokeSettings.layout === "left" || karaokeSettings.preset === "inline_pop_trai") ? ("left" as const) : ("center" as const),
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
  const rawWords = cue?.words?.length
    ? cue.words
    : (cue?.text ?? "").trim().split(/\s+/).filter(Boolean).map((text) => ({ text, start_ms: -1, end_ms: -1 }));

  const n = rawWords.length;
  const isKinetic = ["da_sac_phan_tang", "hop_mau_dong_chinh", "bento_ba_tang", "inline_pop_trai"].includes(settings.preset);

  const breakAfterIndices: number[] = [];
  const words = rawWords.map((word, index) => {
    const role = phanLoaiTuKhoaFront(word.text);
    const active = currentTimeMs >= word.start_ms && currentTimeMs < word.end_ms;
    let sizeFactor = 1.0;
    let isUppercase = false;
    let isPill = false;

    if (isKinetic) {
      if (settings.preset === "da_sac_phan_tang") {
        if (n <= 3) {
          sizeFactor = 1.15;
          if (role !== "NORMAL_WHITE") isUppercase = true;
        } else if (n <= 6) {
          const mid = n === 4 ? 2 : (n === 5 ? 2 : 3);
          if (index < mid) {
            sizeFactor = 0.72;
          } else {
            sizeFactor = 1.22;
            isUppercase = true;
          }
          if (index === mid - 1) breakAfterIndices.push(index);
        } else {
          const l1 = Math.max(2, Math.floor(n / 3));
          const l2 = Math.max(l1 + 2, Math.floor((2 * n) / 3));
          if (index < l1) {
            sizeFactor = 0.65;
          } else if (index < l2) {
            sizeFactor = 1.25;
            isUppercase = true;
          } else {
            sizeFactor = 0.85;
          }
          if (index === l1 - 1) breakAfterIndices.push(index);
          if (index === l2 - 1) breakAfterIndices.push(index);
        }
      } else if (settings.preset === "hop_mau_dong_chinh") {
        const mid = Math.floor(n / 2);
        if (index < mid) {
          sizeFactor = 0.75;
        } else {
          sizeFactor = 1.12;
          isPill = role === "PAIN_CORAL" || role === "METRIC_GOLD" || role === "GROWTH_EMERALD";
          isUppercase = true;
        }
        if (index === mid - 1 && mid > 0) breakAfterIndices.push(index);
      } else if (settings.preset === "bento_ba_tang") {
        if (n <= 4) {
          sizeFactor = index < 2 ? 0.65 : 1.22;
          if (index === 1) breakAfterIndices.push(index);
        } else {
          const l1 = 2;
          const l2 = n <= 6 ? 4 : 5;
          if (index < l1) {
            sizeFactor = 0.58;
            isUppercase = true;
          } else if (index < l2) {
            sizeFactor = 1.25;
            isUppercase = true;
          } else {
            sizeFactor = 0.75;
          }
          if (index === l1 - 1) breakAfterIndices.push(index);
          if (index === l2 - 1) breakAfterIndices.push(index);
        }
      } else if (settings.preset === "inline_pop_trai") {
        const mid = Math.max(1, Math.floor(n / 2));
        sizeFactor = role !== "NORMAL_WHITE" ? 1.22 : 0.75;
        if (role !== "NORMAL_WHITE") isUppercase = true;
        if (index === mid - 1 && n > 3) breakAfterIndices.push(index);
      }
    } else if (settings.layout === "two_line") {
      const splitAt = timViTriNgatDong(rawWords.map((w) => w.text));
      if (splitAt !== null && index === splitAt - 1) {
        breakAfterIndices.push(index);
      }
    }

    const baseColor = KARAOKE_CAPTION_COLORS[settings.accent_color] || "#FFD54A";
    const activeColor = isKinetic
      ? (role !== "NORMAL_WHITE" ? SEMANTIC_COLORS[role] : baseColor)
      : baseColor;

    return {
      text: isUppercase ? word.text.toUpperCase() : word.text,
      active,
      color: active ? activeColor : "#FFFFFF",
      sizeFactor,
      isPill,
      isUppercase,
      role,
    };
  });

  return {
    words,
    breakAfter: breakAfterIndices[0] ?? null,
    breakAfterIndices,
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
