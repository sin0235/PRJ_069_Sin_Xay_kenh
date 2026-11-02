"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { FileVideo2, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { contentVideoApi, ContentVideoApiError } from "@/lib/api/content-video-api";
import { mediaStudioApi, ProductionProjectResponse } from "@/lib/api/media-studio-api";
import { randomUuid } from "@/lib/utils";

const FLOW_STEPS = [
  ["01", "Nhập nội dung"],
  ["02", "Duyệt storyboard"],
  ["03", "Tạo video qua Flow"],
  ["04", "Xem video và QC"],
];

export default function VideoStudioIndexPage() {
  const router = useRouter();
  const [projects, setProjects] = React.useState<ProductionProjectResponse[]>([]);
  const [projectTitle, setProjectTitle] = React.useState("");
  const [content, setContent] = React.useState("");
  const [duration, setDuration] = React.useState(60);
  const [aspectRatio, setAspectRatio] = React.useState<"9:16" | "16:9">("9:16");
  const [draftProjectId, setDraftProjectId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);
  const contentBytes = new TextEncoder().encode(content).length;

  const loadProjects = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await mediaStudioApi.listProjects("AI_VIDEO"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải danh sách dự án.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { void loadProjects(); }, [loadProjects]);

  const createVideoPlan = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!projectTitle.trim() || content.trim().length < 40 || contentBytes > 12000 || duration < 20 || duration > 180) return;

    setCreating(true);
    setError(null);
    setErrorCode(null);
    try {
      let projectId = draftProjectId;
      if (!projectId) {
        const project = await mediaStudioApi.createProject(projectTitle.trim(), "AI_VIDEO");
        projectId = project.id;
        setDraftProjectId(project.id);
        setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      }

      const plan = await contentVideoApi.createPlan(projectId, content.trim(), duration, aspectRatio, randomUuid());
      router.push(`/video-studio/${projectId}/production?plan=${encodeURIComponent(plan.id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được storyboard.");
      setErrorCode(err instanceof ContentVideoApiError ? err.code || null : null);
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-7 px-4 py-6">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-medium text-primary">SIN Creator Studio</p>
        <h1 className="text-3xl font-semibold tracking-tight">Tạo video bằng AI</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Nhập nội dung một lần. AI lập storyboard để anh duyệt, sau đó Flow tạo cảnh và hệ thống ghép video hoàn chỉnh.
        </p>
      </header>

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Quy trình tạo video">
        {FLOW_STEPS.map(([number, label], index) => <li key={number} className={`flex items-center gap-3 rounded-lg border p-3 ${index === 0 ? "border-primary/40 bg-primary/5" : "bg-card"}`}>
          <span className={`grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${index === 0 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{number}</span>
          <span className={`text-sm ${index === 0 ? "font-medium" : "text-muted-foreground"}`}>{label}</span>
        </li>)}
      </ol>

      <Card className="grid gap-7 p-5 sm:p-7 lg:grid-cols-[minmax(0,1.6fr)_minmax(17rem,0.8fr)]">
        <form className="grid content-start gap-5" onSubmit={createVideoPlan}>
          <div className="grid gap-2">
            <label htmlFor="project-title" className="text-sm font-medium">Tên video (bắt buộc)</label>
            <Input id="project-title" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} minLength={2} maxLength={255} placeholder="Ví dụ: AI Agent trong chăm sóc khách hàng" required />
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="video-content" className="text-sm font-medium">Nội dung cần chuyển thành video</label>
              <span className="text-xs text-muted-foreground">{contentBytes.toLocaleString("vi-VN")} / 12.000 byte</span>
            </div>
            <textarea id="video-content" value={content} onChange={(event) => setContent(event.target.value)} minLength={40} maxLength={12000} required className="min-h-52 rounded-md border bg-background p-3 text-sm leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Dán bài viết, đề cương hoặc mô tả ý tưởng. AI sẽ chia thành các cảnh có lời đọc và mô tả hình ảnh." />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label htmlFor="target-duration" className="grid gap-2 text-sm font-medium">Thời lượng mục tiêu
              <div className="flex items-center gap-2"><Input id="target-duration" type="number" min={20} max={180} step={10} value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="w-32" /><span className="font-normal text-muted-foreground">giây</span></div>
            </label>
            <label htmlFor="aspect-ratio" className="grid gap-2 text-sm font-medium">Tỷ lệ khung hình
              <select id="aspect-ratio" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value as "9:16" | "16:9")} className="h-10 rounded-md border bg-background px-3 text-sm font-normal">
                <option value="9:16">Dọc 9:16</option><option value="16:9">Ngang 16:9</option>
              </select>
            </label>
          </div>
          <div className="grid gap-2">
            <Button type="submit" disabled={creating || projectTitle.trim().length < 2 || content.trim().length < 40 || contentBytes > 12000 || duration < 20 || duration > 180} className="h-11 w-fit px-5">
              <Sparkles className="mr-2 size-4" />{creating ? "AI đang lập storyboard..." : draftProjectId ? "Thử tạo storyboard lại" : "Tạo storyboard bằng AI"}
            </Button>
            {projectTitle.trim().length < 2 && <p className="text-xs text-muted-foreground">Nhập tên video để bật nút tạo storyboard.</p>}
            {draftProjectId && <p className="text-xs text-muted-foreground">Dự án đã được tạo. Có thể thử lập storyboard lại mà không tạo project trùng.</p>}
          </div>
        </form>

        <aside className="grid content-start gap-5 border-t pt-5 lg:border-l lg:border-t-0 lg:pl-7 lg:pt-0" aria-label="Cấu hình sản xuất">
          <div>
            <h2 className="font-semibold">Phong cách đã khóa</h2>
            <p className="mt-1 text-sm text-muted-foreground">Origami giấy gấp, dùng mô hình nhân vật, đạo cụ và bối cảnh bằng giấy đã hoàn thiện.</p>
          </div>
          <dl className="grid gap-3 text-sm">
            <div className="flex justify-between gap-4 border-b pb-2"><dt className="text-muted-foreground">Bảng màu</dt><dd className="text-right">Xanh navy · trắng ngà · xanh teal</dd></div>
            <div className="flex justify-between gap-4 border-b pb-2"><dt className="text-muted-foreground">Chuyển động</dt><dd className="text-right">Một hành động liền mạch mỗi cảnh</dd></div>
            <div className="flex justify-between gap-4 border-b pb-2"><dt className="text-muted-foreground">Âm thanh Flow</dt><dd className="text-right">Bật mặc định; lời nói dùng tiếng Việt</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Tỷ lệ</dt><dd className="text-right">Theo lựa chọn ở biểu mẫu</dd></div>
          </dl>
          <p className="text-xs leading-5 text-muted-foreground">Không tạo người đang gấp giấy. Nhân vật và bối cảnh xuất hiện dưới dạng mô hình origami hoàn chỉnh.</p>
        </aside>
      </Card>

      {error && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
        <p>{error}</p>{errorCode === "LLM_NOT_CONFIGURED" && <a href="/settings/integrations" className="mt-2 inline-block font-medium underline underline-offset-4">Mở cấu hình cổng LLM</a>}
      </div>}

      <section className="grid gap-4" aria-labelledby="project-list-heading">
        <div className="flex items-center justify-between gap-4">
          <div><h2 id="project-list-heading" className="text-lg font-semibold">Dự án gần đây</h2><p className="text-sm text-muted-foreground">Tiếp tục tạo storyboard cho một dự án đã có.</p></div>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadProjects()} disabled={loading}><RefreshCw className="mr-2 size-4" />Tải lại</Button>
        </div>
        {loading ? <p role="status" className="text-sm text-muted-foreground">Đang tải dự án...</p> : projects.length === 0 ? (
          <div className="rounded-xl border border-dashed p-7 text-center"><FileVideo2 className="mx-auto mb-3 size-8 text-muted-foreground" aria-hidden="true" /><p className="font-medium">Chưa có dự án video</p><p className="mt-1 text-sm text-muted-foreground">Dự án mới sẽ xuất hiện ở đây sau khi bắt đầu tạo storyboard.</p></div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => <Card key={project.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0"><p className="truncate font-medium">{project.title}</p><p className="mt-1 text-xs text-muted-foreground">{project.status}</p></div>
              <Button type="button" size="sm" onClick={() => router.push(`/video-studio/${project.id}/production`)}><FileVideo2 className="mr-2 size-4" />Mở dự án</Button>
            </Card>)}
          </div>
        )}
      </section>
    </main>
  );
}
