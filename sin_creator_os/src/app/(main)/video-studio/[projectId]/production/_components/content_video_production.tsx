"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AuthApi } from "@/lib/api/auth-api";
import { voiceStudioApi } from "@/lib/api/voice-studio-api";
import { FlowSessionManager } from "@/components/creator/flow-session-manager";
import { ArrowLeft, Check, LoaderCircle, Play, RefreshCw, Save, Sparkles } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { mediaStudioApi, MediaAssetResponse } from "@/lib/api/media-studio-api";
import { contentVideoApi, ContentVideoApiError, ContentVideoPlan, ContentVideoRun } from "@/lib/api/content-video-api";
import { randomUuid } from "@/lib/utils";
import { ShotActionDetails, ShotKindBadges, StoryboardBrief } from "./storyboard_details";

const ACTIVE_RUNS = new Set(["QUEUED", "RUNNING", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_SETUP", "BLOCKED_FLOW_QUOTA"]);

export default function ContentVideoProduction({ projectId, planId, runId, startNew }: { projectId: string; planId?: string; runId?: string; startNew?: boolean }) {
  const router = useRouter();
  const directCreation = ["WORKSPACE_OWNER", "PLATFORM_OWNER"].includes(AuthApi.getCurrentUser()?.role || "");
  const [ttsReady, setTtsReady] = React.useState(false);
  const [flowProfileId, setFlowProfileId] = React.useState<string | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    const refresh = () => voiceStudioApi.getCapabilities().then((value) => {
      if (!cancelled) setTtsReady(value.providers.VIE_NEU_V3_TURBO?.state === "READY" && value.worker.state === "READY");
    }).catch(() => { if (!cancelled) setTtsReady(false); });
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 15000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);
  const [content, setContent] = React.useState("");
  const [duration, setDuration] = React.useState(60);
  const [aspectRatio, setAspectRatio] = React.useState<"9:16" | "16:9">("9:16");
  const [plan, setPlan] = React.useState<ContentVideoPlan | null>(null);
  const [storyboardDraft, setStoryboardDraft] = React.useState<ContentVideoPlan["storyboard"] | null>(null);
  const [editingContent, setEditingContent] = React.useState(false);
  const [editingStoryboard, setEditingStoryboard] = React.useState(false);
  const [run, setRun] = React.useState<ContentVideoRun | null>(null);
  const [loadingHistory, setLoadingHistory] = React.useState(!planId && !startNew);
  const [finalUrl, setFinalUrl] = React.useState<string | null>(null);
  const [previewError, setPreviewError] = React.useState(false);
  const [exportUrl, setExportUrl] = React.useState<string | null>(null);
  const [projectAssets, setProjectAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceAssets, setVoiceAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceSource, setVoiceSource] = React.useState<"NONE" | "UPLOAD" | "TTS">("NONE");
  const [includeSubtitles, setIncludeSubtitles] = React.useState(true);
  const [voiceAssetId, setVoiceAssetId] = React.useState("");
  const [ttsProvider, setTtsProvider] = React.useState<"GWEN_TTS" | "VIE_NEU_V3_TURBO">("VIE_NEU_V3_TURBO");
  const [ttsVoiceId, setTtsVoiceId] = React.useState("Hải Đăng");
  const [ttsReferenceAssetId, setTtsReferenceAssetId] = React.useState("");
  const [ttsReferenceText, setTtsReferenceText] = React.useState("");
  const [voiceCloneConsent, setVoiceCloneConsent] = React.useState(false);
  const [reconcileAssetId, setReconcileAssetId] = React.useState("");
  const [reconcileReason, setReconcileReason] = React.useState("");
  const [confirmedClipMatch, setConfirmedClipMatch] = React.useState(false);
  const [confirmedNoFlowClip, setConfirmedNoFlowClip] = React.useState(false);
  const [newFlowProject, setNewFlowProject] = React.useState(false);
  const idempotencyKey = React.useRef<string | null>(null);
  const retryIdempotency = React.useRef<{ signature: string; key: string } | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [expandedShotIds, setExpandedShotIds] = React.useState<string[]>([]);
  const contentBytes = new TextEncoder().encode(content).length;
  const activeFlowStep = editingContent ? 1 : editingStoryboard ? 2 : run?.status === "COMPLETED" ? 4 : plan?.status === "APPROVED" || run ? 3 : plan ? 2 : 1;
  const editableStoryboard = storyboardDraft || plan?.storyboard || null;
  const hasUiScenes = !!editableStoryboard?.shots.some((shot) => shot.shot_kind === "UI_SIM");
  const storyboardDirty = !!plan && !!storyboardDraft && JSON.stringify(storyboardDraft) !== JSON.stringify(plan.storyboard);
  const sourceUnchanged = !!plan && content.trim() === plan.source_content && duration === plan.target_duration_seconds && aspectRatio === plan.style_snapshot.aspect_ratio;
  const firstUnfinishedShot = run?.steps.find((step) => step.state !== "SUCCEEDED");
  const canEditPreviousStep = !run || !["QUEUED", "RUNNING"].includes(run.status);
  const canRetryRun = !!run && ["COMPLETED", "FAILED", "FAILED_QC", "BLOCKED_FLOW_SETUP", "NEEDS_RECONCILIATION"].includes(run.status);
  const flowProjectUnavailable = run?.status === "BLOCKED_FLOW_SETUP" && run.error_code === "FLOW_REQUEST_NOT_SUBMITTED";
  const runStatusLabel: Record<string, string> = { QUEUED: "Đang chờ", RUNNING: "Đang tạo", COMPLETED: "Hoàn tất", FAILED: "Thất bại", FAILED_QC: "QC chưa đạt", BLOCKED_FLOW_LOGIN: "Cần đăng nhập Flow", BLOCKED_FLOW_SETUP: "Flow cần xử lý", BLOCKED_FLOW_QUOTA: "Flow đã hết hạn mức", NEEDS_RECONCILIATION: "Cần đối soát" };
  const shotStatusLabel: Record<string, string> = { READY: "Chưa tạo", QUEUED: "Đang chờ", RUNNING: "Đang tạo", SUBMITTING: "Đang gửi Flow", SUCCEEDED: "Đã tạo", FAILED: "Thất bại", NEEDS_RECONCILIATION: "Cần đối soát" };
  const expandedStoryboardShotIds = plan?.status === "DRAFT" || editingStoryboard ? editableStoryboard?.shots.map((shot) => shot.shot_id) || [] : expandedShotIds;

  const showError = (err: unknown, fallback: string) => {
    setError(err instanceof Error ? err.message : fallback);
    setErrorCode(err instanceof ContentVideoApiError ? err.code || null : null);
  };

  const reloadPlan = React.useCallback(async () => {
    if (!planId) return;
    try { const next = await contentVideoApi.getPlan(projectId, planId); setPlan(next); setStoryboardDraft(null); }
    catch (err) { showError(err, "Không tải được storyboard."); }
  }, [planId, projectId]);

  React.useEffect(() => {
    if (planId || startNew) {
      setLoadingHistory(false);
      void reloadPlan();
      if (planId && !runId && !startNew) {
        void contentVideoApi.getLatestHistory(projectId).then(({ plan: latestPlan, run: latestRun }) => {
          setRun(latestPlan?.id === planId ? latestRun : null);
        }).catch((err) => showError(err, "Không tải được trạng thái run mới nhất."));
      }
      return;
    }
    setLoadingHistory(true);
    void contentVideoApi.getLatestHistory(projectId).then(({ plan: latestPlan, run: latestRun }) => {
      if (!latestPlan) return;
      setPlan(latestPlan);
      setStoryboardDraft(null);
      setRun(latestRun);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(latestPlan.id)}${latestRun ? `&run=${encodeURIComponent(latestRun.id)}` : ""}`);
    }).catch((err) => showError(err, "Không tải được video đã tạo trong dự án.")).finally(() => setLoadingHistory(false));
  }, [planId, projectId, reloadPlan, router, runId, startNew]);
  React.useEffect(() => {
    void mediaStudioApi.listAssets({ project_id: projectId }).then((assets) => {
      setProjectAssets(assets);
      setVoiceAssets(assets.filter((asset) => asset.mime_detected.startsWith("audio/")));
    }).catch((err) => setError(err.message));
  }, [projectId]);
  React.useEffect(() => {
    if (runId) void contentVideoApi.getRun(projectId, runId).then(setRun).catch((err) => setError(err.message));
  }, [projectId, runId]);
  React.useEffect(() => {
    if (!run || !ACTIVE_RUNS.has(run.status)) return;
    const timer = window.setInterval(() => {
      void contentVideoApi.getRun(projectId, run.id).then(setRun).catch((err) => setError(err.message));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [projectId, run]);
  React.useEffect(() => {
    if (!run?.final_asset_id) return;
    let cancelled = false;
    let playbackUrl: string | null = null;
    void mediaStudioApi.listAssets({ project_id: projectId }).then(async (assets) => {
      const finalAsset = assets.find((asset) => asset.id === run.final_asset_id);
      const nextPlaybackUrl = finalAsset?.url ? await mediaStudioApi.createAssetObjectUrl(finalAsset.url) : null;
      if (cancelled) { if (nextPlaybackUrl) URL.revokeObjectURL(nextPlaybackUrl); return; }
      playbackUrl = nextPlaybackUrl;
      setProjectAssets(assets);
      setFinalUrl(nextPlaybackUrl);
      setExportUrl(assets.find((asset) => asset.id === run.qc_report?.export_asset_id)?.url || null);
    }).catch((err) => { if (!cancelled) showError(err, "Không tải được video đã ghép."); });
    return () => { cancelled = true; if (playbackUrl) URL.revokeObjectURL(playbackUrl); };
  }, [projectId, run?.final_asset_id, run?.qc_report?.export_asset_id]);
  React.useEffect(() => { setPreviewError(false); }, [finalUrl, run?.id]);
  React.useEffect(() => {
    if (run?.status !== "NEEDS_RECONCILIATION") return;
    void mediaStudioApi.listAssets({ project_id: projectId }).then(setProjectAssets);
  }, [projectId, run?.status]);

  const createPlan = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null); setErrorCode(null);
    try {
      const next = await contentVideoApi.createPlan(projectId, content, duration, aspectRatio);
      setPlan(next);
      setStoryboardDraft(null);
      setEditingContent(false);
      setEditingStoryboard(false);
      setRun(null);
      setFinalUrl(null);
      setExportUrl(null);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(next.id)}`);
    } catch (err) { showError(err, "Không tạo được storyboard."); }
    finally { setBusy(false); }
  };

  const approve = async () => {
    if (!plan) return;
    setBusy(true); setError(null); setErrorCode(null);
    try { setPlan(await contentVideoApi.approvePlan(projectId, plan.id)); setExpandedShotIds([]); }
    catch (err) { showError(err, "Không duyệt được storyboard."); }
    finally { setBusy(false); }
  };

  const saveStoryboard = async () => {
    if (!plan || !editableStoryboard || !storyboardDirty) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      const storyboard = { ...editableStoryboard, narration: editableStoryboard.shots.map((shot) => shot.narration.trim()).join(" ") };
      const saved = await contentVideoApi.updatePlan(projectId, plan.id, storyboard);
      setPlan(saved);
      setStoryboardDraft(null);
      setEditingStoryboard(false);
      setRun(null);
      setFinalUrl(null);
      setExportUrl(null);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(saved.id)}`);
    } catch (err) { showError(err, "Không lưu được nội dung storyboard."); }
    finally { setBusy(false); }
  };

  const startRun = async () => {
    if (!plan) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      idempotencyKey.current ||= `content-video-${plan.id}-${randomUuid()}`;
      const created = await contentVideoApi.createRun(projectId, plan.id, {
        source: voiceSource,
        assetId: voiceAssetId || null,
        provider: ttsProvider,
        voiceId: ttsVoiceId.trim() || undefined,
        referenceAssetId: ttsReferenceAssetId || undefined,
        referenceText: ttsReferenceText.trim() || undefined,
        consent: voiceCloneConsent,
        includeSubtitles,
      }, idempotencyKey.current, flowProfileId);
      idempotencyKey.current = null;
      setConfirmedNoFlowClip(false);
      setRun(created);
      setPlan({ ...plan, status: "APPROVED" });
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(plan.id)}&run=${encodeURIComponent(created.id)}`);
    }
    catch (err) { showError(err, "Không khởi chạy được video."); }
    finally { setBusy(false); }
  };

  const retryShots = async (shotIds: string[], inNewFlowProject = false) => {
    if (!plan || !run || (run.status === "NEEDS_RECONCILIATION" && !confirmedNoFlowClip)) return;
    setBusy(true); setError(null); setErrorCode(null);
    const signature = JSON.stringify([run.id, shotIds, inNewFlowProject, confirmedNoFlowClip]);
    if (retryIdempotency.current?.signature !== signature) {
      retryIdempotency.current = { signature, key: `content-video-retry-${randomUuid()}` };
    }
    try {
      const created = await contentVideoApi.retryRun(projectId, run.id, {
        shotIds,
        newFlowProject: inNewFlowProject,
        confirmNoFlowClip: confirmedNoFlowClip,
        idempotencyKey: retryIdempotency.current.key,
      });
      retryIdempotency.current = null;
      setConfirmedNoFlowClip(false);
      setNewFlowProject(false);
      setFinalUrl(null);
      setExportUrl(null);
      setRun(created);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(plan.id)}&run=${encodeURIComponent(created.id)}`);
    } catch (err) { showError(err, "Không tạo lại được shot."); }
    finally { setBusy(false); }
  };

  const editSource = () => {
    if (!plan) return;
    setContent(plan.source_content);
    setDuration(plan.target_duration_seconds);
    setAspectRatio(plan.style_snapshot.aspect_ratio);
    setEditingContent(true);
    setEditingStoryboard(false);
    setStoryboardDraft(null);
  };

  const cancelEditSource = () => {
    if (plan) {
      setContent(plan.source_content);
      setDuration(plan.target_duration_seconds);
      setAspectRatio(plan.style_snapshot.aspect_ratio);
    }
    setEditingContent(false);
  };

  const editStoryboard = () => {
    if (!plan) return;
    setStoryboardDraft(plan.storyboard);
    setExpandedShotIds(plan.storyboard.shots.map((shot) => shot.shot_id));
    setEditingStoryboard(true);
    setEditingContent(false);
  };

  const uploadVoice = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      const asset = await mediaStudioApi.uploadAsset({ file, project_id: projectId, expected_category: "audio" });
      setVoiceAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)]);
      setVoiceAssetId(asset.id);
      setTtsReferenceAssetId(asset.id);
      setVoiceCloneConsent(false);
      idempotencyKey.current = null;
    } catch (err) { showError(err, "Không tải được voice-over."); }
    finally { setBusy(false); event.target.value = ""; }
  };

  const resumeRun = async () => {
    if (!run) return;
    setBusy(true); setError(null); setErrorCode(null);
    try { setRun(await contentVideoApi.resumeRun(projectId, run.id, flowProfileId)); }
    catch (err) { showError(err, "Không tiếp tục được run."); }
    finally { setBusy(false); }
  };

  const rerenderRun = async (withSubtitles: boolean) => {
    if (!run) return;
    setBusy(true); setError(null); setErrorCode(null);
    try { setRun(await contentVideoApi.rerenderRun(projectId, run.id, withSubtitles)); }
    catch (err) { showError(err, "Không ghép lại được video."); }
    finally { setBusy(false); }
  };

  const uploadReconciliationClip = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      await mediaStudioApi.uploadAsset({ file, project_id: projectId, expected_category: "video" });
      setProjectAssets(await mediaStudioApi.listAssets({ project_id: projectId }));
    } catch (err) { showError(err, "Không tải được clip Flow cần đối soát."); }
    finally { setBusy(false); event.target.value = ""; }
  };

  const reconcileRunShot = async () => {
    const uncertainShot = run?.steps.find((step) => step.state === "NEEDS_RECONCILIATION");
    if (!run || !uncertainShot || !reconcileAssetId || !confirmedClipMatch || reconcileReason.trim().length < 12) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      setRun(await contentVideoApi.reconcileShot(projectId, run.id, uncertainShot.shot_id, reconcileAssetId, reconcileReason));
      setConfirmedClipMatch(false);
      setReconcileReason("");
      setReconcileAssetId("");
    } catch (err) { showError(err, "Không đối soát được clip Flow."); }
    finally { setBusy(false); }
  };

  const uncertainShot = run?.steps.find((step) => step.state === "NEEDS_RECONCILIATION");
  const flowProjectUrl = run?.steps.find((step) => step.flow_project_url)?.flow_project_url;
  const uncertainStoryboardShot = plan?.storyboard.shots.find((shot) => shot.shot_id === uncertainShot?.shot_id);
  const reconciliationCandidates = projectAssets.filter((asset) =>
    asset.mime_detected === "video/mp4" &&
    ["GOOGLE_FLOW", "UPLOAD"].includes(asset.source_product) &&
    (!run?.started_at || Date.parse(asset.created_at) >= Date.parse(run.started_at)),
  );

  if (errorCode === "PROJECT_NOT_FOUND") {
    return <main className="mx-auto flex min-h-[50vh] w-full max-w-xl flex-col justify-center gap-4 px-4"><Card className="space-y-3 p-6"><h1 className="text-lg font-semibold">Không tìm thấy dự án</h1><p className="text-sm text-muted-foreground">Dự án này không còn trong workspace. Quay lại danh sách để chọn dự án đang có.</p><Button type="button" onClick={() => router.push("/video-studio")}>Về danh sách video</Button></Card></main>;
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6">
      <header className="flex items-start gap-3">
        <Button variant="ghost" size="icon" aria-label="Về trang tạo video" onClick={() => router.push("/video-studio")}><ArrowLeft /></Button>
        <div className="flex-1"><p className="text-sm text-muted-foreground">Dự án · {plan?.storyboard.title || "Tạo video bằng AI"}</p><h1 className="text-2xl font-semibold">Quy trình tạo video</h1></div>
        {plan && <Button type="button" variant="outline" onClick={() => router.push(`/video-studio/${projectId}/production?new=1`)}><Sparkles className="mr-2 size-4" />Tạo video mới</Button>}
      </header>
      {directCreation && <FlowSessionManager onProfileChange={setFlowProfileId} />}

      <ol className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4" aria-label="Tiến độ tạo video">
        {["Nhập nội dung", "Duyệt storyboard", "Tạo video", "Xem video và QC"].map((label, index) => {
          const step = index + 1;
          const current = step === activeFlowStep;
          const complete = step < activeFlowStep;
          return <li key={label} aria-current={current ? "step" : undefined} className={`flex min-w-0 items-center gap-2 text-xs ${current ? "font-medium text-foreground" : complete ? "text-primary" : "text-muted-foreground"}`}>
            <span className={`flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${current ? "border-primary bg-primary text-primary-foreground" : complete ? "border-primary/30 bg-primary/10 text-primary" : "border-border"}`}>{complete ? <Check aria-hidden="true" className="size-3.5" /> : `0${step}`}</span>
            <span className="truncate">{label}</span>
          </li>;
        })}
      </ol>

      {loadingHistory && <Card role="status" className="p-5 text-sm text-muted-foreground">Đang tải video đã tạo trong dự án...</Card>}
      {(!plan || editingContent) && !loadingHistory && <Card className="p-5"><form className="flex flex-col gap-4" onSubmit={createPlan}>
        <div className="flex items-center justify-between gap-3"><label className="text-sm font-medium" htmlFor="content-source">Nội dung nguồn (40–12.000 ký tự; tối đa 12 KB UTF-8)</label><span className="text-xs text-muted-foreground">{contentBytes.toLocaleString("vi-VN")} / 12.000 byte</span></div>
        <textarea id="content-source" required minLength={40} maxLength={12000} value={content} onChange={(event) => setContent(event.target.value)} className="min-h-48 rounded-md border bg-background p-3 text-sm" placeholder="Dán bài viết, đề cương hoặc nội dung cần chuyển thành video..." />
        <label className="flex items-center gap-3 text-sm">Thời lượng mục tiêu <Input type="number" min={20} max={180} step={1} value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="w-28" /> giây</label>
        <label className="flex items-center gap-3 text-sm" htmlFor="aspect-ratio">Tỷ lệ video
          <select id="aspect-ratio" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value as "9:16" | "16:9")} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="9:16">Dọc 9:16</option><option value="16:9">Ngang 16:9</option>
          </select>
        </label>
        <p className="text-xs text-muted-foreground">Cảnh được chọn theo nội dung, có thể là cảnh vật, quy trình hoặc giao diện. Chỉ nối tiếp cảnh trước khi hành động cần liên tục; các cảnh giữ phong cách và bảng màu nhất quán.</p>
        {editingContent && <p className="text-sm text-muted-foreground">Lưu nội dung mới sẽ tạo revision storyboard mới; run và video của revision trước không còn là kết quả hiện hành.</p>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || content.trim().length < 40 || contentBytes > 12000 || duration < 20 || duration > 180 || (editingContent && sourceUnchanged)}><Sparkles className="mr-2 size-4" />{busy ? "Đang lập storyboard..." : editingContent ? "Lưu nội dung và tạo storyboard mới" : "Tạo storyboard bằng AI"}</Button>
          {editingContent && <Button type="button" variant="outline" onClick={cancelEditSource} disabled={busy}>Hủy sửa nội dung</Button>}
        </div>
      </form></Card>}

      {plan && !editingContent && <>
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h2 className="text-base font-semibold">{plan.storyboard.title}</h2><Badge variant={plan.status === "APPROVED" ? "secondary" : "outline"}>{plan.status === "APPROVED" ? "Đã duyệt" : directCreation ? "Có thể tạo video" : "Bản nháp"}</Badge></div>
            <p className="mt-1 text-sm text-muted-foreground">Bản {plan.revision} · {plan.target_duration_seconds} giây · {plan.storyboard.shots.length} cảnh · {plan.style_snapshot.aspect_ratio}</p>
            <p className="mt-1 text-xs text-muted-foreground">{plan.style_snapshot.style_name} · {plan.style_snapshot.palette.join(" / ")} · {plan.llm_model}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={editSource} disabled={busy || !canEditPreviousStep || editingStoryboard || storyboardDirty}>Quay lại sửa nội dung nguồn</Button>
            {plan.status === "APPROVED" && !editingStoryboard && <Button type="button" variant="outline" onClick={editStoryboard} disabled={busy || !canEditPreviousStep}>Quay lại sửa storyboard</Button>}
            {editingStoryboard && <Button type="button" variant="outline" onClick={() => { setStoryboardDraft(null); setExpandedShotIds([]); setEditingStoryboard(false); }} disabled={busy}>Hủy sửa storyboard</Button>}
            {plan.status === "DRAFT" && storyboardDirty && <Button type="button" variant="outline" onClick={() => setStoryboardDraft(null)} disabled={busy}>Hủy thay đổi storyboard</Button>}
            {(plan.status === "DRAFT" || editingStoryboard) && <>
              <Button variant="outline" onClick={saveStoryboard} disabled={busy || !storyboardDirty}><Save className="mr-2 size-4" />Lưu nội dung đã sửa</Button>
              {plan.status === "DRAFT" && !directCreation && <Button onClick={approve} disabled={busy || storyboardDirty}><Check className="mr-2 size-4" />Duyệt storyboard</Button>}
            </>}
            {(plan.status === "APPROVED" || directCreation) && !run && !editingStoryboard && <Button onClick={() => startRun()} disabled={busy || storyboardDirty || (voiceSource === "TTS" && !ttsReady) || (voiceSource === "UPLOAD" && !voiceAssetId) || (voiceSource === "TTS" && ttsProvider === "GWEN_TTS" && (!ttsReferenceAssetId || !ttsReferenceText.trim() || !voiceCloneConsent)) || (voiceSource === "TTS" && !!ttsReferenceAssetId && !voiceCloneConsent)}><Play className="mr-2 size-4" />Tạo video</Button>}
          </div>
        </Card>
        {run && !editingStoryboard && <Card className="grid gap-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-lg font-semibold">Video đã ghép</h2><p className="mt-1 text-sm text-muted-foreground">Run {run.id.slice(0, 8)} · {run.current_step ? `Đang xử lý ${run.current_step}` : runStatusLabel[run.status] || run.status}</p>{flowProjectUrl && <a href={flowProjectUrl} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm font-medium underline underline-offset-4">Mở project Flow của video này</a>}</div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={run.status === "COMPLETED" ? "secondary" : run.status === "FAILED" || run.status === "FAILED_QC" ? "destructive" : "outline"}>{runStatusLabel[run.status] || run.status}</Badge>
              {run.status === "FAILED" && run.error_code?.startsWith("TTS_") && <Button onClick={resumeRun} disabled={busy || !ttsReady}><RefreshCw data-icon="inline-start" />Tiếp tục sau khi xử lý TTS</Button>}
              {run.status === "BLOCKED_FLOW_LOGIN" && <Button onClick={resumeRun} disabled={busy}><RefreshCw data-icon="inline-start" />Tiếp tục sau khi đăng nhập Flow</Button>}
              {["BLOCKED_FLOW_SETUP", "BLOCKED_FLOW_QUOTA"].includes(run.status) && <Button onClick={resumeRun} disabled={busy}><RefreshCw data-icon="inline-start" />Tiếp tục sau khi sửa Flow</Button>}
              {ACTIVE_RUNS.has(run.status) && <LoaderCircle className="size-5 animate-spin" aria-label="Đang chạy" />}
            </div>
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
            <section aria-label="Video hoàn chỉnh" className="min-w-0">
              {finalUrl && !previewError ? <video controls playsInline src={finalUrl} onError={() => setPreviewError(true)} onLoadedData={() => setPreviewError(false)} className={`mx-auto rounded-xl bg-black object-contain ${plan.style_snapshot.aspect_ratio === "9:16" ? "aspect-[9/16] w-full max-w-sm" : "aspect-video w-full"}`} /> : <div role={previewError ? "alert" : "status"} className={`mx-auto flex items-center justify-center rounded-xl border bg-muted/40 p-6 text-center ${plan.style_snapshot.aspect_ratio === "9:16" ? "aspect-[9/16] w-full max-w-sm" : "aspect-video w-full"}`}>
                <div className="max-w-xs"><h3 className="font-medium">{previewError ? "Không phát được video này" : run.final_asset_id ? "Đang tải video đã ghép" : "Chưa có video hoàn chỉnh"}</h3><p className="mt-1 text-sm text-muted-foreground">{previewError ? "Tệp video không mở được trong trình xem. Bạn có thể thử lại cảnh cần chỉnh hoặc tải gói sản xuất." : run.final_asset_id ? "Video sẽ xuất hiện tại đây khi tải xong." : "Kết quả sẽ xuất hiện tại đây sau khi hoàn tất các cảnh."}</p></div>
              </div>}
            </section>
            <aside className="grid content-start gap-3" aria-label="Trạng thái và kiểm tra chất lượng">
              {run.qc_report && <section className="grid gap-2 rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium">Kiểm tra chất lượng</h3><Badge variant={run.qc_report.status === "PASS" ? "secondary" : "destructive"}>{run.qc_report.status === "PASS" ? "Đạt" : "Cần xem lại"}</Badge></div>
                <p className="text-sm text-muted-foreground">{run.qc_report.acceptance_mode || "QC kỹ thuật"}{run.qc_report.flow_native_audio ? " · Đã giữ âm thanh Flow" : ""}{run.qc_report.speech_alignment === "NOT_MEASURED" ? " · Chưa đo căn chỉnh lời" : ""}</p>
                {run.qc_report.issues.length > 0 && <p className="text-sm text-destructive">{run.qc_report.issues.join(", ")}</p>}
              </section>}
              {run.error_message && <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><p className="font-medium">{run.error_code}</p><p className="mt-1">{run.error_message}</p></div>}
              {run.voice_source === "TTS" && <p className="text-sm text-muted-foreground">Lời đọc được sinh bằng {run.tts_provider === "VIE_NEU_V3_TURBO" ? "VieNeu v3 Turbo" : "Gwen-TTS"}.</p>}
              {run.status === "COMPLETED" && finalUrl && <div className="grid gap-2 rounded-lg bg-primary/5 p-3"><p className="text-sm">Video đã ghép xong. Có thể chỉnh sửa hoặc ghép lại từ các clip Flow hiện có.</p><div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={() => router.push(`/video-studio/${projectId}`)}>Mở timeline để chỉnh sửa</Button><Button type="button" variant="outline" onClick={() => rerenderRun(true)} disabled={busy}>Ghép lại có phụ đề</Button><Button type="button" variant="outline" onClick={() => rerenderRun(false)} disabled={busy}>Ghép lại không phụ đề</Button></div></div>}
              {exportUrl && <Button type="button" variant="link" className="w-fit px-0" onClick={() => void mediaStudioApi.downloadAsset(exportUrl, "goi_san_xuat.zip").catch((err) => showError(err, "Không tải được gói sản xuất."))}>Tải gói sản xuất (ZIP)</Button>}
            </aside>
          </div>
          {flowProjectUnavailable && firstUnfinishedShot && <section className="grid gap-3 rounded-lg border p-4">
            <p className="text-sm">Không gửi được cảnh trong project Flow hiện tại. Nếu không truy cập được project đó, có thể mở project mới và bắt đầu đúng từ {firstUnfinishedShot.shot_id}; các clip đã hoàn tất vẫn được dùng lại.</p>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={newFlowProject} onChange={(event) => setNewFlowProject(event.target.checked)} className="mt-1" />Tôi không truy cập được project Flow hiện tại.</label>
            {newFlowProject && <Button type="button" onClick={() => retryShots([firstUnfinishedShot.shot_id], true)} disabled={busy} className="w-fit">Tiếp tục từ cảnh này trong project Flow mới</Button>}
          </section>}
          {uncertainShot && <section className="grid gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <div><h3 className="font-medium">Đối soát kết quả Flow · {uncertainShot.shot_id}</h3><p className="mt-1 text-sm text-muted-foreground">Flow có thể đã tạo clip nhưng worker chưa nhận được. Mở clip trong Flow, xác nhận đúng nội dung và nhân vật của cảnh này, rồi chọn hoặc tải clip đã tải về. Hệ thống sẽ kiểm tra tệp và tiếp tục từ cảnh sau, không gửi lại lệnh Flow.</p></div>
            {uncertainStoryboardShot && <div className="grid gap-2 rounded-md border bg-background p-3 text-sm"><p><span className="font-medium">Cảnh:</span> {uncertainStoryboardShot.scene}</p><p><span className="font-medium">Lời đọc:</span> {uncertainStoryboardShot.narration}</p><p className="text-muted-foreground"><span className="font-medium text-foreground">Prompt gửi Flow:</span> {uncertainStoryboardShot.prompt}</p></div>}
            <label htmlFor="reconcile-asset" className="text-sm font-medium">Clip trong dự án</label>
            <select id="reconcile-asset" value={reconcileAssetId} onChange={(event) => setReconcileAssetId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm"><option value="">Chọn clip</option>{reconciliationCandidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id} · {asset.source_product}</option>)}</select>
            <label className="grid gap-2 text-sm">Hoặc tải bản thu tiếng Việt lên<input type="file" accept="video/mp4,.mp4" onChange={uploadReconciliationClip} disabled={busy} className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-2" /></label>
            <label htmlFor="reconcile-reason" className="text-sm font-medium">Ghi chú đối soát</label>
            <textarea id="reconcile-reason" minLength={12} maxLength={500} value={reconcileReason} onChange={(event) => setReconcileReason(event.target.value)} className="min-h-20 rounded-md border bg-background p-3 text-sm" placeholder="Ví dụ: đã mở đúng kết quả mới của prompt cảnh này trong Flow..." />
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmedClipMatch} onChange={(event) => setConfirmedClipMatch(event.target.checked)} className="mt-1" />Tôi đã xem clip trong Flow và xác nhận clip này đúng cảnh đang chờ.</label>
            <Button onClick={reconcileRunShot} disabled={busy || !reconcileAssetId || !confirmedClipMatch || reconcileReason.trim().length < 12} className="w-fit">Xác nhận clip và tiếp tục run</Button>
            <label className="flex items-start gap-2 border-t pt-3 text-sm"><input type="checkbox" checked={confirmedNoFlowClip} onChange={(event) => setConfirmedNoFlowClip(event.target.checked)} className="mt-1" />Tôi đã kiểm tra Flow và xác nhận không có clip cho cảnh này.</label>
            <Button onClick={() => retryShots([uncertainShot.shot_id])} disabled={busy || !confirmedNoFlowClip} className="w-fit">Tạo lại từ cảnh này trong project Flow hiện tại</Button>
          </section>}
        </Card>}
        <section className="grid gap-3" aria-label="Storyboard">
          {editableStoryboard?.brief && <StoryboardBrief brief={editableStoryboard.brief} />}
          <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-semibold">Storyboard</h2><p className="text-sm text-muted-foreground">{plan.storyboard.shots.length} cảnh · Chọn một cảnh để xem chi tiết</p></div>{run && ["COMPLETED", "FAILED_QC"].includes(run.status) && <Button type="button" variant="outline" onClick={() => retryShots(run.steps.map((step) => step.shot_id))} disabled={busy}>Làm lại tất cả cảnh</Button>}</div>
          {editingStoryboard && <p className="text-sm text-muted-foreground">Lưu sẽ tạo revision storyboard mới và làm mất hiệu lực run/video của revision trước. Bản mới cần được duyệt lại.</p>}
          <Accordion type="multiple" value={expandedStoryboardShotIds} onValueChange={setExpandedShotIds} className="rounded-xl border bg-card pl-3 pr-1 sm:pl-4 sm:pr-1">
            {editableStoryboard?.shots.map((shot, index) => {
              const step = run?.steps.find((item) => item.shot_id === shot.shot_id);
              const completedRun = !!run && ["COMPLETED", "FAILED_QC"].includes(run.status);
              const retryableStep = !!run && canRetryRun && run.status !== "NEEDS_RECONCILIATION" && (completedRun ? step?.state === "SUCCEEDED" : shot.shot_id === firstUnfinishedShot?.shot_id) && (run.status !== "BLOCKED_FLOW_SETUP" || run.error_code !== "FLOW_CREDITS_INSUFFICIENT");
              const shotLabel = step ? shotStatusLabel[step.state] || step.state : run ? "Chưa tạo" : null;
              return <AccordionItem key={shot.shot_id} value={shot.shot_id} className="border-b last:border-b-0">
                <div className="flex min-w-0 items-center justify-between gap-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-semibold">Cảnh {index + 1}</span><span className="text-xs text-muted-foreground">{shot.shot_id} · {shot.duration_seconds} giây</span>{shotLabel && <Badge variant={step?.state === "FAILED" ? "destructive" : step?.state === "SUCCEEDED" ? "secondary" : "outline"}>{shotLabel}</Badge>}</div>
                    <div className="mt-1 flex flex-wrap gap-1"><ShotKindBadges shot={shot} /></div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{shot.scene}</p>
                  </div>
                  <div className="ml-auto flex shrink-0 items-center gap-2">
                    {retryableStep && <Button type="button" variant="outline" size="sm" onClick={() => retryShots([shot.shot_id])} disabled={busy}><RefreshCw data-icon="inline-start" />Tạo lại</Button>}
                    <AccordionTrigger className="h-8 w-fit flex-none justify-center gap-1 rounded-md border px-2 py-1 text-xs text-foreground hover:bg-muted hover:no-underline"><span>Chi tiết</span></AccordionTrigger>
                  </div>
                </div>
                <AccordionContent className="px-2 sm:px-3">
                  <div className="grid gap-3 pb-2">
                    {plan.status === "DRAFT" || editingStoryboard ? <>
                      <label className="grid gap-1 text-sm">Nội dung cảnh<textarea value={shot.scene} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, scene: event.target.value } : item) })} maxLength={300} className="min-h-16 rounded-md border bg-background p-3" /></label>
                      <label className="grid gap-1 text-sm">Lời thoại<textarea value={shot.narration} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, narration: event.target.value } : item) })} maxLength={2000} className="min-h-20 rounded-md border bg-background p-3" /></label>
                      {shot.shot_kind !== "UI_SIM" && <label className="grid gap-1 text-sm">Mô tả hình ảnh<textarea value={shot.prompt} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, prompt: event.target.value } : item) })} minLength={8} maxLength={3000} className="min-h-24 rounded-md border bg-background p-3" /></label>}
                    </> : <>
                      <p className="text-sm">{shot.scene}</p><p className="text-sm"><span className="font-medium">Lời đọc:</span> {shot.narration}</p>
                      {shot.shot_kind !== "UI_SIM" && <p className="text-sm text-muted-foreground"><span className="font-medium text-foreground">Mô tả hình ảnh:</span> {shot.prompt}</p>}
                      {shot.negative_prompt && <p className="text-xs text-muted-foreground"><span className="font-medium">Tránh:</span> {shot.negative_prompt}</p>}
                    </>}
                    <ShotActionDetails shot={shot} onChange={plan.status === "DRAFT" || editingStoryboard ? (nextShot) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? nextShot : item) }) : undefined} />
                  </div>
                </AccordionContent>
              </AccordionItem>;
            })}
          </Accordion>
          {plan.status === "DRAFT" && <p className="text-sm text-muted-foreground">Storyboard AI chỉ là bản nháp. Sửa nội dung cảnh, lời thoại và mô tả hình ảnh rồi lưu trước khi duyệt. Lời đọc sẽ lấy từ thoại của các cảnh theo thứ tự.</p>}
        </section>
        {(plan.status === "APPROVED" || directCreation) && !run && !editingStoryboard && <Card className="grid gap-3 p-4">
          <label htmlFor="voice-source" className="text-sm font-medium">Nguồn lời đọc tiếng Việt</label>
          {hasUiScenes && <p className="text-sm text-muted-foreground">Cảnh mô phỏng giao diện không có giọng Flow. Chọn TTS hoặc voiceover nếu cần lời đọc cho các cảnh này.</p>}
          <select id="voice-source" value={voiceSource} onChange={(event) => { setVoiceSource(event.target.value as typeof voiceSource); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="NONE">Không thêm âm thanh</option><option value="UPLOAD">Voiceover đã thu sẵn</option><option value="TTS">Sinh bằng TTS</option>
          </select>
          {voiceSource === "UPLOAD" && <>
            <label htmlFor="voice-asset" className="text-sm">Voiceover trong dự án</label>
            <select id="voice-asset" value={voiceAssetId} onChange={(event) => { setVoiceAssetId(event.target.value); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="">Chọn voiceover</option>{voiceAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id}{asset.duration_ms ? ` · ${(asset.duration_ms / 1000).toFixed(1)}s` : ""}</option>)}
            </select>
          </>}
          {voiceSource === "TTS" && <>
            {!ttsReady && <p className="text-sm text-muted-foreground" role="status">TTS chưa sẵn sàng. Cần chuẩn bị model và khởi động worker trước khi tạo video.</p>}
            <label htmlFor="tts-provider" className="text-sm">Nhà cung cấp TTS</label>
            <select id="tts-provider" value={ttsProvider} onChange={(event) => { setTtsProvider(event.target.value as typeof ttsProvider); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="VIE_NEU_V3_TURBO">VieNeu v3 Turbo</option><option value="GWEN_TTS" disabled>Gwen-TTS — chưa sẵn sàng</option>
            </select>
            {ttsProvider === "VIE_NEU_V3_TURBO" && <label className="grid gap-2 text-sm">Tên giọng VieNeu<Input value={ttsVoiceId} onChange={(event) => { setTtsVoiceId(event.target.value); idempotencyKey.current = null; }} maxLength={120} /></label>}
            <label htmlFor="tts-reference" className="text-sm">Audio tham chiếu (tùy chọn với VieNeu)</label>
            <select id="tts-reference" value={ttsReferenceAssetId} onChange={(event) => { setTtsReferenceAssetId(event.target.value); setVoiceCloneConsent(false); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="">Không dùng audio tham chiếu</option>{voiceAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id}</option>)}
            </select>
            <label className="grid gap-2 text-sm">Tải audio tham chiếu vào dự án
              <input type="file" accept="audio/*" onChange={uploadVoice} disabled={busy} className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-2" />
            </label>
            {ttsProvider === "GWEN_TTS" && <label className="grid gap-2 text-sm">Bản chép chính xác của audio tham chiếu
              <textarea value={ttsReferenceText} onChange={(event) => { setTtsReferenceText(event.target.value); idempotencyKey.current = null; }} maxLength={3000} required className="min-h-20 rounded-md border bg-background p-3 text-sm" />
            </label>}
            {ttsReferenceAssetId && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={voiceCloneConsent} onChange={(event) => { setVoiceCloneConsent(event.target.checked); idempotencyKey.current = null; }} className="mt-1" />Tôi có quyền sử dụng audio tham chiếu để tạo giọng đọc.</label>}
          </>}
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={includeSubtitles} onChange={(event) => { setIncludeSubtitles(event.target.checked); idempotencyKey.current = null; }} className="mt-1" /><span><span className="font-medium">Thêm phụ đề khi ghép video</span><span className="block text-xs text-muted-foreground">Phụ đề karaoke tô từ theo giọng đọc thật (nhận dạng giọng nói để lấy mốc thời gian). Có thể ghép lại có/không phụ đề sau khi video hoàn tất.</span></span></label>
          <p className="text-xs text-muted-foreground">Mỗi run chỉ dùng một nguồn lời đọc. Nếu TTS lỗi, hệ thống dừng run và không tự đổi nhà cung cấp.</p>
        </Card>}
        {plan.status === "DRAFT" && <p className="text-sm text-muted-foreground">Chia sẻ URL có mã plan này cho người duyệt. Người tạo không thể tự duyệt theo quy tắc phân quyền.</p>}
      </>}

      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><p>{error}</p>{errorCode === "LLM_NOT_CONFIGURED" && <a href="/settings/integrations" className="mt-2 inline-block font-medium underline underline-offset-4">Mở cấu hình cổng LLM</a>}</div>}
    </main>
  );
}
