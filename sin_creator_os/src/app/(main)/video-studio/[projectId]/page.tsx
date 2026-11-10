"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize2,
  Download,
  Sparkles,
  Eraser,
  Sliders,
  Type,
  Music,
  Mic,
  Film,
  Layers,
  ShieldAlert,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  FileVideo,
  FileAudio,
  HardDrive,
  Clock,
  ExternalLink,
  Wand2,
  Settings2,
  Trash2,
  ListPlus,
  Image as ImageIcon,
  UploadCloud,
  ChevronUp,
  ChevronDown,
  Copy,
  Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

import {
  mediaStudioApi,
  MediaAssetResponse,
  TimelineClip,
  TimelineAudioTrack,
  TimelineCaption,
  TimelineDocument,
  TimelineOverlay,
  TimelineVersionResponse,
} from "@/lib/api/media-studio-api";
import { BangDieuPhoiDung } from "@/components/video_studio/bang_dieu_phoi_dung";
import {
  KARAOKE_CAPTION_COLORS,
  KARAOKE_CAPTION_DEFAULTS,
  taoNoiDungPhuDeXemTruoc,
  taoPhuDeDeLuu,
  taoThongSoPhuDeXemTruoc,
} from "./phu_de_timeline";
import { docManifestDungTuDong } from "@/lib/video_studio/phan_tich_manifest_dung_tu_dong";
import { randomUuid } from "@/lib/utils";
import {
  chonVideoDeMoStudio,
  nenNapVideoTuLienKet,
  taoClipTimelineTuAsset,
  taoKhoaLienKetVideoStudio,
  themClipLienKetVaoTimeline,
  themTimelineLienKetVaoTimeline,
} from "@/lib/video_studio/lien_ket_studio";
import { capNhatHinhHocOverlay } from "@/lib/video_studio/timeline_overlay";

const KARAOKE_PRESETS = [
  { value: "tu_dong", label: "Tự động", accent_color: "champagne", word_pop: true, layout: "center" },
  { value: "da_sac_phan_tang", label: "Đa sắc phân tầng", accent_color: "champagne", word_pop: true, layout: "center" },
  { value: "hop_mau_dong_chinh", label: "Hộp màu", accent_color: "coral", word_pop: true, layout: "center" },
  { value: "bento_ba_tang", label: "Bento 3 tầng", accent_color: "baha_blue", word_pop: true, layout: "center" },
  { value: "inline_pop_trai", label: "Phóng to nội dòng", accent_color: "champagne", word_pop: true, layout: "left" },
] as const;

