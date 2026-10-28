"use client";

import * as React from "react";
import { Loader2, Sparkles, AlertCircle, CheckCircle2, RotateCw } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { AIJob } from "@/types";

export function AIJobIndicator() {
  const [jobs, setJobs] = React.useState<AIJob[]>([]);
  const activeJobs = jobs.filter((j) => j.status === "processing" || j.status === "queued");

  const handleRetry = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) => (j.id === jobId ? { ...j, status: "processing", progress: 15, error: undefined } : j))
    );
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-2 rounded-lg border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary font-medium text-xs px-2.5 transition-all"
        >
          {activeJobs.length > 0 ? (
            <Loader2 className="size-3.5 animate-spin text-primary" />
          ) : (
            <Sparkles className="size-3.5 text-primary" />
          )}
          <span className="font-semibold">Tác Vụ AI</span>
          {activeJobs.length > 0 && (
            <span className="inline-flex items-center justify-center size-4 rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
              {activeJobs.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80 rounded-xl shadow-xl border-border/80 p-2" align="end">
        <DropdownMenuLabel className="text-xs font-semibold px-2 py-1.5 flex items-center justify-between text-foreground">
          <span className="flex items-center gap-1.5">
            <Sparkles className="size-3.5 text-primary" /> Tiến Trình AI Hoạt Động
          </span>
          <Badge variant="secondary" className="text-[10px] font-medium">
            Credit: 420 BAHA Group
          </Badge>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        <div className="max-h-72 overflow-y-auto space-y-2 py-1">
          {jobs.length === 0 ? (
            <div className="py-6 text-center text-xs text-muted-foreground">
              Không có dữ liệu tác vụ AI
            </div>
          ) : (
            jobs.map((job) => (
              <div
                key={job.id}
                className="p-2.5 rounded-lg border border-border/60 hover:bg-muted/40 transition-colors space-y-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-medium text-foreground line-clamp-1 leading-snug">
                    {job.title}
                  </span>
                  {job.status === "processing" && (
                    <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-500 bg-amber-500/10 shrink-0">
                      Đang chạy
                    </Badge>
                  )}
                  {job.status === "completed" && (
                    <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-500 bg-emerald-500/10 shrink-0">
                      Xong
                    </Badge>
                  )}
                  {job.status === "failed" && (
                    <Badge variant="outline" className="text-[10px] border-rose-500/40 text-rose-500 bg-rose-500/10 shrink-0">
                      Thất bại
                    </Badge>
                  )}
                  {job.status === "queued" && (
                    <Badge variant="outline" className="text-[10px] border-slate-500/40 text-muted-foreground shrink-0">
                      Chờ lượt
                    </Badge>
                  )}
                </div>

                {job.status === "processing" && (
                  <div className="space-y-1">
                    <Progress value={job.progress} className="h-1.5" />
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>Xử lý tác vụ AI...</span>
                      <span>{job.progress}%</span>
                    </div>
                  </div>
                )}

                {job.error && (
                  <div className="flex items-center justify-between gap-1 text-[11px] text-rose-500 bg-rose-500/5 p-1.5 rounded">
                    <span className="truncate">{job.error}</span>
                    <button
                      onClick={() => handleRetry(job.id)}
                      className="flex items-center gap-1 font-semibold hover:underline shrink-0 text-[10px]"
                    >
                      <RotateCw className="size-2.5" /> Thử lại
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-center justify-center text-xs text-primary font-medium hover:bg-primary/5 cursor-pointer rounded-lg py-1.5">
          Xem Toàn Bộ Lịch Sử Tác Vụ (Job Center)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
