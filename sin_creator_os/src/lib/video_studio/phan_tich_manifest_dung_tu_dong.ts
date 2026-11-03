import type { TimelineDocument } from "@/lib/api/media-studio-api";

export interface TakeOption {
  take_id: string;
  start_ms: number;
  end_ms: number;
  title: string;
  reason: string;
}

export interface ClipDungTuDong {
  clip_id: string;
  title: string;
  source_start_ms: number;
  source_end_ms: number;
  selected_take_id: string;
  selection_reason: string;
  needs_review: boolean;
  take_options: TakeOption[];
  visual_actions: VisualAction[];
  output_asset_id?: string;
  timeline?: TimelineDocument;
}

export interface VisualAction {
  asset_id: string;
  mode: "CUTAWAY" | "OVERLAY" | "SPEAKER_PIP";
  start_ms: number;
  end_ms: number;
  reason: string;
}

export interface ManifestDungTuDong {
  replay_source_asset_id: string | null;
  clips: ClipDungTuDong[];
  waveform_peaks: number[];
  pause_candidates: [number, number][];
  flow_generated_visuals: { target_clip_id?: string; job_id?: string; state: string }[];
}

const laSoKhongAm = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0;
const laSoDuong = (value: unknown): value is number => Number.isInteger(value) && Number(value) > 0;

function docTimeline(value: unknown): TimelineDocument {
  if (!value || typeof value !== "object") throw new Error();
  const raw = value as Record<string, unknown>;
  if (
    !Array.isArray(raw.clips) ||
    raw.clips.length > 1000 ||
    !Array.isArray(raw.overlays) ||
    raw.overlays.length > 100 ||
    !Array.isArray(raw.captions) ||
    raw.captions.length > 3000
  )
    throw new Error();
  const clips = raw.clips.map((value) => {
    if (!value || typeof value !== "object") throw new Error();
    const clip = value as Record<string, unknown>;
    if (
      typeof clip.clip_id !== "string" ||
      clip.clip_id.length > 64 ||
      typeof clip.asset_id !== "string" ||
      clip.asset_id.length > 255 ||
      (clip.media_type !== "video" && clip.media_type !== "image") ||
      !laSoKhongAm(clip.start_ms) ||
      !laSoDuong(clip.duration_ms) ||
      (clip.effect !== undefined && clip.effect !== "none" && clip.effect !== "punch_in") ||
      (clip.audio_asset_id !== undefined && typeof clip.audio_asset_id !== "string") ||
      (clip.audio_trim_in_ms !== undefined && !laSoKhongAm(clip.audio_trim_in_ms)) ||
      (clip.trim_in_ms !== undefined && !laSoKhongAm(clip.trim_in_ms)) ||
      (clip.trim_out_ms !== undefined && !laSoKhongAm(clip.trim_out_ms)) ||
      (clip.fit !== undefined && clip.fit !== "cover" && clip.fit !== "contain")
    )
      throw new Error();
    return clip as unknown as TimelineDocument["clips"][number];
  });
  const overlays = raw.overlays.map((value) => {
    if (!value || typeof value !== "object") throw new Error();
    const overlay = value as Record<string, unknown>;
    if (
      typeof overlay.asset_id !== "string" ||
      !laSoKhongAm(overlay.start_ms) ||
      !laSoDuong(overlay.duration_ms) ||
      !laSoKhongAm(overlay.x) ||
      overlay.x > 1079 ||
      !laSoKhongAm(overlay.y) ||
      overlay.y > 1919 ||
      !laSoDuong(overlay.width) ||
      overlay.width > 1080 ||
      overlay.x + overlay.width > 1080 ||
      !laSoDuong(overlay.height) ||
      overlay.height > 1920 ||
      overlay.y + overlay.height > 1920
    )
      throw new Error();
    return overlay as unknown as NonNullable<TimelineDocument["overlays"]>[number];
  });
  const captions = raw.captions.map((value) => {
    if (!value || typeof value !== "object") throw new Error();
    const caption = value as Record<string, unknown>;
    if (
      typeof caption.text !== "string" ||
      !laSoKhongAm(caption.start_ms) ||
      !laSoDuong(caption.duration_ms) ||
      (caption.position_y_px !== undefined &&
        (!laSoKhongAm(caption.position_y_px) || caption.position_y_px < 150 || caption.position_y_px > 1600)) ||
      (caption.visual_type !== undefined && caption.visual_type !== "callout")
    )
      throw new Error();
    return caption as unknown as NonNullable<TimelineDocument["captions"]>[number];
  });
  if (
    raw.caption_style !== undefined &&
    raw.caption_style !== "legacy" &&
    raw.caption_style !== "vietsub_v1" &&
    raw.caption_style !== "vietsub_karaoke_v2"
  )
    throw new Error();
  if (
    raw.transition_seconds !== undefined &&
    (typeof raw.transition_seconds !== "number" || raw.transition_seconds < 0 || raw.transition_seconds > 0.5)
  )
    throw new Error();
  return { ...raw, clips, overlays, captions } as TimelineDocument;
}

