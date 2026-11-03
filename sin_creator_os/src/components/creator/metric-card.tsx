"use client";

import * as React from "react";
import { TrendingUp, TrendingDown, LucideIcon } from "lucide-react";
import { SpotlightCard, NumberTicker } from "./motion-primitives";
import { cn } from "cn";

export interface MetricCardProps {
  title: string;
  value: string | number;
  numericValue?: number;
  decimalPlaces?: number;
  prefix?: string;
  suffix?: string;
  changePercent?: number;
  period?: string;
  icon?: LucideIcon;
  subtext?: string;
  className?: string;
}

export function MetricCard({
  title,
  value,
  numericValue,
  decimalPlaces = 0,
  prefix = "",
  suffix = "",
  changePercent,
  period = "so với 7 ngày trước",
  icon: Icon,
  subtext,
  className,
}: MetricCardProps) {
  const isPositive = (changePercent ?? 0) >= 0;

  return (
    <SpotlightCard
      className={cn(
        "rounded-2xl border-border/80 bg-card p-4 space-y-3 shadow-xs hover:border-primary/40 card-hover-lift transition-all",
        className
      )}
      spotlightColor="rgba(43, 111, 184, 0.12)"
      spotlightSize={260}
    >
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-xs font-medium tracking-tight line-clamp-1">{title}</span>
        {Icon && (
          <div className="size-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <Icon className="size-4" />
          </div>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-2xl font-bold tracking-tight text-foreground font-mono">
          {numericValue !== undefined ? (
            <NumberTicker
              value={numericValue}
              decimalPlaces={decimalPlaces}
              prefix={prefix}
              suffix={suffix}
              duration={1.5}
            />
          ) : typeof value === "number" ? (
            <NumberTicker value={value} decimalPlaces={decimalPlaces} duration={1.5} />
          ) : (
            value
          )}
        </div>

        {changePercent !== undefined && (
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={cn(
                "inline-flex items-center gap-0.5 font-semibold px-1.5 py-0.5 rounded-md",
                isPositive
                  ? "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                  : "text-rose-600 dark:text-rose-400 bg-rose-500/10"
              )}
            >
              {isPositive ? (
                <TrendingUp className="size-3 stroke-[2.5]" />
              ) : (
                <TrendingDown className="size-3 stroke-[2.5]" />
              )}
              {isPositive ? `+${changePercent}%` : `${changePercent}%`}
            </span>
            <span className="text-[11px] text-muted-foreground line-clamp-1">{period}</span>
          </div>
        )}

        {subtext && <div className="text-[11px] text-muted-foreground">{subtext}</div>}
      </div>
    </SpotlightCard>
  );
}