export default function VideoStudioPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = (params?.projectId as string) || "";
  const autoEditLinkKey = taoKhoaLienKetVideoStudio(projectId, searchParams.get("asset_id"), searchParams.get("manifest_id"));
  const [projectTitle, setProjectTitle] = React.useState("");
  const [projectLoadStatus, setProjectLoadStatus] = React.useState<"loading" | "ready" | "missing" | "error">("loading");
  const [projectError, setProjectError] = React.useState<string | null>(null);

  const loadProject = React.useCallback(async () => {
    setProjectLoadStatus("loading");
    setProjectError(null);
    try {
      const project = (await mediaStudioApi.listProjects()).find((item) => item.id === projectId);
      if (!project) {
        setProjectLoadStatus("missing");
        return;
      }
      setProjectTitle(project.title);
      setProjectLoadStatus("ready");
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : "Không tải được dự án.");
      setProjectLoadStatus("error");
    }
  }, [projectId]);

  React.useEffect(() => { void loadProject(); }, [loadProject]);

  // State Trình phát Video / Canvas
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(0.0);
  const [totalDuration, setTotalDuration] = React.useState(0.0);
  const [aspectRatio, setAspectRatio] = React.useState<"9:16" | "16:9">("9:16");
  const [showSafeZone, setShowSafeZone] = React.useState(true);
  const videoRef = React.useRef<HTMLVideoElement | null>(null);

  // State Thư Viện Tư Liệu (M-P2)
  const [assets, setAssets] = React.useState<MediaAssetResponse[]>([]);
  const [isLoadingAssets, setIsLoadingAssets] = React.useState(false);
  const [assetFilter, setAssetFilter] = React.useState<"all" | "image" | "video" | "audio">("all");
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [uploadMessage, setUploadMessage] = React.useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState<number | null>(null);

  // State Phân Cảnh & Tư Liệu Đang Chọn
  const [selectedAssetId, setSelectedAssetId] = React.useState<string | null>(null);
  const autoEditAssetLinkKey = React.useRef<string | null>(null);
  const [selectedClipId, setSelectedClipId] = React.useState<string | null>(null);
  const [previewSource, setPreviewSource] = React.useState<{ url: string; type: "image" | "video" } | null>(null);
  const [previewMediaUrl, setPreviewMediaUrl] = React.useState<string | null>(null);
  const [previewMediaType, setPreviewMediaType] = React.useState<"image" | "video">("video");
  const [isLoadingPreview, setIsLoadingPreview] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);

  // State Timeline Đa Track (M-P3 / M-P4)
  const [timelineVersion, setTimelineVersion] = React.useState<number>(0);
  const [timelineClips, setTimelineClips] = React.useState<TimelineClip[]>([]);
  const [timelineOverlays, setTimelineOverlays] = React.useState<TimelineOverlay[]>([]);
  const [selectedOverlayIndex, setSelectedOverlayIndex] = React.useState<number | null>(null);
  const selectedOverlay = selectedOverlayIndex === null ? null : timelineOverlays[selectedOverlayIndex] ?? null;
  const selectedOverlayAsset = selectedOverlay
    ? assets.find((asset) => asset.id === selectedOverlay.asset_id)
    : undefined;
  const overlayPreviewUrl = selectedOverlayAsset?.url ?? null;
  const previewCanvasRef = React.useRef<HTMLDivElement | null>(null);
  const overlayVideoRef = React.useRef<HTMLVideoElement | null>(null);
  const overlayDragRef = React.useRef<{ index: number; clientX: number; clientY: number; x: number; y: number } | null>(null);
  const [timelineLoaded, setTimelineLoaded] = React.useState(false);
  const autoEditTimelineLinkKey = React.useRef<string | null>(null);
  const [timelineVoice, setTimelineVoice] = React.useState<TimelineAudioTrack | null>(null);
  const [timelineMusic, setTimelineMusic] = React.useState<TimelineAudioTrack | null>(null);
  const [timelineCaptions, setTimelineCaptions] = React.useState<TimelineCaption[]>([]);
  const [captionStyle, setCaptionStyle] = React.useState<TimelineDocument["caption_style"]>("legacy");
  const [karaokeSettings, setKaraokeSettings] = React.useState(KARAOKE_CAPTION_DEFAULTS);
  const [transitionSeconds, setTransitionSeconds] = React.useState(0);
  const timelineStateRef = React.useRef({
    clips: timelineClips,
    overlays: timelineOverlays,
    captions: timelineCaptions,
    voice: timelineVoice,
    music: timelineMusic,
    captionStyle,
    karaokeSettings,
    transitionSeconds,
  });
  timelineStateRef.current = {
    clips: timelineClips,
    overlays: timelineOverlays,
    captions: timelineCaptions,
    voice: timelineVoice,
    music: timelineMusic,
    captionStyle,
    karaokeSettings,
    transitionSeconds,
  };
  const [captionText, setCaptionText] = React.useState("");
  const [captionFontSize, setCaptionFontSize] = React.useState(26);
  const [musicAttenuationDb, setMusicAttenuationDb] = React.useState(-18.0);

  const [isSavingTimeline, setIsSavingTimeline] = React.useState(false);
  const [timelineSaveMessage, setTimelineSaveMessage] = React.useState<string | null>(null);
  const [timelineConflict, setTimelineConflict] = React.useState<boolean>(false);

  // State Kết Xuất MP4 (M-P5)
  const [isRenderingTimeline, setIsRenderingTimeline] = React.useState(false);
  const [renderTimelineProgress, setRenderTimelineProgress] = React.useState<string>("");
  const [renderTimelineError, setRenderTimelineError] = React.useState<string | null>(null);
  const [renderedTimelineAsset, setRenderedTimelineAsset] = React.useState<MediaAssetResponse | null>(null);

  // State Flow Pro-Assisted (M-P6)
  const [refImageAssetId, setRefImageAssetId] = React.useState<string | null>(null);
  const [flowPrompt, setFlowPrompt] = React.useState("");
  const [copiedPrompt, setCopiedPrompt] = React.useState(false);

  // State Quick AI
  const [quickPrompt, setQuickPrompt] = React.useState("");
  const [quickGenType, setQuickGenType] = React.useState<"video" | "music">("video");
  const [isGeneratingAi, setIsGeneratingAi] = React.useState(false);
  const [aiGenMessage, setAiGenMessage] = React.useState<string | null>(null);
  const [isAutoProducing, setIsAutoProducing] = React.useState(false);
  const [autoProduceStage, setAutoProduceStage] = React.useState<string | null>(null);

  // State Khử Watermark Veo AI
  const [isCleaningWatermark, setIsCleaningWatermark] = React.useState(false);
  const [cleanWatermarkMessage, setCleanWatermarkMessage] = React.useState<string | null>(null);
  const [autoCleanWatermark, setAutoCleanWatermark] = React.useState(false);
  const [timelineLoadError, setTimelineLoadError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!previewSource) {
      setPreviewMediaUrl(null);
      setIsLoadingPreview(false);
      setPreviewError(null);
      return;
    }

    videoRef.current?.pause();
    setIsPlaying(false);
    setCurrentTime(0);
    setIsLoadingPreview(false);
    setPreviewError(null);
    setPreviewMediaType(previewSource.type);
    setPreviewMediaUrl(previewSource.url);
  }, [previewSource]);

  // Tải danh sách tư liệu từ Backend
  const loadAssets = React.useCallback(async () => {
    setIsLoadingAssets(true);
    try {
      const data = await mediaStudioApi.listAssets({ project_id: projectId });
      setAssets(data);
      if (nenNapVideoTuLienKet(autoEditAssetLinkKey.current, autoEditLinkKey)) {
        const initialVideo = chonVideoDeMoStudio(window.location.search, data);
        if (initialVideo?.url) {
          autoEditAssetLinkKey.current = autoEditLinkKey;
          setSelectedAssetId(initialVideo.id);
          setPreviewSource({ url: initialVideo.url, type: "video" });
        }
      }
    } catch (err: any) {
      console.warn("Không thể tải tư liệu từ API:", err?.message);
    } finally {
      setIsLoadingAssets(false);
    }
  }, [projectId, autoEditLinkKey]);

  // Tải Timeline từ Backend (M-P3)
  const loadTimeline = React.useCallback(async () => {
    setTimelineLoaded(false);
    setTimelineLoadError(null);
    try {
      const res = await mediaStudioApi.getTimeline(projectId);
      const document = res.timeline;
      const clips = document?.clips ?? [];
      const captions = document?.captions ?? [];
      setTimelineVersion(res.version);
      setTimelineClips(clips);
      setTimelineOverlays(document?.overlays ?? []);
      setSelectedOverlayIndex(document?.overlays?.length ? 0 : null);
      setTimelineVoice(document?.voice_track ?? null);
      setTimelineMusic(document?.music_track ?? null);
      setTimelineCaptions(captions);
      setCaptionStyle(document?.caption_style ?? "legacy");
      setKaraokeSettings(document?.karaoke_settings ?? KARAOKE_CAPTION_DEFAULTS);
      setTransitionSeconds(document?.transition_seconds ?? 0);
      setCaptionText(captions[0]?.text ?? "");
      setCaptionFontSize(captions[0]?.font_size ?? 26);
      if (document?.music_track?.ducking_attenuation_db !== undefined) {
        setMusicAttenuationDb(document.music_track.ducking_attenuation_db);
      }
      setTotalDuration(clips.reduce((total, clip) => total + clip.duration_ms, 0) / 1000.0);
      setTimelineLoaded(true);
    } catch (err: any) {
      setTimelineLoadError(err instanceof Error ? err.message : "Không tải được timeline.");
      console.warn("Không thể tải timeline từ API:", err?.message);
    }
  }, [projectId]);

  React.useEffect(() => {
    if (!timelineLoaded || autoEditTimelineLinkKey.current === autoEditLinkKey) return;
    const requestedAssetId = searchParams.get("asset_id");
    if (!requestedAssetId) return;
    const requestedAsset = assets.find((item) => item.id === requestedAssetId);
    if (!requestedAsset) return;
    autoEditTimelineLinkKey.current = autoEditLinkKey;

    const asset = chonVideoDeMoStudio(window.location.search, [requestedAsset]);
    if (!asset) return;
    let active = true;
    const addRenderedClip = (message?: string) => {
      const clipId = `clip_${Date.now().toString(36)}_1`;
      const clip = taoClipTimelineTuAsset(asset, clipId);
      if (!active) return;
      autoEditTimelineLinkKey.current = autoEditLinkKey;
      if (message) setTimelineSaveMessage(message);
      if (!clip) return;
      const nextTimeline = themClipLienKetVaoTimeline(timelineStateRef.current.clips, clip);
      setTimelineClips(nextTimeline.clips);
      setSelectedClipId(nextTimeline.selectedClipId);
    };
    const manifestId = searchParams.get("manifest_id");
    const manifestAsset = assets.find((item) => item.id === manifestId && item.mime_detected === "application/json");
    if (!manifestAsset?.url) {
      addRenderedClip(manifestId ? "Không tìm thấy biên bản dựng chi tiết; đang mở video đã kết xuất." : undefined);
    } else {
      void mediaStudioApi.getAssetText(manifestAsset.url).then((text) => {
        if (!active) return;
        const clipManifest = docManifestDungTuDong(text).clips.find((clip) => clip.output_asset_id === asset.id);
        if (!clipManifest?.timeline) {
          addRenderedClip("Biên bản cũ không có timeline chi tiết; đang mở video đã kết xuất.");
          return;
        }
        const current = timelineStateRef.current;
        const currentTimeline: TimelineDocument = {
          width: 1080,
          height: 1920,
          fps: 30,
          clips: current.clips,
          overlays: current.overlays,
          voice_track: current.voice,
          music_track: current.music,
          captions: current.captions,
          caption_style: current.captionStyle,
          karaoke_settings: current.karaokeSettings,
          transition_seconds: current.transitionSeconds,
        };
        const next = themTimelineLienKetVaoTimeline(currentTimeline, clipManifest.timeline, asset.id.slice(0, 8));
        setTimelineClips(next.timeline.clips);
        setTimelineOverlays(next.timeline.overlays ?? []);
        setSelectedOverlayIndex(next.timeline.overlays?.length ? 0 : null);
        setTimelineCaptions(next.timeline.captions ?? []);
        setTimelineVoice(next.timeline.voice_track ?? null);
        setTimelineMusic(next.timeline.music_track ?? null);
        setCaptionStyle(next.timeline.caption_style ?? "vietsub_v1");
        setKaraokeSettings(next.timeline.karaoke_settings ?? KARAOKE_CAPTION_DEFAULTS);
        setTransitionSeconds(next.timeline.transition_seconds ?? 0.16);
        if (!current.clips.length) {
          setCaptionText(next.timeline.captions?.[0]?.text ?? "");
          setCaptionFontSize(next.timeline.captions?.[0]?.font_size ?? 26);
        }
        setSelectedClipId(next.selectedClipId);
        const firstClip = next.timeline.clips.find((clip) => clip.clip_id === next.selectedClipId);
        const firstClipAsset = assets.find((item) => item.id === firstClip?.asset_id);
        if (firstClipAsset?.url) {
          setPreviewSource({ url: firstClipAsset.url, type: firstClip?.media_type === "image" ? "image" : "video" });
        }
        autoEditTimelineLinkKey.current = autoEditLinkKey;
      }).catch(() => {
        addRenderedClip("Không khôi phục được timeline chi tiết; đang mở video đã kết xuất.");
      });
    }
    return () => { active = false; };
  }, [assets, autoEditLinkKey, searchParams, timelineLoaded]);

  React.useEffect(() => {
    if (projectLoadStatus !== "ready") return;
    void loadAssets();
    void loadTimeline();
  }, [projectLoadStatus, loadAssets, loadTimeline]);

  // Tính lại tổng thời lượng khi timelineClips thay đổi
  React.useEffect(() => {
    const totalDurMs = timelineClips.reduce((acc, clip) => acc + clip.duration_ms, 0);
    setTotalDuration(totalDurMs ? Math.max(1.0, totalDurMs / 1000.0) : 0);
  }, [timelineClips]);

  // Xử lý tải tệp tư liệu lên (M-P2)
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    let expectedCategory: "audio" | "image" | "video" = "video";
    if (file.type.startsWith("image/")) expectedCategory = "image";
    else if (file.type.startsWith("audio/")) expectedCategory = "audio";
    else expectedCategory = "video";

    setIsUploading(true);
    setUploadMessage(`Đang tải lên tệp: ${file.name} (${expectedCategory})...`);
    setUploadProgress(0);

    try {
      const uploaded = await mediaStudioApi.uploadAsset({
        file,
        project_id: projectId,
        expected_category: expectedCategory,
        onProgress: (loadedBytes, totalBytes) => {
          const percent = Math.min(100, Math.floor((loadedBytes / totalBytes) * 100));
          setUploadProgress(percent);
          setUploadMessage(percent === 100
            ? "Đã gửi dữ liệu, đang chờ máy chủ xác nhận..."
            : `Đang tải lên tệp: ${file.name} (${percent}%)...`);
        },
      });

      setUploadMessage(`Đã nạp thành công: ${uploaded.original_filename || uploaded.id}`);
      await loadAssets();

      // Tự động chọn preview
      setSelectedAssetId(uploaded.id);
      if (uploaded.url && expectedCategory !== "audio") {
        setPreviewSource({ url: uploaded.url, type: expectedCategory === "image" ? "image" : "video" });
      }
    } catch (err: any) {
      setUploadMessage(`Lỗi tải lên: ${err?.message || "Không xác định"}`);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Thêm asset vào Timeline (M-P4)
  const handleAddAssetToTimeline = (asset: MediaAssetResponse) => {
    const isImage = asset.mime_detected?.startsWith("image/");
    const isVideo = asset.mime_detected?.startsWith("video/");
    const isAudio = asset.mime_detected?.startsWith("audio/");

    if (isAudio) {
      // Gán vào voice track hoặc music track
      if (!timelineVoice) {
        setTimelineVoice({ asset_id: asset.id, start_ms: 0, duration_ms: asset.duration_ms || 3000, gain_db: 0.0 });
        setUploadMessage(`Đã gán âm thanh '${asset.original_filename || asset.id}' vào Voice Track.`);
      } else {
        setTimelineMusic({
          asset_id: asset.id,
          start_ms: 0,
          duration_ms: asset.duration_ms || 3000,
          gain_db: 0.0,
          ducking_attenuation_db: musicAttenuationDb,
        });
        setUploadMessage(`Đã gán âm thanh '${asset.original_filename || asset.id}' vào Music Track.`);
      }
      return;
    }

    const newClipId = `clip_${Date.now().toString(36)}_${timelineClips.length + 1}`;
    const newDurationMs = isImage ? 3000 : (asset.duration_ms || 3000);

    const newClip: TimelineClip = {
      clip_id: newClipId,
      asset_id: asset.id,
      media_type: isImage ? "image" : "video",
      start_ms: 0,
      duration_ms: newDurationMs,
      trim_in_ms: 0,
      trim_out_ms: isVideo ? newDurationMs : 0,
      fit: "cover",
    };

    setTimelineClips([...timelineClips, newClip]);
    setSelectedClipId(newClipId);
    setSelectedAssetId(asset.id);
    if (asset.url) {
      setPreviewSource({ url: asset.url, type: isImage ? "image" : "video" });
    }
  };

  // Xóa clip khỏi timeline
  const handleRemoveClip = (clipId: string) => {
    setTimelineClips(timelineClips.filter((c) => c.clip_id !== clipId));
    if (selectedClipId === clipId) setSelectedClipId(null);
  };

  // Đổi thứ tự clip (Lên / Xuống)
  const handleMoveClip = (index: number, direction: "up" | "down") => {
    if (direction === "up" && index > 0) {
      const newClips = [...timelineClips];
      const temp = newClips[index - 1];
      newClips[index - 1] = newClips[index];
      newClips[index] = temp;
      setTimelineClips(newClips);
    } else if (direction === "down" && index < timelineClips.length - 1) {
      const newClips = [...timelineClips];
      const temp = newClips[index + 1];
      newClips[index + 1] = newClips[index];
      newClips[index] = temp;
      setTimelineClips(newClips);
    }
  };

  // Cập nhật thông số clip được chọn
  const handleUpdateSelectedClip = (updates: Partial<TimelineClip>) => {
    if (!selectedClipId) return;
    setTimelineClips(
      timelineClips.map((c) => (c.clip_id === selectedClipId ? { ...c, ...updates } : c))
    );
  };

  const handleUpdateSelectedOverlay = (updates: Partial<TimelineOverlay>) => {
    if (selectedOverlayIndex === null) return;
    setTimelineOverlays((current) => current.map((overlay, index) => index === selectedOverlayIndex
      ? capNhatHinhHocOverlay(overlay, updates, Math.round(totalDuration * 1000))
      : overlay));
  };

  const handleOverlayPointerDown = (index: number, event: React.PointerEvent<HTMLDivElement>) => {
    const overlay = timelineOverlays[index];
    if (!overlay) return;
    setSelectedOverlayIndex(index);
    overlayDragRef.current = {
      index,
      clientX: event.clientX,
      clientY: event.clientY,
      x: overlay.x,
      y: overlay.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleOverlayPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = overlayDragRef.current;
    const rect = previewCanvasRef.current?.getBoundingClientRect();
    const overlay = drag && timelineOverlays[drag.index];
    if (!drag || !rect?.width || !rect.height || !overlay) return;
    const x = drag.x + (event.clientX - drag.clientX) * 1080 / rect.width;
    const y = drag.y + (event.clientY - drag.clientY) * 1920 / rect.height;
    setTimelineOverlays((current) => current.map((item, index) => index === drag.index
      ? capNhatHinhHocOverlay(item, { x, y }, Math.round(totalDuration * 1000))
      : item));
  };

  // Lưu phiên bản Timeline (M-P3)
  const handleSaveTimeline = async (): Promise<{ success: boolean; versionId?: string; version?: number }> => {
    setIsSavingTimeline(true);
    setTimelineSaveMessage(null);
    setTimelineConflict(false);

    const doc: TimelineDocument = {
      width: 1080,
      height: 1920,
      fps: 30,
      clips: timelineClips,
      overlays: timelineOverlays,
      voice_track: timelineVoice,
      music_track: timelineMusic
        ? { ...timelineMusic, ducking_attenuation_db: musicAttenuationDb }
        : null,
      captions: taoPhuDeDeLuu(timelineCaptions, captionText, captionFontSize, Math.round(totalDuration * 1000)),
      caption_style: captionStyle,
      karaoke_settings: karaokeSettings,
      transition_seconds: transitionSeconds,
    };

    try {
      const res = await mediaStudioApi.saveTimeline(projectId, doc, timelineVersion);
      setTimelineVersion(res.version);
      setTimelineSaveMessage(`Đã lưu phiên bản Timeline v${res.version} thành công!`);
      return { success: true, versionId: res.id, version: res.version };
    } catch (err: any) {
      if (err?.message?.includes("409") || err?.message?.includes("Xung đột") || err?.message?.includes("STALE")) {
        setTimelineConflict(true);
        setTimelineSaveMessage("Xung đột phiên bản (OCC 409): Timeline đã được lưu bởi phiên khác. Vui lòng tải lại.");
      } else {
        setTimelineSaveMessage(`Lỗi lưu timeline: ${err?.message || "Không xác định"}`);
      }
      return { success: false };
    } finally {
      setIsSavingTimeline(false);
    }
  };

  // Kết xuất Video TikTok MP4 từ Timeline (M-P5)
  const handleRenderTimeline = async () => {
    if (timelineClips.length === 0) {
      setRenderTimelineError("Timeline chưa có phân cảnh nào để kết xuất. Vui lòng thêm ảnh hoặc video.");
      return;
    }

    setIsRenderingTimeline(true);
    setRenderTimelineError(null);
    setRenderTimelineProgress("Đang lưu trạng thái timeline và khởi chạy động cơ render FFmpeg (concurrency=1)...");

    try {
      // 1. Tự động lưu timeline trước khi render; nếu thất bại hoặc conflict thì hủy render ngay
      const saveRes = await handleSaveTimeline();
      if (!saveRes.success || !saveRes.versionId) {
        setRenderTimelineError("Không thể lưu timeline (xung đột phiên bản OCC 409 hoặc lỗi mạng). Đã dừng render để tránh kết xuất sai phiên bản cũ.");
        return;
      }

      setRenderTimelineProgress(`Đang chuẩn hóa phân cảnh dọc 9:16 (1080x1920), Safe Zone và hòa âm -14 LUFS cho bản v${saveRes.version || ""}...`);
      const result = await mediaStudioApi.renderTimeline(projectId, saveRes.versionId);

      setRenderTimelineProgress("Kết xuất hoàn tất 100%!");
      setRenderedTimelineAsset(result);
      if (result.url) {
        setPreviewSource({ url: result.url, type: "video" });
      }
      await loadAssets();
    } catch (err: any) {
      setRenderTimelineError(`Lỗi kết xuất: ${err?.message || "Tiến trình FFmpeg thất bại."}`);
    } finally {
      setIsRenderingTimeline(false);
    }
  };

  const handleAutoProduce = async () => {
    if (!projectId || !quickPrompt.trim() || isAutoProducing) return;
    setIsAutoProducing(true);
    setRenderTimelineError(null);
    setAiGenMessage(null);
    try {
      setAutoProduceStage("Kiểm tra Flow Music...");
      const capabilities = await mediaStudioApi.getMusicCapabilities();
      const musicCapability = capabilities.items.find((item) => item.provider === "FLOW_BROWSER_PILOT");
      if (!musicCapability?.enabled) {
        throw new Error(musicCapability?.blocked_reason || "Flow Music đang tắt trong cấu hình máy chủ.");
      }

      setAutoProduceStage("AI đang tạo nhạc nền bằng Flow Music...");
      const music = await mediaStudioApi.generateMusic({
        prompt: `Nhạc nền không lời cho video TikTok: ${quickPrompt.trim()}`,
        genre: "Pop",
        mood: "Upbeat",
        provider: "FLOW_BROWSER_PILOT",
        mode: "PILOT_ASSISTED",
        duration_sec: 30,
        project_id: projectId,
        idempotency_key: `auto_${projectId}_${randomUuid()}`,
      });

      setAutoProduceStage("Flow đang tạo video dọc 9:16...");
      const video = await mediaStudioApi.generateVideo({
        prompt: quickPrompt.trim(),
        aspect_ratio: "9:16",
        project_id: projectId,
        remove_watermark: autoCleanWatermark,
      });
      const durationMs = Math.max(1000, video.duration_ms || 10000);
      const document: TimelineDocument = {
        width: 1080,
        height: 1920,
        fps: 30,
        clips: [{
          clip_id: `clip_${randomUuid()}`,
          asset_id: video.id,
          media_type: "video",
          start_ms: 0,
          duration_ms: durationMs,
          trim_in_ms: 0,
          trim_out_ms: durationMs,
          fit: "cover",
        }],
        voice_track: null,
        music_track: { asset_id: music.id, start_ms: 0, duration_ms: durationMs, gain_db: 0 },
        caption_style: captionStyle,
        karaoke_settings: karaokeSettings,
        captions: captionText.trim() ? [{
          caption_id: `caption_${randomUuid()}`,
          text: captionText.trim(),
          start_ms: 0,
          duration_ms: durationMs,
          font_size: captionFontSize,
          safe_zone: true,
        }] : [],
      };

      setTimelineClips(document.clips);
      setTimelineMusic(document.music_track || null);
      setTimelineVoice(document.voice_track || null);
      setTimelineCaptions(document.captions || []);
      setCaptionText(document.captions?.[0]?.text ?? "");
      setAutoProduceStage("Đang lưu timeline và phiên bản...");
      const saved = await mediaStudioApi.saveTimeline(projectId, document, timelineVersion);
      setTimelineVersion(saved.version);

      setAutoProduceStage("Đang kết xuất MP4 TikTok...");
      const output = await mediaStudioApi.renderTimeline(projectId, saved.id);
      setRenderedTimelineAsset(output);
      if (output.url) {
        setPreviewSource({ url: output.url, type: "video" });
      }
      setAiGenMessage("Đã tạo video AI, nhạc nền, timeline và MP4 hoàn chỉnh.");
      setAutoProduceStage(null);
      await loadAssets();
    } catch (err: any) {
      setAiGenMessage(`Dừng tại bước tự động: ${err?.message || "Không xác định"}`);
      setAutoProduceStage(null);
    } finally {
      setIsAutoProducing(false);
    }
  };

  // Điều khiển Play / Pause
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  // Sao chép Prompt Flow Pro-Assisted (M-P6)
  const handleCopyFlowPrompt = () => {
    if (!flowPrompt) return;
    navigator.clipboard.writeText(flowPrompt);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2500);
  };

  // Khử logo Veo AI
  const handleCleanWatermark = async (assetId?: string) => {
    const targetId = assetId || selectedAssetId;
    if (!targetId) return;
    setIsCleaningWatermark(true);
    setCleanWatermarkMessage("Đang chạy Reverse Alpha Blending & NCNN AI để xóa sạch logo Veo...");
    try {
      const cleaned = await mediaStudioApi.removeWatermark({ asset_id: targetId });
      setCleanWatermarkMessage("Đã khử sạch watermark Veo AI thành công!");
      await loadAssets();
      setSelectedAssetId(cleaned.id);
      if (cleaned.url) {
        setPreviewSource({ url: cleaned.url, type: "video" });
      }
    } catch (err: any) {
      setCleanWatermarkMessage(`Lỗi xóa logo: ${err?.message || "Không xác định"}`);
    } finally {
      setIsCleaningWatermark(false);
    }
  };

  // Lọc tư liệu hiển thị
  const filteredAssets = assets.filter((a) => {
    if (assetFilter === "image") return a.mime_detected?.startsWith("image/");
    if (assetFilter === "video") return a.mime_detected?.startsWith("video/");
    if (assetFilter === "audio") return a.mime_detected?.startsWith("audio/");
    return true;
  });

  // Tìm clip đang chọn
  const activeSelectedClip = timelineClips.find((c) => c.clip_id === selectedClipId);
  const previewTimelineTimeMs = activeSelectedClip
    ? activeSelectedClip.start_ms + Math.max(0, currentTime * 1000 - (activeSelectedClip.trim_in_ms ?? 0))
    : currentTime * 1000;
  const previewCaptionCue = timelineCaptions.find((cue) => previewTimelineTimeMs >= cue.start_ms && previewTimelineTimeMs < cue.start_ms + cue.duration_ms);
  const previewCaption = timelineCaptions.length
    ? previewCaptionCue?.text ?? ""
    : captionText;
  const previewCanvasHeight = aspectRatio === "9:16" ? 360 : 270;
  const previewCaptionCueForDisplay = previewCaptionCue ?? (previewCaption
    ? { text: previewCaption, start_ms: 0, duration_ms: 0 }
    : undefined);
  const previewCaptionStyle = taoThongSoPhuDeXemTruoc(
    previewCaptionCueForDisplay,
    captionStyle,
    previewCanvasHeight,
    captionFontSize,
    karaokeSettings,
  );
  const karaokePreview = taoNoiDungPhuDeXemTruoc(
    previewCaptionCueForDisplay,
    previewTimelineTimeMs,
    karaokeSettings,
  );
  const isSelectedOverlayActive = selectedOverlay !== null && previewTimelineTimeMs >= selectedOverlay.start_ms
    && previewTimelineTimeMs < selectedOverlay.start_ms + selectedOverlay.duration_ms;

  React.useEffect(() => {
    const player = overlayVideoRef.current;
    if (!player || !selectedOverlay) return;
    if (!isSelectedOverlayActive || !isPlaying) {
      player.pause();
      return;
    }
    const elapsed = (previewTimelineTimeMs - selectedOverlay.start_ms) / 1000;
    const assetDuration = Number.isFinite(player.duration)
      ? player.duration
      : (selectedOverlayAsset?.duration_ms ?? 0) / 1000;
    const offset = assetDuration > 0 ? elapsed % assetDuration : elapsed;
    if (Math.abs(player.currentTime - offset) > 0.35) player.currentTime = offset;
    if (player.paused) void player.play().catch(() => {});
  }, [isPlaying, isSelectedOverlayActive, overlayPreviewUrl, previewTimelineTimeMs, selectedOverlay, selectedOverlayAsset?.duration_ms]);
  const captionsForSave = taoPhuDeDeLuu(timelineCaptions, captionText, captionFontSize, Math.round(totalDuration * 1000));

  if (projectLoadStatus !== "ready") {
    return (
      <main className="flex min-h-[60vh] items-center justify-center p-6">
        <Card className="w-full max-w-lg space-y-4 border-zinc-800 bg-zinc-950 p-6 text-zinc-100">
          <div>
            <h1 className="text-lg font-semibold">
              {projectLoadStatus === "loading" ? "Đang tải dự án video" : projectLoadStatus === "missing" ? "Không tìm thấy dự án" : "Không thể tải dự án"}
            </h1>
            <p className="mt-2 text-sm text-zinc-400">
              {projectLoadStatus === "loading" ? "Đang kiểm tra dữ liệu dự án trong workspace." : projectLoadStatus === "missing" ? "Dự án này không còn trong workspace. Quay lại danh sách để chọn dự án đang có." : projectError}
            </p>
          </div>
          <div className="flex gap-2">
            {projectLoadStatus === "error" && <Button variant="outline" onClick={() => void loadProject()}>Thử tải lại</Button>}
            <Button onClick={() => router.push("/video-studio")}>Về danh sách video</Button>
          </div>
        </Card>
      </main>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] bg-zinc-950 text-zinc-100 rounded-2xl overflow-hidden border border-zinc-800 shadow-2xl">
      {/* 1. Header Điều Khiển Phòng Thu (Studio Top Control Header) */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 bg-zinc-900/95 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/video-studio")}
            className="size-8 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
          >
            <ArrowLeft className="size-4" />
          </Button>

          <div className="flex items-center gap-2">
            <span className="font-bold text-xs text-white">
              {projectTitle}
            </span>
            <Badge variant="outline" className="border-teal-500/40 text-teal-400 bg-teal-500/10 text-[10px] font-mono">
              Timeline v{timelineVersion}
            </Badge>
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10 text-[10px] font-mono">
              9:16 TikTok 1080x1920
            </Badge>
          </div>
        </div>

        {/* Thanh công cụ xem trước trung tâm */}
        <div className="flex items-center gap-2">
          <Button
            variant={showSafeZone ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setShowSafeZone(!showSafeZone)}
            className="h-7 text-xs font-medium rounded-lg bg-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-white"
            title="Bật/Tắt Safe Zone TikTok (Top 150px, Bottom 320px, Right 120px)"
          >
            <ShieldAlert className="size-3.5 mr-1 text-amber-400" />
            <span>Safe Zone</span>
          </Button>

          <div className="flex items-center gap-1 bg-zinc-800 p-0.5 rounded-lg text-xs">
            <button
              onClick={() => setAspectRatio("9:16")}
              className={`px-2 py-0.5 rounded font-mono font-bold transition-colors ${
                aspectRatio === "9:16" ? "bg-teal-600 text-white" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              9:16
            </button>
            <button
              onClick={() => setAspectRatio("16:9")}
              className={`px-2 py-0.5 rounded font-mono font-bold transition-colors ${
                aspectRatio === "16:9" ? "bg-teal-600 text-white" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              16:9
            </button>
          </div>
        </div>

        {/* Cụm Nút Lưu Timeline & Render Video */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadAssets();
              loadTimeline();
            }}
            disabled={isLoadingAssets}
            className="h-8 text-xs font-medium border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
          >
            <RefreshCw className={`size-3.5 mr-1 text-teal-400 ${isLoadingAssets ? "animate-spin" : ""}`} />
            <span>Đồng bộ</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveTimeline}
            disabled={isSavingTimeline}
            className="h-8 text-xs font-semibold border-teal-500/40 bg-teal-950/30 hover:bg-teal-900/40 text-teal-200 gap-1.5"
          >
            {isSavingTimeline ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <Save className="size-3.5" />
            )}
            <span>Lưu Timeline (v{timelineVersion})</span>
          </Button>

          <Button
            size="sm"
            onClick={handleRenderTimeline}
            disabled={isRenderingTimeline || timelineClips.length === 0}
            className="h-8 text-xs font-semibold rounded-lg bg-teal-600 hover:bg-teal-500 text-white gap-1.5 shadow-sm"
          >
            {isRenderingTimeline ? (
              <RefreshCw className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            <span>Kết Xuất TikTok MP4 (1080x1920)</span>
          </Button>
        </div>
      </div>

      {/* Thông báo trạng thái lưu timeline nếu có */}
      {timelineSaveMessage && (
        <div
          className={`px-4 py-1.5 text-xs flex items-center justify-between border-b ${
            timelineConflict
              ? "bg-red-950/60 border-red-800 text-red-200"
              : "bg-teal-950/40 border-teal-800 text-teal-300"
          }`}
        >
          <span>{timelineSaveMessage}</span>
          {timelineConflict && (
            <Button size="sm" variant="outline" onClick={loadTimeline} className="h-6 text-[10px]">
              Tải lại phiên bản mới nhất
            </Button>
          )}
        </div>
      )}
      {timelineLoadError && (
        <div role="alert" className="border-b border-red-900 bg-red-950/60 px-4 py-2 text-xs text-red-200">
          Không tải được timeline: {timelineLoadError}
          <Button size="sm" variant="outline" onClick={loadTimeline} className="ml-3 h-6 text-[10px]">Thử lại</Button>
        </div>
      )}

      {/* 2. Thân Studio: 3 Cột (Trái: Kho Tư Liệu & AI, Giữa: Canvas Xem Trước, Phải: Thuộc Tính) */}
      <div className="flex-1 grid grid-cols-12 min-h-0 overflow-hidden">
        {/* Cột 1: Kho Tư Liệu & AI Generator (3 cols) */}
        <div className="col-span-3 border-r border-zinc-800 bg-zinc-900/60 p-3 flex flex-col justify-between overflow-hidden">
          <Tabs defaultValue="media" className="flex flex-col h-full">
            <TabsList className="grid grid-cols-5 bg-zinc-800/80 p-0.5 rounded-lg mb-3">
              <TabsTrigger value="media" className="text-[10px] py-1 text-zinc-400 hover:text-white data-active:bg-zinc-700 data-active:text-white">Tư Liệu</TabsTrigger>
              <TabsTrigger value="ai" className="text-[10px] py-1 text-zinc-400 hover:text-white data-active:bg-zinc-700 data-active:text-white">AI Flow</TabsTrigger>
              <TabsTrigger value="audio" className="text-[10px] py-1 text-zinc-400 hover:text-white data-active:bg-zinc-700 data-active:text-white">Âm Thanh</TabsTrigger>
              <TabsTrigger value="text" className="text-[10px] py-1 text-zinc-400 hover:text-white data-active:bg-zinc-700 data-active:text-white">Phụ Đề</TabsTrigger>
              <TabsTrigger value="harness" className="text-[10px] py-1 text-zinc-400 hover:text-white data-active:bg-zinc-700 data-active:text-white">Đạo Diễn</TabsTrigger>
            </TabsList>

            {/* Tab Tư Liệu (M-P2: Nạp Ảnh / Video) */}
            <TabsContent value="media" className="flex-1 overflow-y-auto space-y-2.5 pr-1 mt-0">
              {/* Nút Tải Lên Tư Liệu */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept="image/*,video/*,audio/*"
                className="hidden"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="w-full h-8 text-xs font-semibold border-teal-500/50 bg-teal-950/30 hover:bg-teal-900/40 text-teal-200 gap-1.5"
              >
                {isUploading ? (
                  <RefreshCw className="size-3.5 animate-spin" />
                ) : (
                  <UploadCloud className="size-3.5 text-teal-400" />
                )}
                <span>Tải Tư Liệu Lên (Ảnh / Video / Audio)</span>
              </Button>

              {uploadMessage && (
                <p className="text-[10px] text-zinc-300 p-1.5 rounded bg-zinc-800/70 border border-zinc-700">
                  {uploadMessage}
                </p>
              )}
              {isUploading && uploadProgress !== null && (
                <div className="flex items-center gap-2 px-1.5">
                  <progress
                    aria-label="Tiến độ tải tệp lên"
                    className="h-2 w-full accent-teal-400"
                    max={100}
                    value={uploadProgress}
                  />
                  <span className="min-w-9 text-right text-[10px] text-zinc-300">{uploadProgress}%</span>
                </div>
              )}

              {/* Bộ lọc loại tư liệu */}
              <div className="flex items-center gap-1 bg-zinc-800 p-0.5 rounded text-[10px]">
                <button
                  onClick={() => setAssetFilter("all")}
                  className={`flex-1 py-0.5 rounded font-medium ${assetFilter === "all" ? "bg-teal-600 text-white" : "text-zinc-400"}`}
                >
                  Tất cả ({assets.length})
                </button>
                <button
                  onClick={() => setAssetFilter("image")}
                  className={`flex-1 py-0.5 rounded font-medium ${assetFilter === "image" ? "bg-teal-600 text-white" : "text-zinc-400"}`}
                >
                  Ảnh
                </button>
                <button
                  onClick={() => setAssetFilter("video")}
                  className={`flex-1 py-0.5 rounded font-medium ${assetFilter === "video" ? "bg-teal-600 text-white" : "text-zinc-400"}`}
                >
                  Video
                </button>
                <button
                  onClick={() => setAssetFilter("audio")}
                  className={`flex-1 py-0.5 rounded font-medium ${assetFilter === "audio" ? "bg-teal-600 text-white" : "text-zinc-400"}`}
                >
                  Audio
                </button>
              </div>

              {/* Danh Sách Tư Liệu */}
              {filteredAssets.length === 0 ? (
                <div className="p-4 border border-dashed border-zinc-800 rounded-lg text-center text-xs text-zinc-500 space-y-2">
                  <Film className="size-6 mx-auto text-zinc-600" />
                  <p>{assets.length === 0 ? "Thư viện chưa có tư liệu." : "Không có tư liệu thuộc bộ lọc này."}</p>
                  <p className="text-zinc-600">Tải video, ảnh hoặc âm thanh lên để bắt đầu dựng.</p>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {filteredAssets.map((asset) => {
                    const isImg = asset.mime_detected?.startsWith("image/");
                    const isVid = asset.mime_detected?.startsWith("video/");
                    const isAud = asset.mime_detected?.startsWith("audio/");

                    return (
                      <div
                        key={asset.id}
                        onClick={() => {
                          setSelectedAssetId(asset.id);
                          if (asset.url && !isAud) {
                            setPreviewSource({ url: asset.url, type: isImg ? "image" : "video" });
                          }
                        }}
                        className={`p-2 rounded-lg border text-xs cursor-pointer transition-all flex items-center justify-between ${
                          selectedAssetId === asset.id
                            ? "border-teal-500 bg-teal-950/40"
                            : "border-zinc-800 bg-zinc-800/40 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {isImg ? (
                            <ImageIcon className="size-4 text-amber-400 shrink-0" />
                          ) : isVid ? (
                            <FileVideo className="size-4 text-blue-400 shrink-0" />
                          ) : (
                            <FileAudio className="size-4 text-emerald-400 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <p className="font-medium text-white truncate text-[11px]">
                              {asset.original_filename || asset.id}
                            </p>
                            <p className="text-[9px] text-zinc-400 font-mono">
                              {(asset.byte_size / 1024).toFixed(0)} KB • {isImg ? "Ảnh tĩnh" : isVid ? `${((asset.duration_ms || 0)/1000).toFixed(1)}s` : "Âm thanh"}
                            </p>
                          </div>
                        </div>

                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                            e.stopPropagation();
                            handleAddAssetToTimeline(asset);
                          }}
                          className="size-6 p-0 text-teal-400 hover:text-white hover:bg-teal-600/40"
                          title="Thêm vào Timeline"
                        >
                          <Plus className="size-3.5" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </TabsContent>

            {/* Tab AI Flow (M-P6: Flow Pro-Assisted Reference Image) */}
            <TabsContent value="ai" className="flex-1 overflow-y-auto space-y-3 mt-0 pr-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                Flow Pro-Assisted (Ảnh Tham Chiếu)
              </span>

              <div className="p-2.5 rounded-lg border border-purple-500/30 bg-purple-950/20 text-xs space-y-2">
                <span className="font-semibold text-purple-300 block text-[11px]">
                  1. Chọn ảnh tham chiếu từ thư viện:
                </span>
                <select
                  value={refImageAssetId || ""}
                  onChange={(e) => setRefImageAssetId(e.target.value)}
                  className="w-full h-8 px-2 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white"
                >
                  <option value="">-- Chọn ảnh làm nguồn tham chiếu --</option>
                  {assets
                    .filter((a) => a.mime_detected?.startsWith("image/"))
                    .map((img) => (
                      <option key={img.id} value={img.id}>
                        {img.original_filename || img.id}
                      </option>
                    ))}
                </select>

                <div className="space-y-1">
                  <label className="text-[10px] text-zinc-400">2. Câu lệnh mô tả video (Prompt):</label>
                  <textarea
                    value={flowPrompt}
                    onChange={(e) => setFlowPrompt(e.target.value)}
                    placeholder="Mô tả chuyển động cho ảnh tham chiếu: Máy quay di chuyển cận cảnh, ánh sáng ấm áp..."
                    className="w-full h-16 p-2 text-xs bg-zinc-900 border border-zinc-700 rounded-lg text-white resize-none"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCopyFlowPrompt}
                    disabled={!flowPrompt}
                    className="flex-1 h-7 text-[10px] border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800 hover:text-white"
                  >
                    <Copy className="size-3 mr-1" />
                    {copiedPrompt ? "Đã chép!" : "Sao chép Prompt"}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => window.open("https://flow.google/", "_blank")}
                    className="flex-1 h-7 text-[10px] bg-purple-600 hover:bg-purple-500 text-white"
                  >
                    <ExternalLink className="size-3 mr-1" /> Mở Flow Web
                  </Button>
                </div>

                <p className="text-[9px] text-zinc-400 leading-relaxed italic border-t border-purple-500/20 pt-1.5">
                  Quy trình Pro-Assisted: Bạn tự nạp ảnh lên Flow, kết xuất video rồi tải về máy và nhấn &quot;Tải Tư Liệu Lên&quot; để đưa vào dự án.
                </p>
              </div>

              {/* Tạo video, nhạc và bản dựng trong một lượt */}
              <div className="border-t border-zinc-800 pt-2 space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                  Tạo video AI từ mô tả
                </span>
                <textarea
                  value={quickPrompt}
                  onChange={(e) => setQuickPrompt(e.target.value)}
                  placeholder="Chủ đề và mô tả cảnh video cần tạo..."
                  className="w-full h-14 p-2 text-xs bg-zinc-800 border border-zinc-700 rounded-lg text-white resize-none"
                />
                <Button
                  size="sm"
                  onClick={handleAutoProduce}
                  disabled={isAutoProducing || isGeneratingAi || !quickPrompt.trim()}
                  className="w-full h-8 text-[10px] bg-teal-600 hover:bg-teal-500 text-white"
                >
                  {isAutoProducing ? "Đang chạy pipeline..." : "Tạo video AI và dựng MP4 hoàn chỉnh"}
                </Button>
                {autoProduceStage && <p role="status" className="text-[10px] text-teal-300">{autoProduceStage}</p>}
                {aiGenMessage && <p className="text-[9px] text-zinc-400">{aiGenMessage}</p>}
                <p className="text-[9px] text-zinc-500">Luồng lần lượt tạo nhạc Flow, tạo video dọc, ghép phụ đề và kết xuất MP4.</p>
              </div>
            </TabsContent>

            {/* Tab Âm Thanh (Audio & Ducking) */}
            <TabsContent value="audio" className="flex-1 overflow-y-auto space-y-2.5 mt-0 pr-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                Cấu Hình Âm Thanh & Auto-Ducking
              </span>

              <div className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-800/40 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-300">Độ hạ nhạc nền (Auto-Ducking):</span>
                  <span className="font-mono text-teal-400 font-bold">{musicAttenuationDb} dB</span>
                </div>
                <Slider
                  value={[musicAttenuationDb]}
                  min={-30}
                  max={-6}
                  step={1}
                  onValueChange={(val: number[]) => setMusicAttenuationDb(val[0])}
                />
                <p className="text-[10px] text-zinc-500">
                  Tự động dìm nhạc khi có giọng đọc thuyết minh để giữ trọn sự rõ ràng của lời nói.
                </p>
              </div>

              <div className="p-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-xs space-y-1">
                <div className="flex items-center justify-between text-emerald-400 font-medium">
                  <span>Chuẩn Âm Lượng TikTok</span>
                  <Badge variant="outline" className="border-emerald-500 text-emerald-300 text-[9px]">
                    -14 LUFS (EBU R128)
                  </Badge>
                </div>
                <p className="text-[10px] text-zinc-400">
                  Âm lượng được chuẩn hóa tự động qua bộ lọc loudnorm, không bị nền tảng bóp nhỏ.
                </p>
              </div>
            </TabsContent>

            {/* Tab Phụ Đề (Captions) */}
            <TabsContent value="text" className="flex-1 overflow-y-auto space-y-2 mt-0 pr-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
                Phụ Đề An Toàn TikTok (Safe Zone)
              </span>

              <div className="space-y-1.5">
                <span className="text-[10px] text-zinc-400 block">Kiểu phụ đề</span>
                <ToggleGroup
                  type="single"
                  value={captionStyle ?? "legacy"}
                  aria-label="Kiểu phụ đề"
                  variant="outline"
                  size="sm"
                  className="grid w-full grid-cols-3"
                  onValueChange={(value) => {
                    if (value === "legacy" || value === "vietsub_v1" || value === "vietsub_karaoke_v2") {
                      setCaptionStyle(value);
                    }
                  }}
                >
                  <ToggleGroupItem value="legacy" className="px-1 text-[10px]">Cơ bản</ToggleGroupItem>
                  <ToggleGroupItem value="vietsub_v1" className="px-1 text-[10px]">Vietsub</ToggleGroupItem>
                  <ToggleGroupItem value="vietsub_karaoke_v2" className="px-1 text-[10px]">Karaoke</ToggleGroupItem>
                </ToggleGroup>
              </div>

              {captionStyle === "vietsub_karaoke_v2" && (
                <div className="space-y-2.5 rounded-lg border border-zinc-700 bg-zinc-900/70 p-2.5">
                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-400 block">Phong cách</span>
                    <ToggleGroup
                      type="single"
                      value={karaokeSettings.preset}
                      aria-label="Phong cách karaoke"
                      variant="outline"
                      size="sm"
                      className="grid w-full grid-cols-2"
                      onValueChange={(value) => {
                        const preset = KARAOKE_PRESETS.find((item) => item.value === value);
                        if (preset) {
                          setKaraokeSettings((current) => ({
                            ...current,
                            preset: preset.value,
                            accent_color: preset.accent_color,
                            word_pop: preset.word_pop,
                            layout: preset.layout,
                          }));
                        }
                      }}
                    >
                      {KARAOKE_PRESETS.map((preset) => (
                        <ToggleGroupItem key={preset.value} value={preset.value} className="px-1 text-[10px]">
                          {preset.label}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-400 block">Cỡ chữ</span>
                    <ToggleGroup
                      type="single"
                      value={String(karaokeSettings.font_size)}
                      aria-label="Cỡ chữ karaoke"
                      variant="outline"
                      size="sm"
                      className="grid w-full grid-cols-3"
                      onValueChange={(value) => {
                        const size = Number(value);
                        if (size === 64 || size === 84 || size === 100) {
                          setKaraokeSettings((current) => ({ ...current, font_size: size }));
                        }
                      }}
                    >
                      {[64, 84, 100].map((size) => (
                        <ToggleGroupItem key={size} value={String(size)} className="text-[10px]">{size}px</ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-400 block">Bố cục</span>
                    <ToggleGroup
                      type="single"
                      value={karaokeSettings.layout}
                      aria-label="Bố cục phụ đề karaoke"
                      variant="outline"
                      size="sm"
                      className="grid w-full grid-cols-3"
                      onValueChange={(value) => {
                        if (value === "center" || value === "left" || value === "two_line") {
                          setKaraokeSettings((current) => ({ ...current, layout: value }));
                        }
                      }}
                    >
                      <ToggleGroupItem value="center" className="px-1 text-[10px]">Giữa</ToggleGroupItem>
                      <ToggleGroupItem value="left" className="px-1 text-[10px]">Trái</ToggleGroupItem>
                      <ToggleGroupItem value="two_line" className="px-1 text-[10px]">Hai dòng</ToggleGroupItem>
                    </ToggleGroup>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-zinc-400 block">Màu nhấn</span>
                    <ToggleGroup
                      type="single"
                      value={karaokeSettings.accent_color}
                      aria-label="Màu nhấn karaoke"
                      variant="outline"
                      size="sm"
                      className="grid w-full grid-cols-3"
                      onValueChange={(value) => {
                        if (value === "champagne" || value === "baha_blue" || value === "coral") {
                          setKaraokeSettings((current) => ({ ...current, accent_color: value }));
                        }
                      }}
                    >
                      {([
                        ["champagne", "Vàng champagne"],
                        ["baha_blue", "Xanh BAHA"],
                        ["coral", "Đỏ san hô"],
                      ] as const).map(([value, label]) => (
                        <ToggleGroupItem key={value} value={value} className="gap-1 px-1 text-[9px]">
                          <span className="size-2.5 rounded-full border border-white/30" style={{ backgroundColor: KARAOKE_CAPTION_COLORS[value] }} />
                          {label}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </div>

                  <div className="grid grid-cols-3 gap-1 border-t border-zinc-700 pt-2">
                    {([
                      ["outline", "Viền chữ"],
                      ["shadow", "Bóng chữ"],
                      ["word_pop", "Nảy từ"],
                    ] as const).map(([key, label]) => (
                      <label key={key} className="flex items-center gap-1.5 text-[10px] text-zinc-300">
                        <Switch
                          checked={karaokeSettings[key]}
                          aria-label={label}
                          onCheckedChange={(checked) => setKaraokeSettings((current) => ({ ...current, [key]: checked }))}
                          size="sm"
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-[10px] text-zinc-400">
                  {timelineCaptions[0] ? `Câu 1 · ${(timelineCaptions[0].start_ms / 1000).toFixed(1)}–${((timelineCaptions[0].start_ms + timelineCaptions[0].duration_ms) / 1000).toFixed(1)} giây` : "Tạo phụ đề đầu tiên"}
                </label>
                <Input
                  value={captionText}
                  aria-label="Sửa câu phụ đề đầu tiên"
                  onChange={(e) => {
                    const text = e.target.value;
                    setCaptionText(text);
                    setTimelineCaptions((current) => current.map((cue, index) => index === 0 ? { ...cue, text, words: [] } : cue));
                  }}
                  className="h-8 text-xs bg-zinc-800 border-zinc-700 text-white font-bold"
                />
              </div>

              {timelineCaptions.slice(1).map((cue, index) => (
                <div className="space-y-1.5" key={cue.caption_id}>
                  <label className="text-[10px] text-zinc-400">Câu {index + 2} · {(cue.start_ms / 1000).toFixed(1)}–{((cue.start_ms + cue.duration_ms) / 1000).toFixed(1)} giây</label>
                  <Input
                    aria-label={`Sửa câu phụ đề ${index + 2}`}
                    value={cue.text}
                    onChange={(event) => setTimelineCaptions((current) => current.map((item) => item.caption_id === cue.caption_id ? { ...item, text: event.target.value, words: [] } : item))}
                    className="h-8 text-xs bg-zinc-800 border-zinc-700 text-white"
                  />
                </div>
              ))}

              {captionStyle !== "vietsub_karaoke_v2" && <div className="space-y-1.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>Cỡ chữ:</span>
                  <span className="font-mono text-zinc-200">{captionFontSize}px</span>
                </div>
                <Slider
                  value={[captionFontSize]}
                  min={16}
                  max={64}
                  step={2}
                  onValueChange={(val: number[]) => {
                    setCaptionFontSize(val[0]);
                    setTimelineCaptions((current) => current.map((cue) => ({ ...cue, font_size: val[0] })));
                  }}
                />
              </div>}

              <div className="p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-center text-amber-300 font-bold uppercase tracking-wide">
                {previewCaption || "Chưa có phụ đề"}
              </div>
            </TabsContent>

            {/* Tab Đạo Diễn Điều Phối (Director Harness H10) */}
            <TabsContent value="harness" className="flex-1 overflow-y-auto space-y-2 mt-0 pr-1">
              <BangDieuPhoiDung
                projectId={projectId}
                currentRevision={timelineVersion}
                timelineDoc={{
                  clips: timelineClips,
                  captions: captionsForSave.map((cue) => ({ ...cue, end_ms: cue.start_ms + cue.duration_ms })),
                  audio_tracks: [
                    ...(timelineVoice ? [{ track_id: "voice_trk", asset_id: timelineVoice.asset_id, volume: 1.0 }] : []),
                    ...(timelineMusic ? [{ track_id: "music_trk", asset_id: timelineMusic.asset_id, volume: 0.8 }] : [])
                  ]
                }}
                onTimelineUpdate={loadTimeline}
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Cột 2: Khung Canvas Xem Trước (6 cols) */}
        <div className="col-span-6 flex flex-col items-center justify-center p-4 bg-zinc-950 relative overflow-hidden">
          <div
            ref={previewCanvasRef}
            className={`relative rounded-xl overflow-hidden border-2 border-zinc-800 bg-black shadow-2xl flex items-center justify-center transition-all ${
              aspectRatio === "9:16" ? "h-[360px] aspect-[9/16]" : "w-[480px] aspect-[16/9]"
            }`}
          >
            {/* Hiển thị Video hoặc Ảnh */}
            {previewMediaUrl ? (
              previewMediaType === "image" ? (
                <img
                  src={previewMediaUrl}
                  alt="Canvas Preview"
                  className={`size-full ${activeSelectedClip?.fit === "contain" ? "object-contain" : "object-cover"}`}
                  onError={() => {
                    setPreviewMediaUrl(null);
                    setPreviewError("Không thể tải tư liệu xem trước từ máy chủ.");
                  }}
                />
              ) : (
                <video
                  ref={videoRef}
                  src={previewMediaUrl}
                  className={`size-full ${activeSelectedClip?.fit === "contain" ? "object-contain" : "object-cover"}`}
                  preload="metadata"
                  playsInline
                  loop
                  onError={() => {
                    setPreviewMediaUrl(null);
                    setPreviewError("Không thể phát tư liệu xem trước từ máy chủ.");
                  }}
                  onLoadedMetadata={() => {
                    const trimInMs = activeSelectedClip?.trim_in_ms ?? 0;
                    if (trimInMs && videoRef.current) videoRef.current.currentTime = trimInMs / 1000;
                  }}
                  onTimeUpdate={() => {
                    if (videoRef.current) {
                      setCurrentTime(videoRef.current.currentTime);
                    }
                  }}
                />
              )
            ) : (
              <div className="flex flex-col items-center justify-center text-zinc-600 space-y-2">
                <Film className="size-8" />
                <span className="max-w-56 text-center text-xs">{isLoadingPreview ? "Đang tải bản xem trước" : previewError || "Tải video hoặc chọn một phân cảnh để xem trước"}</span>
              </div>
            )}

            {selectedOverlay && overlayPreviewUrl && (
              <div
                role="button"
                tabIndex={0}
                aria-pressed={selectedOverlayIndex !== null}
                aria-label="Kéo để đổi vị trí lớp diễn họa; dùng phím mũi tên để tinh chỉnh"
                className={`absolute z-10 touch-none cursor-move ${selectedOverlayIndex !== null ? "ring-1 ring-teal-300" : ""}`}
                style={{
                  left: `${selectedOverlay.x / 1080 * 100}%`,
                  top: `${selectedOverlay.y / 1920 * 100}%`,
                  width: `${selectedOverlay.width / 1080 * 100}%`,
                  height: `${selectedOverlay.height / 1920 * 100}%`,
                }}
                onPointerDown={(event) => {
                  if (selectedOverlayIndex !== null) handleOverlayPointerDown(selectedOverlayIndex, event);
                }}
                onPointerMove={handleOverlayPointerMove}
                onPointerUp={() => { overlayDragRef.current = null; }}
                onPointerCancel={() => { overlayDragRef.current = null; }}
                onKeyDown={(event) => {
                  const nudge = event.shiftKey ? 10 : 1;
                  if (event.key === "ArrowLeft") handleUpdateSelectedOverlay({ x: selectedOverlay.x - nudge });
                  else if (event.key === "ArrowRight") handleUpdateSelectedOverlay({ x: selectedOverlay.x + nudge });
                  else if (event.key === "ArrowUp") handleUpdateSelectedOverlay({ y: selectedOverlay.y - nudge });
                  else if (event.key === "ArrowDown") handleUpdateSelectedOverlay({ y: selectedOverlay.y + nudge });
                  else return;
                  event.preventDefault();
                }}
              >
                {selectedOverlayAsset?.mime_detected.startsWith("image/") ? (
                  <img src={overlayPreviewUrl} alt="Diễn họa giấy gấp" className="size-full object-contain pointer-events-none" />
                ) : (
                  <video
                    ref={overlayVideoRef}
                    src={overlayPreviewUrl}
                    muted
                    loop
                    playsInline
                    preload="metadata"
                    className="size-full object-contain pointer-events-none"
                    onLoadedMetadata={(event) => {
                      const offset = Math.max(0, previewTimelineTimeMs - selectedOverlay.start_ms) / 1000;
                      event.currentTarget.currentTime = event.currentTarget.duration > 0
                        ? offset % event.currentTarget.duration
                        : offset;
                    }}
                  />
                )}
              </div>
            )}

            {/* Ranh Giới Vùng An Toàn TikTok (Safe Zone TikTok Overlay) */}
            {showSafeZone && aspectRatio === "9:16" && (
              <div className="absolute inset-0 pointer-events-none border border-dashed border-red-500/40">
                <div className="absolute top-0 inset-x-0 h-10 border-b border-red-500/30 bg-red-500/10 flex items-center justify-center text-[9px] text-red-400 font-mono">
                  Safe Zone Top (Tránh nút tìm kiếm)
                </div>
                <div className="absolute bottom-0 inset-x-0 h-16 border-t border-red-500/30 bg-red-500/10 flex items-center justify-center text-[9px] text-red-400 font-mono">
                  Safe Zone Bottom (Tránh caption & audio bar)
                </div>
                <div className="absolute top-10 bottom-16 right-0 w-8 border-l border-red-500/30 bg-red-500/10 flex items-center justify-center text-[8px] text-red-400 [writing-mode:vertical-lr] font-mono">
                  Safe Zone Right (Tránh nút tương tác)
                </div>
              </div>
            )}

            {/* Lớp Phụ Đề Chữ Nổi Bật Nằm Trong Vùng An Toàn */}
            {previewCaption && (
              <div
                className={`absolute z-20 pointer-events-none flex ${captionStyle === "legacy" ? "inset-x-4 bottom-20" : captionStyle === "vietsub_karaoke_v2" ? "inset-x-10" : "inset-x-4"} ${previewCaptionStyle.textAlign === "left" ? "justify-start text-left" : "justify-center text-center"}`}
                style={captionStyle === "vietsub_v1"
                  ? { top: `${previewCaptionStyle.topPercent}%` }
                  : captionStyle === "vietsub_karaoke_v2"
                    ? { top: `${previewCaptionStyle.topPercent}%`, transform: "translateY(-50%)" }
                    : undefined}
              >
                <span
                  style={captionStyle === "vietsub_karaoke_v2" ? {
                    fontSize: `${previewCaptionStyle.fontSizePx}px`,
                    color: "white",
                    WebkitTextStroke: karaokeSettings.outline
                      ? `${Math.max(0.6, previewCaptionStyle.fontSizePx * 0.035)}px rgba(0,0,0,0.96)`
                      : "transparent",
                    textShadow: karaokeSettings.shadow ? "0 3px 7px rgba(0,0,0,0.9)" : "none",
                    lineHeight: 1.12,
                  } : { fontSize: `${previewCaptionStyle.fontSizePx}px` }}
                  className={captionStyle === "vietsub_v1"
                    ? `font-extrabold text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)] px-1 py-0.5 rounded-none ${previewCaptionCueForDisplay?.visual_type === "callout" ? "bg-teal-700/95" : "bg-black/70"}`
                    : captionStyle === "vietsub_karaoke_v2"
                      ? "inline-block max-w-full px-2 py-1 font-black motion-reduce:transition-none motion-reduce:transform-none"
                      : "font-extrabold text-amber-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)] px-2 py-1 bg-black/60 rounded"}
                >
                  {captionStyle === "vietsub_karaoke_v2"
                    ? karaokePreview.words.map((word, index) => (
                      <React.Fragment key={`${index}-${word.text}`}>
                        {karaokePreview.breakAfter === index && <br />}
                        <span
                          className={`inline-block transition-transform duration-100 motion-reduce:transition-none motion-reduce:scale-100 ${word.active && karaokeSettings.word_pop ? "scale-105" : ""}`}
                          style={{
                            color: word.active ? KARAOKE_CAPTION_COLORS[karaokeSettings.accent_color] : "white",
                          }}
                        >
                          {word.text}
                        </span>
                        {index < karaokePreview.words.length - 1 ? " " : ""}
                      </React.Fragment>
                    ))
                    : previewCaption}
                </span>
              </div>
            )}
          </div>

          {/* Thanh Điều Khiển Phát Nhanh */}
          <div className="flex items-center gap-4 mt-3 bg-zinc-900/90 px-4 py-1.5 rounded-full border border-zinc-800 shadow-md">
            <button
              onClick={togglePlay}
              disabled={!previewMediaUrl || previewMediaType !== "video"}
              aria-label={isPlaying ? "Dừng xem trước" : "Phát xem trước"}
              className="text-white hover:text-teal-400 transition-colors p-1"
            >
              {isPlaying ? <Pause className="size-4 fill-current" /> : <Play className="size-4 fill-current ml-0.5" />}
            </button>
            <span className="font-mono text-xs text-zinc-300 font-bold">
              00:{currentTime < 10 ? `0${currentTime.toFixed(1)}` : currentTime.toFixed(1)} / 00:
              {totalDuration < 10 ? `0${totalDuration.toFixed(1)}` : totalDuration.toFixed(1)}
            </span>
          </div>
        </div>

        {/* Cột 3: Thuộc Tính & Phân Tích (3 cols) */}
        <div className="col-span-3 border-l border-zinc-800 bg-zinc-900/60 p-3 space-y-4 overflow-y-auto">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Sliders className="size-3.5 text-teal-400" /> Bảng Thuộc Tính (Inspector)
            </span>
            <Badge variant="outline" className="text-[9px] border-zinc-700 text-zinc-400">
              TikTok 9:16
            </Badge>
          </div>

          {/* Chi tiết Clip được chọn trên Timeline */}
          {activeSelectedClip ? (
            <div className="p-2.5 rounded-lg border border-teal-500/40 bg-teal-950/20 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-teal-300 flex items-center gap-1">
                  {activeSelectedClip.media_type === "image" ? <ImageIcon className="size-3.5" /> : <Film className="size-3.5" />}
                  Phân cảnh: {activeSelectedClip.clip_id}
                </span>
                <Badge variant="outline" className="text-[9px] border-teal-500 text-teal-300">
                  {activeSelectedClip.media_type === "image" ? "Ảnh" : "Video"}
                </Badge>
              </div>

              {/* Cắt xén Video Trim In/Out & Thời lượng */}
              {activeSelectedClip.media_type === "video" ? (
                <div className="space-y-2 border-t border-zinc-800/80 pt-2">
                  {(() => {
                    const matchedAsset = assets.find((a) => a.id === activeSelectedClip.asset_id);
                    const sourceMaxDurationMs = matchedAsset?.duration_ms && matchedAsset.duration_ms > 0
                      ? matchedAsset.duration_ms
                      : (activeSelectedClip.trim_out_ms && activeSelectedClip.trim_out_ms > 60000 ? activeSelectedClip.trim_out_ms : 60000);

                    return (
                      <>
                        <div className="space-y-1">
                          <div className="flex justify-between text-[11px] text-zinc-300">
                            <span>Điểm vào (Trim In):</span>
                            <span className="font-mono text-teal-400">
                              {((activeSelectedClip.trim_in_ms || 0) / 1000).toFixed(1)}s
                            </span>
                          </div>
                          <Slider
                            value={[activeSelectedClip.trim_in_ms || 0]}
                            min={0}
                            max={Math.max(0, (activeSelectedClip.trim_out_ms || activeSelectedClip.duration_ms || sourceMaxDurationMs) - 500)}
                            step={100}
                            onValueChange={(val: number[]) => {
                              const newTrimIn = val[0];
                              const currentTrimOut = activeSelectedClip.trim_out_ms || (activeSelectedClip.duration_ms || sourceMaxDurationMs);
                              const newTrimOut = Math.max(currentTrimOut, newTrimIn + 500);
                              handleUpdateSelectedClip({
                                trim_in_ms: newTrimIn,
                                trim_out_ms: Math.min(newTrimOut, sourceMaxDurationMs),
                                duration_ms: Math.min(newTrimOut, sourceMaxDurationMs) - newTrimIn,
                              });
                            }}
                          />
                        </div>

                        <div className="space-y-1">
                          <div className="flex justify-between text-[11px] text-zinc-300">
                            <span>Điểm ra (Trim Out):</span>
                            <span className="font-mono text-teal-400">
                              {(((activeSelectedClip.trim_out_ms || activeSelectedClip.duration_ms || sourceMaxDurationMs)) / 1000).toFixed(1)}s
                              {matchedAsset?.duration_ms ? ` / ${(matchedAsset.duration_ms / 1000).toFixed(1)}s` : ""}
                            </span>
                          </div>
                          <Slider
                            value={[Math.min(activeSelectedClip.trim_out_ms || activeSelectedClip.duration_ms || sourceMaxDurationMs, sourceMaxDurationMs)]}
                            min={(activeSelectedClip.trim_in_ms || 0) + 500}
                            max={sourceMaxDurationMs}
                            step={100}
                            onValueChange={(val: number[]) => {
                              const newTrimOut = Math.min(val[0], sourceMaxDurationMs);
                              const currentTrimIn = activeSelectedClip.trim_in_ms || 0;
                              handleUpdateSelectedClip({
                                trim_out_ms: newTrimOut,
                                duration_ms: Math.max(500, newTrimOut - currentTrimIn),
                              });
                            }}
                          />
                        </div>
                      </>
                    );
                  })()}

                  <div className="flex justify-between text-[10px] text-zinc-400 bg-zinc-900 px-2 py-1 rounded">
                    <span>Thời lượng phân cảnh cắt:</span>
                    <span className="font-mono font-semibold text-emerald-400">
                      {(((activeSelectedClip.duration_ms || 3000)) / 1000).toFixed(1)}s
                    </span>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px] text-zinc-300">
                    <span>Thời lượng hiển thị ảnh:</span>
                    <span className="font-mono text-teal-400">
                      {((activeSelectedClip.duration_ms || 3000) / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <Slider
                    value={[activeSelectedClip.duration_ms || 3000]}
                    min={500}
                    max={15000}
                    step={500}
                    onValueChange={(val: number[]) => handleUpdateSelectedClip({ duration_ms: val[0] })}
                  />
                </div>
              )}

              {/* Chế độ Khung hình (Fit mode) */}
              <div className="space-y-1">
                <span className="text-[11px] text-zinc-300">Khớp khung 9:16:</span>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant={activeSelectedClip.fit === "cover" ? "secondary" : "ghost"}
                    onClick={() => handleUpdateSelectedClip({ fit: "cover" })}
                    className={`flex-1 h-6 text-[10px] ${activeSelectedClip.fit === "cover" ? "bg-zinc-700 text-white hover:bg-zinc-600" : "text-zinc-300 hover:bg-zinc-800 hover:text-white"}`}
                  >
                    Cover (Cắt phủ)
                  </Button>
                  <Button
                    size="sm"
                    variant={activeSelectedClip.fit === "contain" ? "secondary" : "ghost"}
                    onClick={() => handleUpdateSelectedClip({ fit: "contain" })}
                    className={`flex-1 h-6 text-[10px] ${activeSelectedClip.fit === "contain" ? "bg-zinc-700 text-white hover:bg-zinc-600" : "text-zinc-300 hover:bg-zinc-800 hover:text-white"}`}
                  >
                    Contain (Vừa khung)
                  </Button>
                </div>
              </div>

              {/* Thao tác xóa khỏi timeline */}
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleRemoveClip(activeSelectedClip.clip_id)}
                className="w-full h-6 text-[10px] mt-1"
              >
                <Trash2 className="size-3 mr-1" /> Xóa phân cảnh này
              </Button>
            </div>
          ) : selectedOverlay ? null : (
            <p className="text-[10px] text-zinc-500 italic text-center p-2 border border-dashed border-zinc-800 rounded">
              Bấm vào một phân cảnh ở Timeline dưới đáy để chỉnh sửa thuộc tính
            </p>
          )}

          {selectedOverlay && selectedOverlayIndex !== null && (
            <div className="p-2.5 rounded-lg border border-purple-500/40 bg-purple-950/20 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-purple-300 flex items-center gap-1">
                  <Layers className="size-3.5" /> Lớp diễn họa {selectedOverlayIndex + 1}
                </span>
                <Button
                  size="sm"
                  variant="destructive"
                  aria-label="Xóa lớp diễn họa"
                  onClick={() => {
                    setTimelineOverlays((current) => current.filter((_, index) => index !== selectedOverlayIndex));
                    setSelectedOverlayIndex(selectedOverlayIndex > 0 ? selectedOverlayIndex - 1 : null);
                  }}
                  className="size-6 p-0"
                >
                  <Trash2 className="size-3" />
                </Button>
              </div>
              <p className="text-[10px] text-zinc-400">Kéo lớp trên khung xem trước hoặc nhập giá trị để căn chỉnh chính xác.</p>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ["X", "x", 0, 1080 - selectedOverlay.width],
                  ["Y", "y", 0, 1920 - selectedOverlay.height],
                  ["Rộng", "width", 1, 1080 - selectedOverlay.x],
                  ["Cao", "height", 1, 1920 - selectedOverlay.y],
                ] as const).map(([label, field, min, max]) => (
                  <label key={field} className="space-y-1 text-[10px] text-zinc-400">
                    <span>{label} (px)</span>
                    <Input
                      type="number"
                      min={min}
                      max={max}
                      value={selectedOverlay[field]}
                      aria-label={`${label} lớp diễn họa`}
                      onChange={(event) => {
                        const value = event.currentTarget.valueAsNumber;
                        if (Number.isFinite(value)) handleUpdateSelectedOverlay({ [field]: value });
                      }}
                      className="h-7 bg-zinc-950 border-zinc-700 text-white"
                    />
                  </label>
                ))}
                <label className="space-y-1 text-[10px] text-zinc-400">
                  <span>Bắt đầu (giây)</span>
                  <Input
                    type="number"
                    min={0}
                    step={0.1}
                    value={(selectedOverlay.start_ms / 1000).toFixed(1)}
                    aria-label="Thời điểm bắt đầu lớp diễn họa"
                    onChange={(event) => {
                      const value = event.currentTarget.valueAsNumber;
                      if (Number.isFinite(value)) handleUpdateSelectedOverlay({ start_ms: value * 1000 });
                    }}
                    className="h-7 bg-zinc-950 border-zinc-700 text-white"
                  />
                </label>
                <label className="space-y-1 text-[10px] text-zinc-400">
                  <span>Thời lượng (giây)</span>
                  <Input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={(selectedOverlay.duration_ms / 1000).toFixed(1)}
                    aria-label="Thời lượng lớp diễn họa"
                    onChange={(event) => {
                      const value = event.currentTarget.valueAsNumber;
                      if (Number.isFinite(value)) handleUpdateSelectedOverlay({ duration_ms: value * 1000 });
                    }}
                    className="h-7 bg-zinc-950 border-zinc-700 text-white"
                  />
                </label>
              </div>
            </div>
          )}

          {/* Khử Logo Veo AI Chuyên Biệt */}
          <div className="p-2.5 rounded-lg border border-purple-500/30 bg-purple-950/20 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-purple-300 flex items-center gap-1.5">
                <Eraser className="size-3.5 text-purple-400" /> Khử Logo Veo AI
              </span>
            </div>
            <p className="text-[10px] text-zinc-400">
              Loại bỏ logo hình thoi và chữ Veo bằng toán học phân giải alpha ngược.
            </p>
            {selectedAssetId && (
              <Button
                size="sm"
                variant="outline"
                disabled={isCleaningWatermark}
                onClick={() => handleCleanWatermark()}
                className="w-full h-7 text-xs border-purple-500/50 text-purple-200 hover:bg-purple-900/30 gap-1"
              >
                {isCleaningWatermark ? (
                  <>
                    <RefreshCw className="size-3 animate-spin" /> Đang tẩy logo...
                  </>
                ) : (
                  <>
                    <Sparkles className="size-3 text-purple-400" /> Tẩy Logo Tư Liệu Đang Chọn
                  </>
                )}
              </Button>
            )}
            {cleanWatermarkMessage && (
              <p className="text-[10px] text-zinc-300 bg-zinc-900 p-1.5 rounded border border-zinc-800">
                {cleanWatermarkMessage}
              </p>
            )}
          </div>

          {/* Thành Phẩm Sau Kết Xuất (M-P5) */}
          {renderedTimelineAsset && (
            <div className="p-2.5 rounded-lg border border-emerald-500/40 bg-emerald-950/20 space-y-2 text-xs">
              <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                <CheckCircle2 className="size-4" />
                <span>Thành Phẩm Sẵn Sàng (MP4)</span>
              </div>
              <div className="text-[10px] font-mono text-zinc-300 space-y-0.5">
                
                <p>Dung lượng: {(renderedTimelineAsset.byte_size / (1024 * 1024)).toFixed(2)} MB</p>
                <p>Thời lượng: {((renderedTimelineAsset.duration_ms || 0) / 1000).toFixed(1)}s</p>
                <p>Chuẩn âm: -14 LUFS (EBU R128)</p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (renderedTimelineAsset.url) {
                    mediaStudioApi.downloadAsset(renderedTimelineAsset.url, renderedTimelineAsset.original_filename || "video.mp4")
                      .catch((error) => setRenderTimelineError(error.message || "Không thể tải video."));
                  }
                }}
                className="w-full h-7 text-xs border-emerald-500/50 text-emerald-300 hover:bg-emerald-900/30 gap-1"
              >
                <ExternalLink className="size-3" /> Tải về máy
              </Button>
            </div>
          )}

          {renderTimelineProgress && (
            <p className="text-[10px] text-teal-300 bg-teal-950/40 p-2 rounded border border-teal-800">
              {renderTimelineProgress}
            </p>
          )}

          {renderTimelineError && (
            <p className="text-[10px] text-red-300 bg-red-950/40 p-2 rounded border border-red-800">
              {renderTimelineError}
            </p>
          )}
        </div>
      </div>

      {/* 3. Timeline Đa Track Dưới Đáy (Bottom Timeline Multi-Track Editor M-P4) */}
      <div className="h-44 border-t border-zinc-800 bg-zinc-900/95 flex flex-col justify-between p-3 select-none">
        {/* Thanh Điều Khiển Timeline */}
        <div className="flex items-center justify-between text-xs pb-1.5 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="font-mono text-teal-400 font-bold">TIMELINE EDITOR</span>
            <span className="text-zinc-500 font-mono text-[11px]">30 FPS • 1080x1920 • Safe Zone</span>
          </div>

          <div className="flex items-center gap-2 text-zinc-400 text-xs">
            <span>Tổng thời lượng: <strong className="text-white font-mono">{totalDuration.toFixed(1)}s</strong></span>
          </div>
        </div>

        {/* Các lớp timeline hiện có */}
        <div className="flex-1 space-y-1.5 py-1.5 overflow-y-auto">
          {/* Track 1: Phân Cảnh (Video & Ảnh) */}
          <div className="flex items-center gap-2 h-7 text-xs">
            <span className="w-20 font-mono text-[10px] text-zinc-400 truncate flex items-center gap-1">
              <Film className="size-3 text-blue-400" /> Phân Cảnh
            </span>
            <div className="flex-1 h-full rounded bg-blue-950/40 border border-blue-500/30 relative flex items-center px-1 gap-1.5 overflow-x-auto">
              {timelineClips.length === 0 ? (
                <span className="text-[10px] text-zinc-500 italic pl-1">
                  Chưa có phân cảnh. Bấm dấu + tại thư viện tư liệu bên trái để thêm.
                </span>
              ) : (
                timelineClips.map((clip, idx) => (
                  <div
                    key={clip.clip_id}
                    onClick={() => {
                      setSelectedClipId(clip.clip_id);
                      const matchingAsset = assets.find((a) => a.id === clip.asset_id);
                      if (matchingAsset && matchingAsset.url) {
                        setPreviewSource({ url: matchingAsset.url, type: clip.media_type === "image" ? "image" : "video" });
                      }
                    }}
                    className={`h-5.5 px-2 rounded cursor-pointer flex items-center gap-1.5 text-[10px] font-mono shrink-0 border transition-all ${
                      selectedClipId === clip.clip_id
                        ? "bg-teal-600 text-white border-teal-400 font-bold"
                        : "bg-blue-900/60 text-blue-200 border-blue-500/40 hover:bg-blue-800/60"
                    }`}
                  >
                    <span>#{idx + 1} {clip.media_type === "image" ? "[Ảnh]" : "[Video]"}</span>
                    <span>{(clip.duration_ms / 1000).toFixed(1)}s</span>

                    {/* Điều khiển di chuyển thứ tự bằng nút (Keyboard accessible) */}
                    <div className="flex items-center gap-0.5 ml-1" onClick={(e) => e.stopPropagation()}>
                      {idx > 0 && (
                        <button
                          type="button"
                          onClick={() => handleMoveClip(idx, "up")}
                          className="hover:text-amber-300"
                          title="Chuyển lên trước"
                        >
                          <ChevronUp className="size-3" />
                        </button>
                      )}
                      {idx < timelineClips.length - 1 && (
                        <button
                          type="button"
                          onClick={() => handleMoveClip(idx, "down")}
                          className="hover:text-amber-300"
                          title="Chuyển ra sau"
                        >
                          <ChevronDown className="size-3" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleRemoveClip(clip.clip_id)}
                        className="hover:text-red-400 ml-0.5"
                        title="Xóa phân cảnh"
                      >
                        <Trash2 className="size-2.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {timelineOverlays.length > 0 && (
            <div className="flex items-center gap-2 h-6 text-xs">
              <span className="w-20 font-mono text-[10px] text-zinc-400 truncate flex items-center gap-1">
                <Layers className="size-3 text-purple-400" /> Diễn họa
              </span>
              <div className="flex-1 h-full rounded bg-purple-950/40 border border-purple-500/30 relative flex items-center px-1 gap-1.5 overflow-x-auto">
                {timelineOverlays.map((overlay, index) => {
                  const asset = assets.find((item) => item.id === overlay.asset_id);
                  return (
                    <button
                      key={`${overlay.asset_id}_${index}`}
                      type="button"
                      aria-pressed={selectedOverlayIndex === index}
                      onClick={() => setSelectedOverlayIndex(index)}
                      className={`h-5 px-2 rounded flex items-center gap-1.5 shrink-0 border text-[10px] font-mono transition-colors ${selectedOverlayIndex === index
                        ? "bg-purple-600 text-white border-purple-300"
                        : "bg-purple-900/60 text-purple-200 border-purple-500/40 hover:bg-purple-800/60"}`}
                    >
                      <span className="max-w-32 truncate">{asset?.original_filename || `Lớp ${index + 1}`}</span>
                      <span>{(overlay.start_ms / 1000).toFixed(1)}–{((overlay.start_ms + overlay.duration_ms) / 1000).toFixed(1)}s</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Track 2: Caption Track */}
          <div className="flex items-center gap-2 h-6 text-xs">
            <span className="w-20 font-mono text-[10px] text-zinc-400 truncate flex items-center gap-1">
              <Type className="size-3 text-amber-400" /> Phụ đề
            </span>
            <div className="flex-1 h-full rounded bg-amber-950/60 border border-amber-500/40 relative flex items-center px-2">
              <span className="text-[10px] text-amber-300 truncate font-mono">
                {captionsForSave.length ? `${captionsForSave.length} câu phụ đề · ${captionFontSize}px · Vùng an toàn` : "Chưa có phụ đề."}
              </span>
            </div>
          </div>

          {/* Track 3: Voiceover Track */}
          <div className="flex items-center gap-2 h-6 text-xs">
            <span className="w-20 font-mono text-[10px] text-zinc-400 truncate flex items-center gap-1">
              <Mic className="size-3 text-teal-400" /> Giọng Đọc
            </span>
            <div className="flex-1 h-full rounded bg-teal-950/60 border border-teal-500/40 relative flex items-center px-2">
              <span className="text-[10px] text-teal-300 truncate font-mono">
                {timelineVoice ? `Tệp giọng đọc: ${timelineVoice.asset_id}` : "Chưa có giọng đọc."}
              </span>
            </div>
          </div>

          {/* Track 4: Music Track */}
          <div className="flex items-center gap-2 h-6 text-xs">
            <span className="w-20 font-mono text-[10px] text-zinc-400 truncate flex items-center gap-1">
              <Music className="size-3 text-emerald-400" /> Nhạc Nền
            </span>
            <div className="flex-1 h-full rounded bg-emerald-950/60 border border-emerald-500/40 relative flex items-center px-2">
              <span className="text-[10px] text-emerald-300 truncate font-mono">
                {timelineMusic ? `Nhạc nền · Tự động giảm ${musicAttenuationDb} dB` : "Chưa có nhạc nền."}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
