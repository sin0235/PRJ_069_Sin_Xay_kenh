"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, LoaderCircle, Play, RefreshCw, Save, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { mediaStudioApi, MediaAssetResponse } from "@/lib/api/media-studio-api";
import { contentVideoApi, ContentVideoApiError, ContentVideoPlan, ContentVideoRun } from "@/lib/api/content-video-api";

const ACTIVE_RUNS = new Set(["QUEUED", "RUNNING", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_SETUP"]);
const RETRYABLE_RUNS = new Set(["FAILED", "FAILED_QC"]);

export default function ContentVideoProduction({ projectId, planId, runId, startNew }: { projectId: string; planId?: string; runId?: string; startNew?: boolean }) {
  const router = useRouter();
  const [content, setContent] = React.useState("");
  const [duration, setDuration] = React.useState(60);
  const [aspectRatio, setAspectRatio] = React.useState<"9:16" | "16:9">("9:16");
  const [plan, setPlan] = React.useState<ContentVideoPlan | null>(null);
  const [storyboardDraft, setStoryboardDraft] = React.useState<ContentVideoPlan["storyboard"] | null>(null);
  const [run, setRun] = React.useState<ContentVideoRun | null>(null);
  const [loadingHistory, setLoadingHistory] = React.useState(!planId && !startNew);
  const [finalUrl, setFinalUrl] = React.useState<string | null>(null);
  const [exportUrl, setExportUrl] = React.useState<string | null>(null);
  const [projectAssets, setProjectAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceAssets, setVoiceAssets] = React.useState<MediaAssetResponse[]>([]);
  const [voiceSource, setVoiceSource] = React.useState<"NONE" | "UPLOAD" | "TTS">("NONE");
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
  const idempotencyKey = React.useRef<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const contentBytes = new TextEncoder().encode(content).length;
  const activeFlowStep = run?.status === "COMPLETED" ? 4 : plan?.status === "APPROVED" || run ? 3 : plan ? 2 : 1;
  const editableStoryboard = storyboardDraft || plan?.storyboard || null;
  const storyboardDirty = !!plan && !!storyboardDraft && JSON.stringify(storyboardDraft) !== JSON.stringify(plan.storyboard);

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
    if (planId || startNew) { setLoadingHistory(false); void reloadPlan(); return; }
    setLoadingHistory(true);
    void contentVideoApi.getLatestHistory(projectId).then(({ plan: latestPlan, run: latestRun }) => {
      if (!latestPlan) return;
      setPlan(latestPlan);
      setStoryboardDraft(null);
      setRun(latestRun);
      router.replace(`/video-studio/${projectId}/production?plan=${encodeURIComponent(latestPlan.id)}${latestRun ? `&run=${encodeURIComponent(latestRun.id)}` : ""}`);
    }).catch((err) => showError(err, "Không tải được video đã tạo trong dự án.")).finally(() => setLoadingHistory(false));
  }, [planId, projectId, reloadPlan, router, startNew]);
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

  const saveStoryboard = async () => {
    if (!plan || !editableStoryboard || !storyboardDirty) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      const storyboard = { ...editableStoryboard, narration: editableStoryboard.shots.map((shot) => shot.narration.trim()).join(" ") };
      const saved = await contentVideoApi.updatePlan(projectId, plan.id, storyboard);
      setPlan(saved); setStoryboardDraft(null);
    } catch (err) { showError(err, "Không lưu được nội dung storyboard."); }
    finally { setBusy(false); }
  };

  const startRun = async (confirmedUncertainRetry = false) => {
    if (!plan || (run?.status === "NEEDS_RECONCILIATION" && (!confirmedUncertainRetry || !confirmedNoFlowClip))) return;
    setBusy(true); setError(null); setErrorCode(null);
    try {
      idempotencyKey.current ||= `content-video-${plan.id}-${crypto.randomUUID()}`;
      const created = await contentVideoApi.createRun(projectId, plan.id, {
        source: voiceSource,
        assetId: voiceAssetId || null,
        provider: ttsProvider,
        voiceId: ttsVoiceId.trim() || undefined,
        referenceAssetId: ttsReferenceAssetId || undefined,
        referenceText: ttsReferenceText.trim() || undefined,
        consent: voiceCloneConsent,
      }, idempotencyKey.current);
      idempotencyKey.current = null;
      setConfirmedNoFlowClip(false);
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
      setTtsReferenceAssetId(asset.id);
      setVoiceCloneConsent(false);
      idempotencyKey.current = null;
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

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Tiến độ tạo video">
        {["Nhập nội dung", "Duyệt storyboard", "Tạo video qua Flow", "Xem video và QC"].map((label, index) => {
          const step = index + 1;
          const current = step === activeFlowStep;
          const complete = step < activeFlowStep;
          return <li key={label} aria-current={current ? "step" : undefined} className={`rounded-lg border p-3 text-sm ${current ? "border-primary/40 bg-primary/5 font-medium" : complete ? "border-primary/20 text-primary" : "text-muted-foreground"}`}>
            <span className="mr-2 font-semibold">0{step}</span>{label}
          </li>;
        })}
      </ol>

      {loadingHistory && <Card role="status" className="p-5 text-sm text-muted-foreground">Đang tải video đã tạo trong dự án...</Card>}
      {!plan && !loadingHistory && <Card className="p-5"><form className="flex flex-col gap-4" onSubmit={createPlan}>
        <div className="flex items-center justify-between gap-3"><label className="text-sm font-medium" htmlFor="content-source">Nội dung nguồn (40–12.000 ký tự; tối đa 12 KB UTF-8)</label><span className="text-xs text-muted-foreground">{contentBytes.toLocaleString("vi-VN")} / 12.000 byte</span></div>
        <textarea id="content-source" required minLength={40} maxLength={12000} value={content} onChange={(event) => setContent(event.target.value)} className="min-h-48 rounded-md border bg-background p-3 text-sm" placeholder="Dán bài viết, đề cương hoặc nội dung cần chuyển thành video..." />
        <label className="flex items-center gap-3 text-sm">Thời lượng mục tiêu <Input type="number" min={20} max={180} step={1} value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="w-28" /> giây</label>
        <label className="flex items-center gap-3 text-sm" htmlFor="aspect-ratio">Tỷ lệ video
          <select id="aspect-ratio" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value as "9:16" | "16:9")} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="9:16">Dọc 9:16</option><option value="16:9">Ngang 16:9</option>
          </select>
        </label>
        <p className="text-xs text-muted-foreground">Profile pilot cố định được khóa ở server; mọi shot dùng cùng bảng màu và continuity anchor. Shot sau nhận frame cuối shot trước làm tham chiếu và được nối bằng crossfade ngắn.</p>
        <Button type="submit" disabled={busy || content.trim().length < 40 || contentBytes > 12000 || duration < 20 || duration > 180}><Sparkles className="mr-2 size-4" />{busy ? "Đang lập storyboard..." : "Tạo storyboard bằng AI"}</Button>
      </form></Card>}

      {plan && <>
        <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div><p className="font-medium">{plan.storyboard.title} · Rev {plan.revision}</p><p className="text-sm text-muted-foreground">{plan.target_duration_seconds}s · {plan.storyboard.shots.length} shot · {plan.style_snapshot.aspect_ratio} · {plan.status} · {plan.llm_model}</p><p className="mt-1 text-xs text-muted-foreground">{plan.style_snapshot.style_name} · {plan.style_snapshot.palette.join(" / ")}</p></div>
          <div className="flex gap-2">
            {plan.status === "DRAFT" && <>
              <Button variant="outline" onClick={saveStoryboard} disabled={busy || !storyboardDirty}><Save className="mr-2 size-4" />Lưu nội dung đã sửa</Button>
              <Button onClick={approve} disabled={busy || storyboardDirty}><Check className="mr-2 size-4" />Duyệt storyboard</Button>
            </>}
            {plan.status === "APPROVED" && (!run || RETRYABLE_RUNS.has(run.status)) && <Button onClick={() => startRun()} disabled={busy || (voiceSource === "UPLOAD" && !voiceAssetId) || (voiceSource === "TTS" && ttsProvider === "GWEN_TTS" && (!ttsReferenceAssetId || !ttsReferenceText.trim() || !voiceCloneConsent)) || (voiceSource === "TTS" && !!ttsReferenceAssetId && !voiceCloneConsent)}><Play className="mr-2 size-4" />{run ? "Tạo run mới qua Flow" : "Tạo video qua Flow"}</Button>}
          </div>
        </Card>
        <section className="grid gap-3" aria-label="Storyboard">
          <h2 className="text-lg font-semibold">Storyboard · {plan.storyboard.shots.length} cảnh</h2>
          {editableStoryboard?.shots.map((shot, index) => <Card key={shot.shot_id} className="grid gap-3 p-4">
            <div className="flex items-start justify-between gap-3"><h3 className="font-medium">Cảnh {index + 1}</h3><span className="shrink-0 text-sm text-muted-foreground">{shot.duration_seconds}s</span></div>
            {plan.status === "DRAFT" ? <>
              <label className="grid gap-1 text-sm">Nội dung cảnh<textarea value={shot.scene} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, scene: event.target.value } : item) })} maxLength={300} className="min-h-16 rounded-md border bg-background p-3" /></label>
              <label className="grid gap-1 text-sm">Lời thoại<textarea value={shot.narration} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, narration: event.target.value } : item) })} maxLength={2000} className="min-h-20 rounded-md border bg-background p-3" /></label>
              <label className="grid gap-1 text-sm">Mô tả hình ảnh<textarea value={shot.prompt} onChange={(event) => setStoryboardDraft({ ...(storyboardDraft || plan.storyboard), shots: (storyboardDraft || plan.storyboard).shots.map((item) => item.shot_id === shot.shot_id ? { ...item, prompt: event.target.value } : item) })} minLength={8} maxLength={3000} className="min-h-24 rounded-md border bg-background p-3" /></label>
            </> : <>
              <p className="text-sm">{shot.scene}</p><p className="text-sm"><span className="font-medium">Lời đọc:</span> {shot.narration}</p>
              <p className="text-sm text-muted-foreground"><span className="font-medium text-foreground">Mô tả hình ảnh:</span> {shot.prompt}</p>
              {shot.negative_prompt && <p className="text-xs text-muted-foreground"><span className="font-medium">Tránh:</span> {shot.negative_prompt}</p>}
            </>}
          </Card>)}
          {plan.status === "DRAFT" && <p className="text-sm text-muted-foreground">Storyboard AI chỉ là bản nháp. Sửa nội dung cảnh, lời thoại và mô tả hình ảnh rồi lưu trước khi duyệt. Lời đọc sẽ lấy từ thoại của các cảnh theo thứ tự.</p>}
        </section>
        {plan.status === "APPROVED" && (!run || RETRYABLE_RUNS.has(run.status)) && <Card className="grid gap-3 p-4">
          <label htmlFor="voice-source" className="text-sm font-medium">Nguồn lời đọc tiếng Việt</label>
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
            <label htmlFor="tts-provider" className="text-sm">Nhà cung cấp TTS</label>
            <select id="tts-provider" value={ttsProvider} onChange={(event) => { setTtsProvider(event.target.value as typeof ttsProvider); idempotencyKey.current = null; }} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="VIE_NEU_V3_TURBO">VieNeu v3 Turbo</option><option value="GWEN_TTS">Gwen-TTS</option>
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
          <p className="text-xs text-muted-foreground">Mỗi run chỉ dùng một nguồn lời đọc. Nếu TTS lỗi, hệ thống dừng run và không tự đổi nhà cung cấp.</p>
        </Card>}
        {plan.status === "DRAFT" && <p className="text-sm text-muted-foreground">Chia sẻ URL có mã plan này cho người duyệt. Người tạo không thể tự duyệt theo quy tắc phân quyền.</p>}
      </>}

      {run && <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Run {run.id.slice(0, 8)} · {run.status}</h2>{run.current_step && <p className="text-sm text-muted-foreground">Đang xử lý {run.current_step}</p>}{flowProjectUrl && <a href={flowProjectUrl} target="_blank" rel="noreferrer" className="text-sm font-medium underline underline-offset-4">Mở project Flow của video này</a>}</div>
          {run.status === "BLOCKED_FLOW_LOGIN" && <Button onClick={resumeRun} disabled={busy}><RefreshCw className="mr-2 size-4" />Tiếp tục sau khi đăng nhập Flow</Button>}
          {run.status === "BLOCKED_FLOW_SETUP" && <Button onClick={resumeRun} disabled={busy}><RefreshCw className="mr-2 size-4" />Tiếp tục sau khi sửa Flow</Button>}
          {ACTIVE_RUNS.has(run.status) && <LoaderCircle className="size-5 animate-spin" aria-label="Đang chạy" />}
        </div>
        {uncertainShot && <section className="grid gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-4">
          <div><h3 className="font-medium">Đối soát kết quả Flow · {uncertainShot.shot_id}</h3><p className="mt-1 text-sm text-muted-foreground">Flow có thể đã tạo clip nhưng worker chưa nhận được. Mở clip trong Flow, xác nhận đúng nội dung và nhân vật của shot này, rồi chọn hoặc tải clip đã tải về. Hệ thống sẽ kiểm tra file và tiếp tục từ shot sau, không gửi lại lệnh Flow.</p></div>
          {uncertainStoryboardShot && <div className="grid gap-2 rounded-md border bg-background p-3 text-sm"><p><span className="font-medium">Cảnh:</span> {uncertainStoryboardShot.scene}</p><p><span className="font-medium">Lời đọc:</span> {uncertainStoryboardShot.narration}</p><p className="text-muted-foreground"><span className="font-medium">Prompt gửi Flow:</span> {uncertainStoryboardShot.prompt}</p></div>}
          <label htmlFor="reconcile-asset" className="text-sm font-medium">Clip trong dự án</label>
          <select id="reconcile-asset" value={reconcileAssetId} onChange={(event) => setReconcileAssetId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="">Không thêm âm thanh</option>
            {reconciliationCandidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename || asset.id} · {asset.source_product}</option>)}
          </select>
          <label className="grid gap-2 text-sm">Hoặc tải bản thu tiếng Việt lên
            <input type="file" accept="video/mp4,.mp4" onChange={uploadReconciliationClip} disabled={busy} className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-2" />
          </label>
          <label htmlFor="reconcile-reason" className="text-sm font-medium">Ghi chú đối soát</label>
          <textarea id="reconcile-reason" minLength={12} maxLength={500} value={reconcileReason} onChange={(event) => setReconcileReason(event.target.value)} className="min-h-20 rounded-md border bg-background p-3 text-sm" placeholder="Ví dụ: đã mở đúng kết quả mới của prompt shot này trong Flow..." />
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmedClipMatch} onChange={(event) => setConfirmedClipMatch(event.target.checked)} className="mt-1" />Tôi đã xem clip trong Flow và xác nhận clip này đúng shot đang chờ.</label>
          <Button onClick={reconcileRunShot} disabled={busy || !reconcileAssetId || !confirmedClipMatch || reconcileReason.trim().length < 12} className="w-fit">Xác nhận clip và tiếp tục run</Button>
          <label className="flex items-start gap-2 border-t pt-3 text-sm"><input type="checkbox" checked={confirmedNoFlowClip} onChange={(event) => setConfirmedNoFlowClip(event.target.checked)} className="mt-1" />Tôi đã kiểm tra Flow và không có clip cho shot này. Run mới sẽ gửi lại toàn bộ video trong project Flow mới; nếu request cũ hoàn tất trễ, Flow có thể tạo thêm clip.</label>
          <Button onClick={() => startRun(true)} disabled={busy || !confirmedNoFlowClip} className="w-fit">Tạo lại video trong project Flow mới</Button>
        </section>}
        <div className="grid gap-2 sm:grid-cols-2">{run.steps.map((step) => <div key={step.shot_id} className="rounded-md border p-3 text-sm">{step.shot_id} <span className="float-right text-muted-foreground">{step.state}</span></div>)}</div>
        {run.voice_source === "TTS" && <p className="text-sm text-muted-foreground">Lời đọc được sinh bằng {run.tts_provider === "VIE_NEU_V3_TURBO" ? "VieNeu v3 Turbo" : "Gwen-TTS"}.</p>}
        {run.error_message && <p role="alert" className="text-sm text-destructive">{run.error_code}: {run.error_message}</p>}
        {run.qc_report && <div className="rounded-md border p-3 text-sm">QC kỹ thuật: <strong>{run.qc_report.status}</strong>{run.qc_report.acceptance_mode && <span> · {run.qc_report.acceptance_mode}</span>}{run.qc_report.flow_native_audio && <span> · đã giữ âm thanh Flow</span>}{run.qc_report.speech_alignment === "NOT_MEASURED" && <span> · căn chỉnh lời chưa đo</span>}{run.qc_report.issues.length > 0 && <span> · {run.qc_report.issues.join(", ")}</span>}</div>}
        {finalUrl && <video controls playsInline src={finalUrl} className="max-h-[70vh] rounded-lg bg-black" />}
        {run.status === "COMPLETED" && finalUrl && <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4"><p className="text-sm">Video đã ghép xong. Có thể chỉnh sửa hoặc ghép lại từ các clip Flow hiện có.</p><Button type="button" onClick={() => router.push(`/video-studio/${projectId}`)}>Mở timeline để chỉnh hoặc ghép lại</Button></div>}
        {exportUrl && <button type="button" onClick={() => void mediaStudioApi.downloadAsset(exportUrl, "goi_san_xuat.zip").catch((err) => showError(err, "Không tải được gói sản xuất."))} className="text-sm font-medium underline underline-offset-4">Tải gói sản xuất (ZIP)</button>}
      </Card>}
      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><p>{error}</p>{errorCode === "LLM_NOT_CONFIGURED" && <a href="/settings/integrations" className="mt-2 inline-block font-medium underline underline-offset-4">Mở cấu hình cổng LLM</a>}</div>}
    </main>
  );
}
