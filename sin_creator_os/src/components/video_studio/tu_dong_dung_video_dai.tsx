"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileVideo2, Upload, WandSparkles } from "lucide-react";

import { type MediaAssetResponse, mediaStudioApi } from "@/lib/api/media-studio-api";
import { docManifestDungTuDong, type ManifestDungTuDong } from "@/lib/video_studio/phan_tich_manifest_dung_tu_dong";

interface TuDongDungVideoDaiProps {
  projectId: string;
  assets: MediaAssetResponse[];
  onAssetsChanged: () => void;
  initialOutputAssetId?: string | null;
}

const TERMINAL_STATES = new Set(["SUCCEEDED", "FAILED", "NEEDS_RECONCILIATION", "CANCELLED", "EXPIRED"]);

const nhanTrangThaiDienHoa = (state: string) => {
  if (state === "SUCCEEDED") return "Đã tạo";
  if (state === "BLOCKED_FLOW_PROFILE" || state === "BLOCKED_FLOW_LOGIN") return "Cần đăng nhập Flow";
  if (state === "BLOCKED_FLOW_QUOTA") return "Flow hết hạn mức";
  if (state === "BLOCKED_FLOW_SETUP") return "Flow cần thiết lập";
  if (state === "FAILED" || state === "MISSING") return "Cần rà soát";
  if (state === "CANCELLED") return "Đã hủy";
  if (state === "EXPIRED") return "Đã hết thời gian";
  return "Đang xử lý";
};