export function docManifestDungTuDong(value: string): ManifestDungTuDong {
  try {
    const raw = JSON.parse(value) as Record<string, unknown>;
    if (
      !Array.isArray(raw.clips) ||
      raw.clips.length > 100 ||
      !Array.isArray(raw.waveform_peaks) ||
      !Array.isArray(raw.pause_candidates) ||
      (raw.flow_generated_visuals !== undefined && !Array.isArray(raw.flow_generated_visuals)) ||
      (raw.flow_generated_visuals?.length ?? 0) > 2000
    ) {
      throw new Error();
    }
    const flow_generated_visuals = (raw.flow_generated_visuals ?? []).map((item) => {
      if (!item || typeof item !== "object") throw new Error();
      const visual = item as Record<string, unknown>;
      if (
        typeof visual.state !== "string" ||
        visual.state.length === 0 ||
        visual.state.length > 64 ||
        (visual.target_clip_id !== undefined &&
          (typeof visual.target_clip_id !== "string" || visual.target_clip_id.length === 0 || visual.target_clip_id.length > 64)) ||
        (visual.job_id !== undefined &&
          (typeof visual.job_id !== "string" || visual.job_id.length === 0 || visual.job_id.length > 64))
      )
        throw new Error();
      return {
        ...(visual.target_clip_id ? { target_clip_id: visual.target_clip_id } : {}),
        ...(visual.job_id ? { job_id: visual.job_id } : {}),
        state: visual.state,
      };
    });
    const clips = raw.clips.map((item): ClipDungTuDong => {
      if (!item || typeof item !== "object") throw new Error();
      const clip = item as Record<string, unknown>;
      if (
        typeof clip.clip_id !== "string" ||
        typeof clip.title !== "string" ||
        !laSoKhongAm(clip.source_start_ms) ||
        !laSoKhongAm(clip.source_end_ms) ||
        clip.source_end_ms <= clip.source_start_ms ||
        typeof clip.selected_take_id !== "string" ||
        typeof clip.selection_reason !== "string" ||
        typeof clip.needs_review !== "boolean" ||
        !Array.isArray(clip.take_options) ||
        (clip.visual_actions !== undefined && !Array.isArray(clip.visual_actions))
      )
        throw new Error();
      const take_options = clip.take_options.map((rawTake): TakeOption => {
        if (!rawTake || typeof rawTake !== "object") throw new Error();
        const take = rawTake as Record<string, unknown>;
        if (
          typeof take.take_id !== "string" ||
          !laSoKhongAm(take.start_ms) ||
          !laSoKhongAm(take.end_ms) ||
          take.end_ms <= take.start_ms ||
          typeof take.title !== "string" ||
          typeof take.reason !== "string"
        )
          throw new Error();
        return {
          take_id: take.take_id,
          start_ms: take.start_ms,
          end_ms: take.end_ms,
          title: take.title,
          reason: take.reason,
        };
      });
      if (!take_options.some((take) => take.take_id === clip.selected_take_id)) throw new Error();
      const visual_actions = (clip.visual_actions ?? []).map((rawAction): VisualAction => {
        if (!rawAction || typeof rawAction !== "object") throw new Error();
        const action = rawAction as Record<string, unknown>;
        if (
          typeof action.asset_id !== "string" ||
          (action.mode !== "CUTAWAY" && action.mode !== "OVERLAY" && action.mode !== "SPEAKER_PIP") ||
          !laSoKhongAm(action.start_ms) ||
          !laSoKhongAm(action.end_ms) ||
          action.end_ms <= action.start_ms ||
          typeof action.reason !== "string"
        )
          throw new Error();
        return {
          asset_id: action.asset_id,
          mode: action.mode,
          start_ms: action.start_ms,
          end_ms: action.end_ms,
          reason: action.reason,
        };
      });
      if (clip.output_asset_id !== undefined && typeof clip.output_asset_id !== "string") throw new Error();
      return {
        clip_id: clip.clip_id,
        title: clip.title,
        source_start_ms: clip.source_start_ms,
        source_end_ms: clip.source_end_ms,
        selected_take_id: clip.selected_take_id,
        selection_reason: clip.selection_reason,
        needs_review: clip.needs_review,
        take_options,
        visual_actions,
        ...(clip.output_asset_id ? { output_asset_id: clip.output_asset_id } : {}),
        ...(clip.timeline !== undefined ? { timeline: docTimeline(clip.timeline) } : {}),
      };
    });
    const waveform_peaks = raw.waveform_peaks.map((peak) => {
      if (!Number.isInteger(peak) || Number(peak) < 0 || Number(peak) > 100) throw new Error();
      return Number(peak);
    });
    const pause_candidates = raw.pause_candidates.map((pause): [number, number] => {
      if (
        !Array.isArray(pause) ||
        pause.length !== 2 ||
        !laSoKhongAm(pause[0]) ||
        !laSoKhongAm(pause[1]) ||
        pause[1] <= pause[0]
      )
        throw new Error();
      return [Number(pause[0]), Number(pause[1])];
    });
    const replay_source_asset_id = typeof raw.source_asset_id === "string" && raw.source_asset_id.length <= 36
      && Array.isArray(raw.words) && raw.words.length > 0 && raw.plan && typeof raw.plan === "object"
      && Array.isArray(raw.visual_briefs) && Array.isArray(raw.visual_generation)
      ? raw.source_asset_id : null;
    return { clips, waveform_peaks, pause_candidates, flow_generated_visuals, replay_source_asset_id };
  } catch {
    throw new Error("AUTO_EDIT_MANIFEST_INVALID");
  }
}
