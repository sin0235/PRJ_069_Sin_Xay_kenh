import type { TimelineClip, TimelineDocument } from "@/lib/api/media-studio-api";

export interface AssetStudioRef {
  id: string;
}

export interface VideoStudioAssetRef extends AssetStudioRef {
  mime_detected: string;
  url?: string | null;
  duration_ms?: number;
}

export const taoClipTimelineTuAsset = (asset: VideoStudioAssetRef, clipId: string): TimelineClip | null => {
  if (!asset.mime_detected.startsWith("video/") || !asset.url) return null;
  const durationMs = asset.duration_ms && asset.duration_ms > 0 ? asset.duration_ms : 3000;
  return {
    clip_id: clipId,
    asset_id: asset.id,
    media_type: "video",
    start_ms: 0,
    duration_ms: durationMs,
    trim_in_ms: 0,
    trim_out_ms: durationMs,
    fit: "cover",
  };
};

export const themClipLienKetVaoTimeline = (clips: TimelineClip[], linkedClip: TimelineClip) => {
  const existing = clips.find((clip) => clip.asset_id === linkedClip.asset_id);
  return existing
    ? { clips, selectedClipId: existing.clip_id }
    : { clips: [...clips, linkedClip], selectedClipId: linkedClip.clip_id };
};

export const themTimelineLienKetVaoTimeline = (current: TimelineDocument, linked: TimelineDocument, prefix: string) => {
  const hasCurrentContent =
    current.clips.length > 0 ||
    (current.overlays?.length ?? 0) > 0 ||
    (current.captions?.length ?? 0) > 0 ||
    Boolean(current.voice_track ?? current.music_track);
  const offsetMs = current.clips.reduce((total, clip) => total + clip.duration_ms, 0);
  const linkedClips = linked.clips.map((clip) => ({
    ...clip,
    clip_id: `${prefix}_${clip.clip_id}`.slice(0, 64),
    start_ms: offsetMs + clip.start_ms,
  }));
  const linkedCaptions = (linked.captions ?? []).map((caption, index) => ({
    ...caption,
    caption_id: `${prefix}_caption_${index}`.slice(0, 64),
    start_ms: offsetMs + caption.start_ms,
  }));
  const linkedOverlays = (linked.overlays ?? []).map((overlay) => ({
    ...overlay,
    start_ms: offsetMs + overlay.start_ms,
  }));
  const base = hasCurrentContent ? current : linked;
  return {
    timeline: {
      ...base,
      clips: [...current.clips, ...linkedClips],
      captions: [...(current.captions ?? []), ...linkedCaptions],
      overlays: [...(current.overlays ?? []), ...linkedOverlays],
      caption_style: hasCurrentContent ? (current.caption_style ?? linked.caption_style) : linked.caption_style,
      transition_seconds: hasCurrentContent
        ? (current.transition_seconds ?? linked.transition_seconds)
        : linked.transition_seconds,
    },
    selectedClipId: linkedClips[0]?.clip_id ?? null,
  };
};

export const taoDuongDanVideoStudio = (projectId: string, assetId: string, manifestId?: string): string =>
  `/video-studio/${encodeURIComponent(projectId)}?asset_id=${encodeURIComponent(assetId)}` +
  (manifestId ? `&manifest_id=${encodeURIComponent(manifestId)}` : "");

export const taoKhoaLienKetVideoStudio = (
  projectId: string,
  assetId: string | null,
  manifestId?: string | null,
): string => JSON.stringify([projectId, assetId, manifestId ?? null]);

export const nenNapVideoTuLienKet = (loadedLinkKey: string | null, linkKey: string): boolean =>
  loadedLinkKey !== linkKey;

export const chonAssetIdTuLienKetStudio = (search: string, assets: AssetStudioRef[]): string | null => {
  const assetId = new URLSearchParams(search).get("asset_id");
  return assetId && assets.some((asset) => asset.id === assetId) ? assetId : null;
};

export const chonVideoDeMoStudio = (search: string, assets: VideoStudioAssetRef[]): VideoStudioAssetRef | null => {
  const requestedId = new URLSearchParams(search).get("asset_id");
  const usableVideo = (asset: VideoStudioAssetRef) => asset.mime_detected.startsWith("video/") && Boolean(asset.url);
  return assets.find((asset) => asset.id === requestedId && usableVideo(asset)) ?? assets.find(usableVideo) ?? null;
};
