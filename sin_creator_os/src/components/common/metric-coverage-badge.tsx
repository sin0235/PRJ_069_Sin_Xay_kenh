import * as React from "react";
import { ShieldCheck, Clock, AlertTriangle, AlertCircle, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface MetricCoverageBadgeProps {
  metrics?: Record<string, any> | null;
  metricsStatus?: string;
  observedAt?: string | null;
  className?: string;
}

/**
 * MetricCoverageBadge: Hien thi tinh trang quan sat du lieu chi so
 * Tuan thu nguyen tac Ground Truth P11 va Quy chuan Rule 9 (100% SVG Vector, 0 Emoji).
 */
export function MetricCoverageBadge({
  metrics,
  metricsStatus,
  observedAt,
  className = "",
}: MetricCoverageBadgeProps) {
  // 1. Truong hop chua co quan sat so lieu thuc te hoac metrics == null
  const isMissingMetrics =
    metrics == null ||
    metricsStatus === "METRICS_NOT_YET_OBSERVED" ||
    metricsStatus === "NOT_AVAILABLE";

  if (isMissingMetrics) {
    return (
      <Badge
        variant="outline"
        className={`bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20 text-[10px] font-medium gap-1.5 px-2 py-0.5 ${className}`}
      >
        <Clock className="size-3 shrink-0" />
        <span>CHƯA CÓ QUAN SÁT THỰC TẾ</span>
      </Badge>
    );
  }

  // 2. Truong hop kenh bi het han hoac so lieu quan sat > 30 ngay
  let isExpired = metricsStatus === "EXPIRED" || metricsStatus === "TOKEN_EXPIRED";
  if (!isExpired && observedAt) {
    const obsDate = new Date(observedAt);
    const now = new Date();
    const diffDays = (now.getTime() - obsDate.getTime()) / (1000 * 3600 * 24);
    if (diffDays > 30) {
      isExpired = true;
    }
  }

  if (isExpired) {
    return (
      <Badge
        variant="outline"
        className={`bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 text-[10px] font-medium gap-1.5 px-2 py-0.5 ${className}`}
      >
        <AlertTriangle className="size-3 shrink-0 text-amber-600" />
        <span>SỐ LIỆU ĐÃ HẾT HẠN</span>
      </Badge>
    );
  }

  // 3. Truong hop phat hien bat thuong do TikTok loc bot view sut giam
  if (metricsStatus === "AUDIT_PURGED_ANOMALY") {
    return (
      <Badge
        variant="outline"
        className={`bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30 text-[10px] font-medium gap-1.5 px-2 py-0.5 ${className}`}
      >
        <RefreshCw className="size-3 shrink-0 text-blue-600" />
        <span>ĐÃ LỌC VIEW BOT TIKTOK</span>
      </Badge>
    );
  }

  // 4. So lieu quan sat hop le da duoc kiem chung
  return (
    <Badge
      variant="outline"
      className={`bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-medium gap-1.5 px-2 py-0.5 ${className}`}
    >
      <ShieldCheck className="size-3 shrink-0 text-emerald-600" />
      <span>SỐ LIỆU ĐÃ KIỂM CHỨNG</span>
    </Badge>
  );
}
