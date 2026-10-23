"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, LoaderCircle, Play, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { mediaStudioApi, MediaAssetResponse } from "@/lib/api/media-studio-api";
import { contentVideoApi, ContentVideoApiError, ContentVideoPlan, ContentVideoRun } from "@/lib/api/content-video-api";

const ACTIVE_RUNS = new Set(["QUEUED", "RUNNING", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_SETUP"]);
const RETRYABLE_RUNS = new Set(["FAILED", "FAILED_QC"]);

export default function ContentVideoProduction({ projectId, planId, runId }: { projectId: string; planId?: string; runId?: string }) {
  const router = useRouter();
  const [content, setContent] = React.useState("");
  const [duration, setDuration] = React.useState(60);
  const [plan, setPlan] = React.useState<ContentVideoPlan | null>(null);
  const [run, setRun] = React.useState<ContentVideoRun | null>(null);
  const [finalUrl, setFinalUrl] = React.useState<string | null>(null);
  const [exportUrl, setExportUrl] = React.useState<string | null>(null);
  const [projectAssets, setProjectAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceAssets, setVoiceAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceAssetId, setVoiceAssetId] = React.useState("");
  const [reconcileAssetId, setReconcileAssetId] = React.useState("");
  const [reconcileReason, setReconcileReason] = React.useState("");
  const [confirmedClipMatch, setConfirmedClipMatch] = React.useState(false);
  const idempotencyKey = React.useRef<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const contentBytes = new TextEncoder().encode(content).length;

  const showError = (err: unknown, fallback: string) => {
    setError(err instanceof Error ? err.message : fallback);
    setErrorCode(err instanceof ContentVideoApiError ? err.code || null : null);
  };

  const reloadPlan = React.useCallback(async () => {
    if (!planId) return;
    try { setPlan(await contentVideoApi.getPlan(projectId, planId)); }
    catch (err) { showError(err, "Không tải được storyboard."); }
  }, [planId, projectId]);

  React.useEffect(() => { void reloadPlan(); }, [reloadPlan]);
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
    void mediaStudioApi.listAssets({ project_id: projectId }).then((assets) => {
      setProjectAssets(assets);
      setFinalUrl(assets.find((asset) => asset.id === run.final_asset_id)?.url || null);
      setExportUrl(assets.find((asset) => asset.id === run.qc_report?.export_asset_id)?.url || null);
    });
  }, [projectId, run?.final_asset_id, run?.qc_report?.export_asset_id]);
  React.useEffect(() => {
    if (run?.status !== "NEEDS_RECONCILIATION") return;
    void mediaStudioApi.listAssets({ project_id: projectId }).then(setProjectAssets);
  }, [projectId, run?.status]);

  const createPlan = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null); setErrorCode(null);
    try {
      const next = await contentVideoApi.createPlan(projectId, content, duration);
      setPlan(next);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(next.id)}`);
    } catch (err) { showError(err, "Không tạo được storyboard."); }
    finally { setBusy(false); }
  };

  const approve = async () => {
    if (!plan) return;
    setBusy(true); setError(null); setErrorCode(null);
    try { setPlan(await contentVideoApi.approvePlan(projectId, plan.id)); }
    catch (err) { showError(err, "Không duyệt được storyboard."); }
    finally { setBusy(false); }
  };

  const startRun = async () => {
    if (!plan) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      idempotencyKey.current ||= `content-video-${plan.id}-${crypto.randomUUID()}`;
      const created = await contentVideoApi.createRun(projectId, plan.id, voiceAssetId || null, idempotencyKey.current);
      idempotencyKey.current = null;
      setRun(created);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(plan.id)}&run=${encodeURIComponent(created.id)}`);
    }
    catch (err) { showError(err, "Không khởi chạy được video."); }
    finally { setBusy(false); }
  };

  const uploadVoice = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      const asset = await mediaStudioApi.uploadAsset({ file, project_id: projectId, expected_category: "audio" });
      setVoiceAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)]);
      setVoiceAssetId(asset.id);
    } catch (err) { showError(err, "Không tải được voice-over."); }
    finally { setBusy(false); event.target.value = ""; }
  };

  const resumeRun = async () => {
    if (!run) return;
    setBusy(true); setError(null); setErrorCode(null);
    try { setRun(await contentVideoApi.resumeRun(projectId, run.id)); }
    catch (err) { showError(err, "Không tiếp tục được run."); }
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
  const uncertainStoryboardShot = plan?.storyboard.shots.find((shot) => shot.shot_id === uncertainShot?.shot_id);
  const reconciliationCandidates = projectAssets.filter((asset) =>
    asset.mime_detected === "video/mp4" &&
    ["GOOGLE_FLOW", "UPLOAD"].includes(asset.source_product) &&
    (!run?.started_at || Date.parse(asset.created_at) >= Date.parse(run.started_at)),
  );

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 py-6">
      <header className="flex items-start gap-3">
        <Button variant="ghost" size="icon" aria-label="Quay lại" onClick={() => router.push(`/video-studio/${projectId}`)}><ArrowLeft /></Button>
        <div><p className="text-sm text-muted-foreground">Sản xuất thật · LLM → duyệt → Flow → QC</p><h1 className="text-2xl font-semibold">Tạo video từ nội dung</h1></div>
      </header>

      {!plan && <Card className="p-5"><form className="flex flex-col gap-4" onSubmit={createPlan}>
        <div className="flex items-center justify-between gap-3"><label className="text-sm font-medium" htmlFor="content-source">Nội dung nguồn (40–12.000 ký tự; tối đa 12 KB UTF-8)</label><span className="text-xs text-muted-foreground">{contentBytes.toLocaleString("vi-VN")} / 12.000 byte</span></div>
        <textarea id="content-source" required minLength={40} maxLength={12000} value={content} onChange={(event) => setContent(event.target.value)} className="min-h-48 rounded-md border bg-background p-3 text-sm" placeholder="Dán bài viết, đề cương hoặc nội dung cần chuyển thành video..." />
        <label className="flex items-center gap-3 text-sm">Thời lượng mục tiêu <Input type="number" min={30} max={180} step={1} value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="w-28" /> giây</label>
        <p className="text-xs text-muted-foreground">Profile pilot cố định được khóa ở server; mọi shot dùng cùng bảng màu và continuity anchor. Shot sau nhận frame cuối shot trước làm tham chiếu và được nối bằng crossfade ngắn.</p>
        <Button type="submit" disabled={busy || content.trim().length < 40 || contentBytes > 12000 || duration < 30 || duration > 180}><Sparkles className="mr-2 size-4" />{busy ? "Đang lập storyboard..." : "Tạo storyboard"}</Button>
      </form></Card>}

      {plan && <>
        <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div><p className="font-medium">{plan.storyboard.title} · Rev {plan.revision}</p><p className="text-sm text-muted-foreground">{plan.target_duration_seconds}s · {plan.storyboard.shots.length} shot · {plan.status} · {plan.llm_model}</p><p className="mt-1 text-xs text-muted-foreground">{plan.style_snapshot.style_name} · {plan.style_snapshot.palette.join(" / ")}</p></div>
          <div className="flex gap-2">
            {plan.status === "DRAFT" && <Button onClick={approve} disabled={busy}><Check className="mr-2 size-4" />Duyệt storyboard</Button>}
            {plan.status === "APPROVED" && (!run || RETRYABLE_RUNS.has(run.status)) && <Button onClick={startRun} disabled={busy}><Play className="mr-2 size-4" />{run ? "Tạo run mới qua Flow" : "Tạo video qua Flow"}</Button>}
          </div>
        </Card>
        {plan.status === "APPROVED" && (!run || RETRYABLE_RUNS.has(run.status)) && <Card className="grid gap-3 p-4">
          <div><h2 className="font-medium">Âm thanh lời đọc</h2><p className="text-sm text-muted-foreground">Để trống để dùng lời thoại do Flow tạo trong từng shot. Hoặc chọn/tải voice-over dài đúng {plan.target_duration_seconds} giây (sai số tối đa 0,5 giây); bản thu sẽ thay lời đọc Flow trong video cuối.</p></div>
          <label htmlFor="voice-asset" className="text-sm font-medium">Nguồn lời đọc</label>
          <select id="voice-asset" value={voiceAssetId} onChange={(event) => { setVoiceAssetId(event.target.value); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="">Lời đọc native của Flow</option>
            {voiceAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id}{asset.duration_ms ? ` · ${(asset.duration_ms / 1000).toFixed(1)}s` : ""}</option>)}
          </select>
          <label className="grid gap-2 text-sm">Hoặc tải voice-over lên
            <input type="file" accept="audio/*" onChange={uploadVoice} disabled={busy} className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-2" />
          </label>
        </Card>}
        {plan.status === "DRAFT" && <p className="text-sm text-muted-foreground">Chia sẻ URL có mã plan này cho người duyệt. Người tạo không thể tự duyệt theo quy tắc phân quyền.</p>}
        <section className="grid gap-3">{plan.storyboard.shots.map((shot, index) => <Card key={shot.shot_id} className="grid gap-3 p-4 md:grid-cols-[100px_1fr]"><div className="text-sm font-semibold">Shot {index + 1}<p className="font-normal text-muted-foreground">{shot.duration_seconds}s</p></div><div><h2 className="font-medium">{shot.scene}</h2><p className="mt-1 text-sm">{shot.narration}</p><p className="mt-2 text-xs text-muted-foreground">{shot.prompt}</p></div></Card>)}</section>
      </>}

      {run && <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Run {run.id.slice(0, 8)} · {run.status}</h2>{run.current_step && <p className="text-sm text-muted-foreground">Đang xử lý {run.current_step}</p>}</div>
          {run.status === "BLOCKED_FLOW_LOGIN" && <Button onClick={resumeRun} disabled={busy}><RefreshCw className="mr-2 size-4" />Tiếp tục sau khi đăng nhập Flow</Button>}
          {run.status === "BLOCKED_FLOW_SETUP" && <Button onClick={resumeRun} disabled={busy}><RefreshCw className="mr-2 size-4" />Tiếp tục sau khi sửa Flow</Button>}
          {ACTIVE_RUNS.has(run.status) && <LoaderCircle className="size-5 animate-spin" aria-label="Đang chạy" />}
        </div>
        {uncertainShot && <section className="grid gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-4">
          <div><h3 className="font-medium">Đối soát kết quả Flow · {uncertainShot.shot_id}</h3><p className="mt-1 text-sm text-muted-foreground">Flow có thể đã tạo clip nhưng worker chưa nhận được. Mở clip trong Flow, xác nhận đúng nội dung và nhân vật của shot này, rồi chọn hoặc tải clip đã tải về. Hệ thống sẽ kiểm tra file và tiếp tục từ shot sau, không gửi lại lệnh Flow.</p></div>
          {uncertainStoryboardShot && <div className="grid gap-2 rounded-md border bg-background p-3 text-sm"><p><span className="font-medium">Cảnh:</span> {uncertainStoryboardShot.scene}</p><p><span className="font-medium">Lời đọc:</span> {uncertainStoryboardShot.narration}</p><p className="text-muted-foreground"><span className="font-medium">Prompt:</span> {uncertainStoryboardShot.prompt}</p></div>}
          <label htmlFor="reconcile-asset" className="text-sm font-medium">Clip trong dự án</label>
          <select id="reconcile-asset" value={reconcileAssetId} onChange={(event) => setReconcileAssetId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="">Chọn clip MP4 mới của run này</option>
            {reconciliationCandidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id} · {asset.source_product}</option>)}
          </select>
          <label className="grid gap-2 text-sm">Hoặc tải clip Flow đã tải về
            <input type="file" accept="video/mp4,.mp4" onChange={uploadReconciliationClip} disabled={busy} className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-2" />
          </label>
          <label htmlFor="reconcile-reason" className="text-sm font-medium">Ghi chú đối soát</label>
          <textarea id="reconcile-reason" minLength={12} maxLength={500} value={reconcileReason} onChange={(event) => setReconcileReason(event.target.value)} className="min-h-20 rounded-md border bg-background p-3 text-sm" placeholder="Ví dụ: đã mở đúng kết quả mới của prompt shot này trong Flow..." />
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmedClipMatch} onChange={(event) => setConfirmedClipMatch(event.target.checked)} className="mt-1" />Tôi đã xem clip trong Flow và xác nhận clip này đúng shot đang chờ.</label>
          <Button onClick={reconcileRunShot} disabled={busy || !reconcileAssetId || !confirmedClipMatch || reconcileReason.trim().length < 12} className="w-fit">Xác nhận clip và tiếp tục run</Button>
        </section>}
        <div className="grid gap-2 sm:grid-cols-2">{run.steps.map((step) => <div key={step.shot_id} className="rounded-md border p-3 text-sm">{step.shot_id} <span className="float-right text-muted-foreground">{step.state}</span></div>)}</div>
        {run.error_message && <p role="alert" className="text-sm text-destructive">{run.error_code}: {run.error_message}</p>}
        {run.qc_report && <div className="rounded-md border p-3 text-sm">QC kỹ thuật: <strong>{run.qc_report.status}</strong>{run.qc_report.acceptance_mode && <span> · {run.qc_report.acceptance_mode}</span>}{run.qc_report.voice_source === "FLOW_NATIVE" && <span> · lời đọc Flow</span>}{run.qc_report.speech_alignment === "NOT_MEASURED" && <span> · căn chỉnh lời chưa đo</span>}{run.qc_report.issues.length > 0 && <span> · {run.qc_report.issues.join(", ")}</span>}</div>}
        {finalUrl && <video controls playsInline src={finalUrl} className="max-h-[70vh] rounded-lg bg-black" />}
        {exportUrl && <a href={exportUrl} download className="text-sm font-medium underline underline-offset-4">Tải gói sản xuất (ZIP)</a>}
      </Card>}
      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><p>{error}</p>{errorCode === "LLM_NOT_CONFIGURED" && <a href="/settings/integrations" className="mt-2 inline-block font-medium underline underline-offset-4">Mở cấu hình cổng LLM</a>}</div>}
    </main>
  );
}
