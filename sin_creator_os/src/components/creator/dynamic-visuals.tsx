"use client";

import * as React from "react";
import { cn } from "cn";
import { CheckCircle2, AlertCircle, Clock, RotateCw, Sparkles, Volume2 } from "lucide-react";

/**
 * 1. StatusBeacon: Chấm trạng thái đa tầng với vòng radar phát sóng động
 */
export interface StatusBeaconProps {
  status: "processing" | "queued" | "completed" | "failed" | "idle";
  size?: "sm" | "md" | "lg";
  className?: string;
  showIcon?: boolean;
}

export function StatusBeacon({
  status,
  size = "md",
  className,
  showIcon = false,
}: StatusBeaconProps) {
  const sizeClasses = {
    sm: "size-2",
    md: "size-2.5",
    lg: "size-3.5",
  };

  const containerSizes = {
    sm: "size-4",
    md: "size-5",
    lg: "size-7",
  };

  if (showIcon) {
    if (status === "processing") {
      return (
        <div className={cn("relative flex items-center justify-center", containerSizes[size], className)}>
          <span className="absolute inset-0 rounded-full bg-primary/25 animate-radar" />
          <RotateCw className={cn("text-primary animate-spin", size === "sm" ? "size-3" : size === "md" ? "size-4" : "size-5")} />
        </div>
      );
    }
    if (status === "queued") {
      return (
        <div className={cn("flex items-center justify-center text-amber-500", containerSizes[size], className)}>
          <Clock className={cn("animate-pulse", size === "sm" ? "size-3" : size === "md" ? "size-4" : "size-5")} />
        </div>
      );
    }
    if (status === "completed") {
      return (
        <div className={cn("flex items-center justify-center text-emerald-500", containerSizes[size], className)}>
          <CheckCircle2 className={size === "sm" ? "size-3" : size === "md" ? "size-4" : "size-5"} />
        </div>
      );
    }
    if (status === "failed") {
      return (
        <div className={cn("flex items-center justify-center text-destructive", containerSizes[size], className)}>
          <AlertCircle className={size === "sm" ? "size-3" : size === "md" ? "size-4" : "size-5"} />
        </div>
      );
    }
  }

  return (
    <div className={cn("relative inline-flex items-center justify-center", containerSizes[size], className)}>
      {status === "processing" && (
        <>
          <span className="absolute inset-0 rounded-full bg-primary/30 animate-radar" />
          <span className={cn("rounded-full bg-primary shadow-xs shadow-primary/50 relative z-10", sizeClasses[size])} />
        </>
      )}

      {status === "queued" && (
        <>
          <span className="absolute inset-0 rounded-full bg-amber-500/20 animate-ping opacity-60 duration-1000" />
          <span className={cn("rounded-full bg-amber-500 animate-pulse relative z-10", sizeClasses[size])} />
        </>
      )}

      {status === "completed" && (
        <span className={cn("rounded-full bg-emerald-500 shadow-xs shadow-emerald-500/40", sizeClasses[size])} />
      )}

      {status === "failed" && (
        <span className={cn("rounded-full bg-destructive shadow-xs shadow-destructive/40", sizeClasses[size])} />
      )}

      {status === "idle" && (
        <span className={cn("rounded-full bg-muted-foreground/40", sizeClasses[size])} />
      )}
    </div>
  );
}

/**
 * 2. SoundEqualizer: Cột sóng âm vector nhảy nhịp nhàng khi phát audio
 */
export interface SoundEqualizerProps {
  isPlaying?: boolean;
  colorClass?: string;
  className?: string;
  height?: number;
}

export function SoundEqualizer({
  isPlaying = false,
  colorClass = "bg-primary",
  className,
  height = 16,
}: SoundEqualizerProps) {
  return (
    <div
      className={cn("inline-flex items-end gap-0.5 select-none", className)}
      style={{ height: `${height}px` }}
      aria-label={isPlaying ? "Đang phát âm thanh" : "Đã tạm dừng âm thanh"}
    >
      <span
        className={cn(
          "w-1 rounded-full transition-all duration-300",
          colorClass,
          isPlaying ? "h-full animate-eq-1" : "h-[25%] opacity-50"
        )}
      />
      <span
        className={cn(
          "w-1 rounded-full transition-all duration-300",
          colorClass,
          isPlaying ? "h-full animate-eq-2" : "h-[45%] opacity-50"
        )}
      />
      <span
        className={cn(
          "w-1 rounded-full transition-all duration-300",
          colorClass,
          isPlaying ? "h-full animate-eq-3" : "h-[30%] opacity-50"
        )}
      />
      <span
        className={cn(
          "w-1 rounded-full transition-all duration-300",
          colorClass,
          isPlaying ? "h-full animate-eq-4" : "h-[60%] opacity-50"
        )}
      />
    </div>
  );
}

/**
 * 3. ShimmerProgressBar: Thanh tiến độ có dải sóng ánh sáng chuyển động
 */
export interface ShimmerProgressBarProps {
  value: number; // 0 - 100
  isProcessing?: boolean;
  heightClass?: string;
  className?: string;
}

export function ShimmerProgressBar({
  value,
  isProcessing = false,
  heightClass = "h-1.5",
  className,
}: ShimmerProgressBarProps) {
  const clampedValue = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("w-full bg-muted rounded-full overflow-hidden relative", heightClass, className)}>
      <div
        className="h-full bg-primary transition-all duration-500 ease-out rounded-full relative overflow-hidden"
        style={{ width: `${clampedValue}%` }}
      >
        {isProcessing && (
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/35 to-transparent animate-shimmer" />
        )}
      </div>
    </div>
  );
}

/**
 * 4. FloatingSparkleSVG: Biểu tượng 4 cánh sao SVG tỏa sáng vi mô
 */
export interface FloatingSparkleSVGProps {
  className?: string;
  size?: number;
}

export function FloatingSparkleSVG({ className, size = 16 }: FloatingSparkleSVGProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("animate-float hover:rotate-12 transition-transform duration-300", className)}
    >
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
      <polygon points="12 6 14 10 18 12 14 14 12 18 10 14 6 12 10 10" fill="currentColor" fillOpacity="0.2" />
    </svg>
  );
}
