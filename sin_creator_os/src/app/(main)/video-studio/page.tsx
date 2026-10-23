"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { FileVideo2, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { mediaStudioApi, ProductionProjectResponse } from "@/lib/api/media-studio-api";

export default function VideoStudioIndexPage() {
  const router = useRouter();
  const [projects, setProjects] = React.useState<ProductionProjectResponse[]>([]);
  const [title, setTitle] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);

  const loadProjects = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await mediaStudioApi.listProjects());
    } catch (err: any) {
      setError(err?.message || "Không thể tải danh sách dự án.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { void loadProjects(); }, [loadProjects]);

  const createProject = async (event: React.FormEvent) => {
    event.preventDefault();
    if (title.trim().length < 2) return;
    setCreating(true);
    setError(null);
    try {
      const project = await mediaStudioApi.createProject(title.trim());
      router.push(`/video-studio/${project.id}`);
    } catch (err: any) {
      setError(err?.message || "Không thể tạo dự án.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 py-6">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-medium text-muted-foreground">SIN Creator Studio</p>
        <h1 className="text-3xl font-semibold tracking-tight">Dự án video</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Tạo dự án để sinh video bằng Flow, dựng timeline và xuất bản MP4 dọc.
        </p>
      </header>

      <Card className="max-w-2xl p-5">
        <form onSubmit={createProject} className="flex flex-col gap-3 sm:flex-row">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            minLength={2}
            maxLength={255}
            placeholder="Tên dự án video"
            aria-label="Tên dự án video"
            required
          />
          <Button type="submit" disabled={creating || title.trim().length < 2}>
            <Plus className="mr-2 size-4" />
            {creating ? "Đang tạo..." : "Tạo dự án"}
          </Button>
        </form>
      </Card>

      <section className="flex flex-col gap-4" aria-labelledby="project-list-heading">
        <div className="flex items-center justify-between gap-4">
          <h2 id="project-list-heading" className="text-lg font-semibold">Dự án của workspace</h2>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadProjects()} disabled={loading}>
            <RefreshCw className="mr-2 size-4" />
            Tải lại
          </Button>
        </div>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {loading ? (
          <p role="status" className="text-sm text-muted-foreground">Đang tải dự án...</p>
        ) : projects.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center">
            <FileVideo2 className="mx-auto mb-3 size-8 text-muted-foreground" aria-hidden="true" />
            <p className="font-medium">Workspace chưa có dự án video</p>
            <p className="mt-1 text-sm text-muted-foreground">Tạo dự án ở trên để bắt đầu.</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Card key={project.id} className="flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="truncate font-medium">{project.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{project.status}</p>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={() => router.push(`/video-studio/${project.id}`)}>
                  Mở
                </Button>
              </Card>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
