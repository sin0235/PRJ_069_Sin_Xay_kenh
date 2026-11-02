"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Clapperboard } from "lucide-react";

import { TuDongDungVideoDai } from "@/components/video_studio/tu_dong_dung_video_dai";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { type MediaAssetResponse, mediaStudioApi, type ProductionProjectResponse } from "@/lib/api/media-studio-api";

export default function AutoEditPage() {
  const [projects, setProjects] = useState<ProductionProjectResponse[]>([]);
  const [projectId, setProjectId] = useState("");
  const [newProjectTitle, setNewProjectTitle] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [initialOutputAssetId, setInitialOutputAssetId] = useState<string | null>(null);
  const [assets, setAssets] = useState<MediaAssetResponse[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void mediaStudioApi.listProjects("AUTO_EDIT").then((items) => {
      if (active) {
        setProjects(items);
        const query = new URLSearchParams(window.location.search);
        const requestedProjectId = query.get("project_id");
        setInitialOutputAssetId(query.get("asset_id"));
        if (requestedProjectId && items.some((project) => project.id === requestedProjectId)) {
          setProjectId(requestedProjectId);
        }
      }
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Không tải được danh sách dự án.");
    }).finally(() => {
      if (active) setLoadingProjects(false);
    });
    return () => { active = false; };
  }, []);

  const loadAssets = useCallback(async () => {
    if (!projectId) {
      setAssets([]);
      return;
    }
    try {
      setAssets(await mediaStudioApi.listAssets({ project_id: projectId, limit: 100, throwOnError: true }));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải danh sách video đã xử lý.");
    }
  }, [projectId]);

  const createAutoEditProject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const title = newProjectTitle.trim();
    if (title.length < 2 || creatingProject) return;
    setCreatingProject(true);
    setError(null);
    try {
      const project = await mediaStudioApi.createProject(title, "AUTO_EDIT");
      setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      setProjectId(project.id);
      setNewProjectTitle("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo dự án Auto Edit.");
    } finally {
      setCreatingProject(false);
    }
  };

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-1 py-2 sm:px-0">
      <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-center">
        <div className="grid size-12 shrink-0 place-items-center rounded-xl border bg-primary/5 text-primary">
          <Clapperboard className="size-6" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-medium text-primary">Auto Edit</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Dựng clip từ video dài</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
            Tìm các kịch bản trong một lần quay, chọn take tốt, lược khoảng nghỉ và thêm phụ đề cùng diễn họa giấy gấp.
          </p>
        </div>
      </header>

      <Card className="space-y-4 p-4 sm:p-5">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(17rem,0.62fr)] lg:items-start">
          <div className="space-y-1">
            <h2 className="font-semibold">Dự án Auto Edit</h2>
            <p className="text-sm text-muted-foreground">Dự án của luồng dựng tự động được quản lý riêng với luồng tạo video bằng AI.</p>
          </div>
          <label className="grid gap-2 text-sm font-medium" htmlFor="auto-edit-project">
            Dự án Auto Edit
            <select
              id="auto-edit-project"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              disabled={loadingProjects || projects.length === 0}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">{loadingProjects ? "Đang tải dự án Auto Edit" : "Chọn dự án Auto Edit"}</option>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}
            </select>
          </label>
        </div>

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
            <span>{error}</span>
            {projectId && (
              <button type="button" onClick={() => void loadAssets()} className="rounded border border-current px-3 py-1.5 font-medium">
                Tải lại danh sách clip
              </button>
            )}
          </div>
        )}
        <form onSubmit={createAutoEditProject} className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-end">
          <label className="grid flex-1 gap-2 text-sm font-medium" htmlFor="auto-edit-new-project">
            Tạo dự án Auto Edit
            <input
              id="auto-edit-new-project"
              value={newProjectTitle}
              onChange={(event) => setNewProjectTitle(event.target.value)}
              minLength={2}
              maxLength={255}
              required
              placeholder="Ví dụ: Video chia sẻ kiến thức tháng 11"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          <Button type="submit" disabled={creatingProject || loadingProjects || newProjectTitle.trim().length < 2}>
            {creatingProject ? "Đang tạo" : "Tạo dự án"}
          </Button>
        </form>
        {!loadingProjects && projects.length === 0 && !error && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">Chưa có dự án Auto Edit. Tạo một dự án ở trên để bắt đầu.</p>
        )}
        {projectId && <TuDongDungVideoDai key={projectId} projectId={projectId} assets={assets} onAssetsChanged={loadAssets} initialOutputAssetId={initialOutputAssetId} />}
      </Card>
    </main>
  );
}