export function TuDongDungVideoDai({ projectId, assets, onAssetsChanged, initialOutputAssetId }: TuDongDungVideoDaiProps) {
  const videos = assets.filter(
    (asset) => asset.mime_detected.startsWith("video/") && asset.source_product === "UPLOAD" && !asset.parent_asset_id,
  );
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadSessionId, setUploadSessionId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ loaded: 0, total: 0 });
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState("");
  const [outputs, setOutputs] = useState<MediaAssetResponse[]>([]);
  const [manifest, setManifest] = useState<ManifestDungTuDong | null>(null);
  const [previewAssetId, setPreviewAssetId] = useState<string | null>(null);
  const [requestedPreviewAssetId, setRequestedPreviewAssetId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewCaptionUrl, setPreviewCaptionUrl] = useState<string | null>(null);
  const [loadingPreviewId, setLoadingPreviewId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [reviewingAssetId, setReviewingAssetId] = useState<string | null>(null);
  const persistedOutputs = useMemo(() => {
    const direct = assets.filter((asset) => asset.source_product === "AUTO_EDIT" && (!sourceAssetId || asset.parent_asset_id === sourceAssetId));
    const videoIds = new Set(direct.filter((asset) => asset.mime_detected.startsWith("video/")).map((asset) => asset.id));
    return [...direct, ...assets.filter((asset) => asset.source_product === "AUTO_EDIT" && videoIds.has(asset.parent_asset_id ?? ""))];
  }, [assets, sourceAssetId]);
  const visibleOutputs = outputs.length > 0
    ? outputs
    : (starting || (jobId !== null && !TERMINAL_STATES.has(jobState)) ? [] : persistedOutputs);
  const visibleVideoOutputs = visibleOutputs.filter((asset) => asset.mime_detected.startsWith("video/"));
  const manifestAsset = visibleOutputs.find((item) => item.mime_detected === "application/json");


  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    return () => {
      if (previewCaptionUrl) URL.revokeObjectURL(previewCaptionUrl);
    };
  }, [previewCaptionUrl]);

  useEffect(() => {
    const asset = visibleOutputs.find((item) => item.mime_detected === "application/json");
    if (!asset?.url) {
      setManifest(null);
      return;
    }
    let active = true;
    void mediaStudioApi.getAssetText(asset.url).then((text) => {
      if (active) setManifest(docManifestDungTuDong(text));
    }).catch((cause: unknown) => {
      if (active) {
        setManifest(null);
        console.warn("Không đọc được biên bản dựng video:", cause);
      }
    });
    return () => { active = false; };
  }, [visibleOutputs]);

  useEffect(() => {
    if (!jobId || TERMINAL_STATES.has(jobState)) return;
    let checking = false;
    const poll = async () => {
      if (checking) return;
      checking = true;
      try {
        const job = await mediaStudioApi.getAutoEditJob(jobId);
        setJobState(job.state);
        if (job.state === "SUCCEEDED") {
          const results = await Promise.all((job.output_asset_ids ?? []).map((id) => mediaStudioApi.getAsset(id)));
          setOutputs(results);
          onAssetsChanged();
        } else if (TERMINAL_STATES.has(job.state)) {
          setError(job.error_message ?? job.error_code ?? "Tác vụ dựng video không hoàn tất.");
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể kiểm tra trạng thái tác vụ.");
      } finally {
        checking = false;
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2500);
    return () => window.clearInterval(timer);
  }, [jobId, jobState, onAssetsChanged]);

  const start = async (manifestAssetId?: string, originalSourceId = sourceAssetId) => {
    if (!originalSourceId || starting || (jobId !== null && !TERMINAL_STATES.has(jobState))) return;
    setSourceAssetId(originalSourceId);
    setStarting(true);
    setError(null);
    setOutputs([]);
    setPreviewAssetId(null);
    setPreviewUrl(null);
    setPreviewCaptionUrl(null);
    setJobId(null);
    setJobState("");
    try {
      const job = await mediaStudioApi.startAutoEditVideo(projectId, originalSourceId, manifestAssetId);
      setJobId(job.job_id);
      setJobState(job.state);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể gửi video cho bộ dựng tự động.");
    } finally {
      setStarting(false);
    }
  };

  const uploadVideo = async () => {
    if (!uploadFile || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const asset = await mediaStudioApi.uploadVideoInChunks({
        file: uploadFile,
        project_id: projectId,
        resume_session_id: uploadSessionId ?? undefined,
        onSessionId: setUploadSessionId,
        onProgress: (loaded, total) => setUploadProgress({ loaded, total }),
      });
      setSourceAssetId(asset.id);
      setUploadSessionId(null);
      setUploadFile(null);
      onAssetsChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải video lên dự án.");
    } finally {
      setUploading(false);
    }
  };

  const preview = useCallback(async (asset: MediaAssetResponse) => {
    if (!asset.url) return;
    setLoadingPreviewId(asset.id);
    setPreviewCaptionUrl(null);
    setError(null);
    try {
      setPreviewUrl(await mediaStudioApi.createAssetObjectUrl(asset.url));
      setPreviewAssetId(asset.id);
      const subtitle = visibleOutputs.find(
        (item) => item.parent_asset_id === asset.id && item.mime_detected === "application/x-subrip",
      );
      if (subtitle?.url) {
        const srt = await mediaStudioApi.getAssetText(subtitle.url);
        const vtt = `WEBVTT\n\n${srt.replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2")}`;
        setPreviewCaptionUrl(URL.createObjectURL(new Blob([vtt], { type: "text/vtt" })));
      } else {
        setPreviewCaptionUrl(null);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải bản xem trước.");
    } finally {
      setLoadingPreviewId(null);
    }
  }, [visibleOutputs]);

  useEffect(() => {
    if (!initialOutputAssetId || requestedPreviewAssetId === initialOutputAssetId || loadingPreviewId) return;
    const asset = visibleOutputs.find((item) => item.id === initialOutputAssetId && item.mime_detected.startsWith("video/"));
    if (asset) {
      setRequestedPreviewAssetId(initialOutputAssetId);
      void preview(asset);
    }
  }, [initialOutputAssetId, loadingPreviewId, preview, requestedPreviewAssetId, visibleOutputs]);

  const handleReview = async (asset: MediaAssetResponse, decision: "APPROVE" | "REJECT") => {
    setReviewingAssetId(asset.id);
    setError(null);
    try {
      const reviewed = await mediaStudioApi.reviewAsset(asset.id, decision);
      setOutputs((current) => (current.length > 0 ? current : visibleOutputs).map((item) => item.id === reviewed.id ? reviewed : item));
      onAssetsChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể ghi nhận kết quả rà soát.");
    } finally {
      setReviewingAssetId(null);
    }
  };

  let buttonLabel = "Tự chọn đoạn và dựng clip";
  if (starting) buttonLabel = "Đang gửi tác vụ";
  else if (jobId && !TERMINAL_STATES.has(jobState)) buttonLabel = jobState === "WAITING_FOR_FLOW" ? "Đang tạo diễn hoạ giấy gấp" : "Đang dựng video";

  const waveform = manifest?.waveform_peaks ?? [];
  const waveformBars = waveform.length > 180
    ? Array.from({ length: 180 }, (_, index) => Math.max(...waveform.slice(Math.floor(index * waveform.length / 180), Math.ceil((index + 1) * waveform.length / 180))))
    : waveform;
  const sourceDurationMs = waveform.length * 100;
  const pauseBuckets = new Set<number>();
  for (const [start, end] of manifest?.pause_candidates ?? []) {
    if (sourceDurationMs > 0) {
      const first = Math.floor(start / sourceDurationMs * waveformBars.length);
      const last = Math.ceil(end / sourceDurationMs * waveformBars.length);
      for (let index = first; index < last && index < waveformBars.length; index += 1) pauseBuckets.add(index);
    }
  }
  const formatMs = (milliseconds: number) => `${Math.floor(milliseconds / 60000)}:${String(Math.floor(milliseconds / 1000) % 60).padStart(2, "0")}`;

  return (
    <section
      className="space-y-6"
      aria-labelledby="auto-edit-title"
    >
      <div>
        <h3 id="auto-edit-title" className="text-lg font-semibold text-foreground">
          Tạo clip tự động
        </h3>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          Tải một lần quay có nhiều kịch bản. AI tìm điểm nghỉ, so sánh các take, bỏ đoạn thừa và đề xuất diễn họa phù hợp.
          Mỗi clip đầu ra đều có bản xem trước để nhân viên duyệt.
        </p>
      </div>

      <div className="grid gap-5 rounded-xl border border-dashed bg-muted/30 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.72fr)] lg:items-center">
        <div className="flex items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Upload className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="font-medium">Tải video quay lên</p>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">Hỗ trợ video dung lượng lớn. Nếu kết nối ngắt, chọn lại đúng tệp để tiếp tục.</p>
          </div>
        </div>
        <div className="grid gap-2 text-sm font-medium text-foreground">
          <span>Tệp video</span>
          <input
            id="auto-edit-upload"
            type="file"
            aria-label="Chọn video từ thiết bị"
            accept="video/*"
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setUploadFile(file);
              event.currentTarget.value = "";
              setUploadSessionId(null);
              setUploadProgress({ loaded: 0, total: file?.size ?? 0 });
              setError(null);
            }}
            className="peer sr-only"
          />
          <label
            htmlFor="auto-edit-upload"
            className="inline-flex min-h-10 cursor-pointer items-center justify-center rounded-md border border-input bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-ring"
          >
            Chọn video
          </label>
        </div>
        {uploadFile && (
          <div className="space-y-1 text-sm text-muted-foreground lg:col-span-2">
            <p>{uploadFile.name} · {(uploadFile.size / (1024 ** 3)).toFixed(2)} GiB</p>
            {uploadProgress.total > 0 && <progress className="h-2 w-full accent-primary" value={uploadProgress.loaded} max={uploadProgress.total} aria-label="Tiến độ tải video" />}
            {uploading && <p role="status" aria-live="polite">Đã tải {(uploadProgress.loaded / (1024 ** 3)).toFixed(2)} / {(uploadProgress.total / (1024 ** 3)).toFixed(2)} GiB</p>}
          </div>
        )}
        <button
          type="button"
          onClick={() => void uploadVideo()}
          disabled={!uploadFile || uploading}
          className="min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 lg:col-span-2"
        >
          {uploading ? "Đang tải video theo từng phần" : "Tải hoặc tiếp tục tải video"}
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(17rem,0.72fr)] lg:items-end">
      <label className="grid gap-2 text-sm font-medium text-foreground" htmlFor="auto-edit-source">
        Video nguồn
        <select
          id="auto-edit-source"
          value={sourceAssetId}
          onChange={(event) => {
            setSourceAssetId(event.target.value);
            setOutputs([]);
            setJobId(null);
            setJobState("");
            setPreviewAssetId(null);
            setPreviewUrl(null);
            setPreviewCaptionUrl(null);
            setError(null);
          }}
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Chọn video đã tải lên</option>
          {videos.map((asset) => (
            <option key={asset.id} value={asset.id}>
              {asset.original_filename || asset.id}{" "}
              {asset.duration_ms ? `(${Math.round(asset.duration_ms / 1000)} giây)` : ""}
            </option>
          ))}
        </select>
      </label>

      {videos.length === 0 && (
        <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          Tải video nguồn lên ở tab Tư Liệu trước khi chạy.
        </p>
      )}

      <button
        type="button"
        onClick={() => void start()}
        disabled={!sourceAssetId || starting || (!!jobId && !TERMINAL_STATES.has(jobState))}
        className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 lg:col-span-2"
      >
        {!starting && !jobId && <WandSparkles className="size-4" aria-hidden="true" />}
        {buttonLabel}
      </button>
      </div>

      {jobId && (
        <p
          className="rounded-md border bg-muted/40 p-3 text-sm text-foreground"
          role="status"
          aria-live="polite"
        >
          Tác vụ {jobId.slice(0, 8)}: {jobState === "WAITING_FOR_FLOW" ? "đang tạo diễn hoạ giấy gấp" : jobState}. Whisper, LLM, Flow và FFmpeg xử lý theo từng giai đoạn.
        </p>
      )}

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {visibleVideoOutputs.length > 0 && (
        <div className="space-y-3 border-t pt-5">
          <div className="flex items-start gap-3">
            <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
              <FileVideo2 className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h4 className="font-semibold text-base text-foreground">Clip đã dựng</h4>
              <p className="mt-1 text-sm text-muted-foreground">Xem, duyệt hoặc yêu cầu chỉnh sửa từng clip ngay tại đây.</p>
            </div>
          </div>
          {manifestAsset && manifest?.replay_source_asset_id && videos.some((video) => video.id === manifest.replay_source_asset_id) && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => { if (manifest.replay_source_asset_id) void start(manifestAsset.id, manifest.replay_source_asset_id); }}
                disabled={starting || (!!jobId && !TERMINAL_STATES.has(jobState))}
                className="inline-flex min-h-10 items-center justify-center rounded-md border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                Dựng lại bố cục
              </button>
              <p className="text-sm text-muted-foreground">Giữ kịch bản và các cảnh đã tạo; AI sắp xếp lại cách trình bày.</p>
            </div>
          )}
          {manifest && (
            <div className="space-y-3 rounded-lg border bg-card p-4">
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Dạng sóng video nguồn. Vùng màu vàng là khoảng nghỉ ứng viên.</p>
                <div className="flex h-16 items-center gap-px overflow-hidden rounded-md bg-muted px-1" role="img" aria-label="Dạng sóng âm thanh và mốc nghỉ từ video nguồn">
                  {waveformBars.map((peak, index) => (
                    <span
                      key={`wave-${index}`}
                      className={`min-w-0 flex-1 rounded-sm ${pauseBuckets.has(index) ? "bg-amber-400" : "bg-primary/70"}`}
                      style={{ height: `${Math.max(3, peak)}%` }}
                    />
                  ))}
                </div>
              </div>
              {manifest.flow_generated_visuals.length > 0 && (
                <div className="space-y-1 rounded-md border bg-muted/40 p-3" aria-label="Trạng thái diễn họa origami">
                  <p className="text-sm font-medium text-foreground">Diễn họa giấy gấp</p>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {manifest.flow_generated_visuals.map((visual) => (
                      <li key={`${visual.target_clip_id ?? "project"}-${visual.job_id ?? visual.state}`}>
                        {visual.target_clip_id ? `Clip ${visual.target_clip_id}: ` : "Toàn dự án: "}{nhanTrangThaiDienHoa(visual.state)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <ol className="space-y-2" aria-label="Các kịch bản được tách">
                {manifest.clips.map((clip, index) => (
                  <li key={clip.clip_id} className="rounded-md border p-3 text-sm text-muted-foreground">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong className="text-foreground">{index + 1}. {clip.title}</strong>
                      <span className={clip.needs_review ? "text-amber-600 dark:text-amber-300" : "text-success"}>
                        {clip.needs_review ? "Cần rà soát" : "Take đã chọn"}
                      </span>
                    </div>
                    <p className="mt-1">Nguồn {formatMs(clip.source_start_ms)}–{formatMs(clip.source_end_ms)}; take {clip.selected_take_id}</p>
                    <p className="mt-1">Lý do: {clip.selection_reason}</p>
                    {clip.visual_actions.length > 0 && (
                    <ul className="mt-2 space-y-1 text-sm text-muted-foreground" aria-label="Các lớp diễn hoạ được chọn">
                        {clip.visual_actions.map((action) => (
                          <li key={`${action.asset_id}-${action.start_ms}`}>
                            {action.mode === "OVERLAY" ? "Lớp phủ hoạt ảnh" : action.mode === "SPEAKER_PIP" ? "Người nói trong khung nhỏ" : "Cảnh diễn hoạ xen vào"} {formatMs(action.start_ms)}–{formatMs(action.end_ms)}: {action.reason}
                          </li>
                        ))}
                      </ul>
                    )}
                    {clip.take_options.length > 1 && (
                      <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                        {clip.take_options.filter((take) => take.take_id !== clip.selected_take_id).map((take) => (
                          <li key={take.take_id}>Take khác {take.take_id} ({formatMs(take.start_ms)}–{formatMs(take.end_ms)}): {take.reason}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
          {visibleVideoOutputs.map((asset) => (
            <div
              key={asset.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-3"
            >
              <div className="min-w-0 space-y-1">
                <span className="block truncate text-sm font-medium text-foreground">{asset.original_filename ?? asset.id}</span>
                {asset.mime_detected.startsWith("video/") && (
                  <span className="block text-xs text-muted-foreground" aria-live="polite">
                    Trạng thái: {asset.approval_state === "APPROVED" ? "Đã duyệt" : asset.approval_state === "REJECTED" ? "Cần chỉnh sửa" : "Chờ nhân viên rà soát"}
                  </span>
                )}
              </div>
              {asset.url && (
                <div className="flex shrink-0 flex-wrap justify-end gap-1">
                  {asset.mime_detected.startsWith("video/") && (
                    <>
                      <button
                        type="button"
                        onClick={() => void preview(asset)}
                        disabled={loadingPreviewId !== null}
                        className="rounded px-2 py-1 font-medium text-primary text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                      >
                        {loadingPreviewId === asset.id ? "Đang tải" : "Xem"}
                      </button>
                      {asset.approval_state === "UNREVIEWED" && (
                        <>
                          <button
                            type="button"
                            onClick={() => void handleReview(asset, "APPROVE")}
                            disabled={reviewingAssetId !== null}
                            className="rounded px-2 py-1 font-medium text-success text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                          >
                            {reviewingAssetId === asset.id ? "Đang lưu" : "Duyệt clip"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleReview(asset, "REJECT")}
                            disabled={reviewingAssetId !== null}
                            className="rounded px-2 py-1 font-medium text-amber-600 text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-amber-300 disabled:opacity-50"
                          >
                            Yêu cầu chỉnh sửa
                          </button>
                        </>
                      )}
                    </>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const url = asset.url;
                      if (url) {
                        void mediaStudioApi.downloadAsset(url, asset.original_filename ?? "video.mp4").catch((cause: unknown) => {
                          setError(cause instanceof Error ? cause.message : "Không thể tải clip xuống.");
                        });
                      }
                    }}
                    className="rounded px-2 py-1 font-medium text-primary text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    Tải xuống
                  </button>
                </div>
              )}
            </div>
          ))}
          {previewUrl && previewAssetId && (
            /* biome-ignore lint/a11y/useMediaCaption: Captions are burned into the rendered MP4. */
            <video
              key={previewAssetId}
              className="w-full rounded-lg border bg-black"
              controls
              playsInline
              preload="metadata"
              src={previewUrl}
              aria-label="Xem trước clip dựng tự động"
            >
              {previewCaptionUrl && (
                <track kind="captions" srcLang="vi" label="Tiếng Việt" src={previewCaptionUrl} />
              )}
            </video>
          )}
          <p className="text-amber-300 text-xs">
            Đầu ra chưa được duyệt để đăng. Nhân viên có thể rà soát và yêu cầu chỉnh sửa từng clip tại đây.
          </p>
        </div>
      )}
    </section>
  );
}
