"use client";

import * as React from "react";
import { cn } from "cn";
import {
  easeOutExpo,
  calculateTiltAngles,
  generateVectorConfettiParticles,
  type ConfettiParticle,
  type ConfettiShape,
} from "../../lib/motion-math";

export { easeOutExpo, calculateTiltAngles, generateVectorConfettiParticles };
export type { ConfettiParticle, ConfettiShape };

/**
 * 1. SpotlightCard: Thẻ có hào quang ánh sáng bám theo con trỏ chuột
 */
export interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  spotlightColor?: string;
  spotlightSize?: number;
  borderGlow?: boolean;
}

export function SpotlightCard({
  children,
  className,
  spotlightColor = "rgba(43, 111, 184, 0.16)",
  spotlightSize = 350,
  borderGlow = true,
  ...props
}: SpotlightCardProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [position, setPosition] = React.useState<{ x: number; y: number }>({ x: -1000, y: -1000 });
  const [opacity, setOpacity] = React.useState<number>(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setPosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseEnter = () => setOpacity(1);
  const handleMouseLeave = () => setOpacity(0);

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "relative rounded-xl border border-border bg-card text-card-foreground shadow-xs overflow-hidden transition-all duration-300",
        className
      )}
      {...props}
    >
      {/* Lớp hào quang theo chuột */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(${spotlightSize}px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 75%)`,
        }}
      />
      {borderGlow && (
        <div
          className="pointer-events-none absolute inset-0 rounded-xl transition-opacity duration-300 border border-primary/20"
          style={{
            opacity,
            maskImage: `radial-gradient(${spotlightSize * 0.75}px circle at ${position.x}px ${position.y}px, black, transparent 80%)`,
            WebkitMaskImage: `radial-gradient(${spotlightSize * 0.75}px circle at ${position.x}px ${position.y}px, black, transparent 80%)`,
          }}
        />
      )}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

/**
 * 2. BorderBeam: Đường tia sáng laser chuyển động bao quanh viền thẻ (SVG Vector Driven)
 */
export interface BorderBeamProps {
  className?: string;
  size?: number;
  duration?: number;
  colorFrom?: string;
  colorTo?: string;
  borderWidth?: number;
  anchor?: number;
}

export function BorderBeam({
  className,
  size = 200,
  duration = 10,
  colorFrom = "#2b6fb8",
  colorTo = "#60a5fa",
  borderWidth = 1.5,
}: BorderBeamProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 rounded-[inherit] overflow-hidden border border-transparent [mask-clip:padding-box,border-box] [mask-composite:intersect] [mask:linear-gradient(transparent,transparent),linear-gradient(white,white)]",
        className
      )}
    >
      <div
        className="absolute aspect-square bg-gradient-to-l from-[var(--color-from)] via-[var(--color-to)] to-transparent"
        style={
          {
            width: `${size}px`,
            offsetPath: `rect(0 auto auto 0 round calc(var(--radius, 12px) - ${borderWidth}px))`,
            animation: `border-beam ${duration}s infinite linear`,
            "--color-from": colorFrom,
            "--color-to": colorTo,
          } as React.CSSProperties
        }
      />
    </div>
  );
}

/**
 * 3. TiltCard: Thẻ tương tác 3D nghiêng theo góc độ con trỏ chuột kèm phản quang Glare
 */
export interface TiltCardProps extends React.HTMLAttributes<HTMLDivElement> {
  maxTilt?: number;
  glare?: boolean;
  scale?: number;
}

export function TiltCard({
  children,
  className,
  maxTilt = 8,
  glare = true,
  scale = 1.015,
  ...props
}: TiltCardProps) {
  const cardRef = React.useRef<HTMLDivElement>(null);
  const [style, setStyle] = React.useState<React.CSSProperties>({});
  const [glareStyle, setGlareStyle] = React.useState<React.CSSProperties>({ opacity: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const { tiltX, tiltY, percentageX, percentageY } = calculateTiltAngles(
      mouseX,
      mouseY,
      rect.width,
      rect.height,
      maxTilt
    );

    setStyle({
      transform: `perspective(1000px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg) scale3d(${scale}, ${scale}, ${scale})`,
      transition: "transform 0.1s ease-out",
    });

    if (glare) {
      const glareAngle = Math.atan2(percentageY, percentageX) * (180 / Math.PI) - 90;
      setGlareStyle({
        opacity: 0.18,
        background: `linear-gradient(${glareAngle}deg, rgba(255,255,255,0.7) 0%, transparent 70%)`,
        transition: "opacity 0.2s ease-out",
      });
    }
  };

  const handleMouseLeave = () => {
    setStyle({
      transform: "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)",
      transition: "transform 0.45s cubic-bezier(0.16, 1, 0.3, 1)",
    });
    setGlareStyle({
      opacity: 0,
      transition: "opacity 0.45s ease-out",
    });
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={style}
      className={cn(
        "relative rounded-xl border border-border bg-card text-card-foreground shadow-xs preserve-3d will-change-transform",
        className
      )}
      {...props}
    >
      {glare && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-xl z-20 overflow-hidden"
          style={glareStyle}
        />
      )}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

/**
 * 4. NumberTicker: Bộ đếm số chuyển động lăn mượt (Exponential Easing)
 */
export interface NumberTickerProps {
  value: number;
  duration?: number; // giây
  delay?: number; // giây
  decimalPlaces?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

export function NumberTicker({
  value,
  duration = 1.6,
  delay = 0,
  decimalPlaces = 0,
  prefix = "",
  suffix = "",
  className,
}: NumberTickerProps) {
  const [displayValue, setDisplayValue] = React.useState<number>(0);
  const startTimeRef = React.useRef<number | null>(null);
  const frameRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const startAnimation = () => {
      startTimeRef.current = null;

      const step = (timestamp: number) => {
        if (!startTimeRef.current) startTimeRef.current = timestamp;
        const elapsed = (timestamp - startTimeRef.current) / 1000;
        const progress = Math.min(1, elapsed / duration);
        const easedProgress = easeOutExpo(progress);
        const currentVal = easedProgress * value;

        setDisplayValue(currentVal);

        if (progress < 1) {
          frameRef.current = requestAnimationFrame(step);
        } else {
          setDisplayValue(value);
        }
      };

      frameRef.current = requestAnimationFrame(step);
    };

    if (delay > 0) {
      timeoutId = setTimeout(startAnimation, delay * 1000);
    } else {
      startAnimation();
    }

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration, delay]);

  const formatted = React.useMemo(() => {
    return new Intl.NumberFormat("vi-VN", {
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
    }).format(displayValue);
  }, [displayValue, decimalPlaces]);

  return (
    <span className={cn("inline-block tabular-nums font-semibold tracking-tight", className)}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}

/**
 * 5. InfiniteMarquee: Dải băng chuyền vô tận trôi mượt với tính năng tạm dừng khi hover
 */
export interface InfiniteMarqueeProps {
  children: React.ReactNode;
  pauseOnHover?: boolean;
  reverse?: boolean;
  speed?: "slow" | "normal" | "fast";
  className?: string;
}

export function InfiniteMarquee({
  children,
  pauseOnHover = true,
  reverse = false,
  speed = "normal",
  className,
}: InfiniteMarqueeProps) {
  const speedClass =
    speed === "fast"
      ? "animate-marquee-fast"
      : reverse
      ? "animate-marquee-reverse"
      : "animate-marquee";

  return (
    <div
      className={cn(
        "group flex overflow-hidden select-none gap-4 [mask-image:linear-gradient(to_right,transparent,white_10%,white_90%,transparent)]",
        className
      )}
    >
      <div
        className={cn(
          "flex min-w-full shrink-0 items-center justify-around gap-4",
          speedClass,
          pauseOnHover && "group-hover:[animation-play-state:paused]"
        )}
      >
        {children}
      </div>
      <div
        aria-hidden="true"
        className={cn(
          "flex min-w-full shrink-0 items-center justify-around gap-4",
          speedClass,
          pauseOnHover && "group-hover:[animation-play-state:paused]"
        )}
      >
        {children}
      </div>
    </div>
  );
}

/**
 * 6. ShimmerButton: Nút bấm sang trọng với dải lụa sáng quét góc chéo
 */
export interface ShimmerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  shimmerColor?: string;
  variant?: "primary" | "secondary" | "outline";
}

export function ShimmerButton({
  children,
  className,
  shimmerColor = "rgba(255, 255, 255, 0.35)",
  variant = "primary",
  disabled,
  ...props
}: ShimmerButtonProps) {
  const variantStyles = {
    primary: "bg-primary text-primary-foreground hover:bg-primary/95 shadow-md shadow-primary/20",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    outline: "border border-border bg-background hover:bg-muted text-foreground",
  };

  return (
    <button
      disabled={disabled}
      className={cn(
        "relative inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 overflow-hidden active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none cursor-pointer",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {!disabled && (
        <span
          aria-hidden="true"
          className="absolute inset-0 -translate-x-full animate-shimmer"
          style={{
            background: `linear-gradient(90deg, transparent 0%, ${shimmerColor} 50%, transparent 100%)`,
          }}
        />
      )}
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </button>
  );
}

/**
 * 7. VectorConfetti: Pháo hoa hạt vector hình học SVG (100% tuân thủ nguyên tắc không dùng emoji)
 */
let activeConfettiTrigger: ((origin?: { x: number; y: number }) => void) | null = null;

export function triggerGlobalVectorConfetti(origin?: { x: number; y: number }) {
  if (activeConfettiTrigger) {
    activeConfettiTrigger(origin);
  }
}

export function VectorConfettiCanvas() {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let particles: ConfettiParticle[] = [];
    let animationFrameId: number | null = null;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    const drawParticle = (p: ConfettiParticle) => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((p.rotation * Math.PI) / 180);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = Math.max(0, p.opacity);

      if (p.shape === "circle") {
        ctx.beginPath();
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.shape === "diamond") {
        ctx.beginPath();
        ctx.moveTo(0, -p.size);
        ctx.lineTo(p.size * 0.6, 0);
        ctx.lineTo(0, p.size);
        ctx.lineTo(-p.size * 0.6, 0);
        ctx.closePath();
        ctx.fill();
      } else if (p.shape === "ribbon") {
        ctx.fillRect(-p.size * 0.75, -p.size * 0.25, p.size * 1.5, p.size * 0.5);
      } else if (p.shape === "star") {
        // Vẽ sao vector 4 cánh
        ctx.beginPath();
        for (let i = 0; i < 4; i++) {
          const armAngle = (i * Math.PI) / 2;
          ctx.lineTo(Math.cos(armAngle) * p.size, Math.sin(armAngle) * p.size);
          const innerAngle = armAngle + Math.PI / 4;
          ctx.lineTo(Math.cos(innerAngle) * (p.size * 0.35), Math.sin(innerAngle) * (p.size * 0.35));
        }
        ctx.closePath();
        ctx.fill();
      }

      ctx.restore();
    };

    const loop = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.22; // Trọng lực nhẹ
        p.vx *= 0.98; // Ma sát không khí
        p.rotation += p.rotationSpeed;
        p.opacity -= p.decay;

        if (p.opacity <= 0 || p.y > canvas.height + 20) {
          particles.splice(i, 1);
        } else {
          drawParticle(p);
        }
      }

      if (particles.length > 0) {
        animationFrameId = requestAnimationFrame(loop);
      }
    };

    activeConfettiTrigger = (origin) => {
      const startX = origin?.x ?? canvas.width / 2;
      const startY = origin?.y ?? canvas.height / 3;
      const newParticles = generateVectorConfettiParticles(startX, startY, 70);
      particles = [...particles, ...newParticles];

      if (!animationFrameId || particles.length === newParticles.length) {
        cancelAnimationFrame(animationFrameId!);
        animationFrameId = requestAnimationFrame(loop);
      }
    };

    return () => {
      activeConfettiTrigger = null;
      window.removeEventListener("resize", resizeCanvas);
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-50 select-none"
      aria-hidden="true"
    />
  );
}

/**
 * 8. ParticleConstellationCanvas: Nền mạng lưới hạt sao kết nối tương tác đa điểm
 */
export interface ParticleConstellationCanvasProps {
  particleCount?: number;
  maxDistance?: number;
  className?: string;
  particleColor?: string;
  lineColor?: string;
}

export function ParticleConstellationCanvas({
  particleCount = 35,
  maxDistance = 110,
  className,
  particleColor = "rgba(43, 111, 184, 0.45)",
  lineColor = "rgba(43, 111, 184, 0.12)",
}: ParticleConstellationCanvasProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = container.clientWidth);
    let height = (canvas.height = container.clientHeight);
    let animationFrameId: number;

    const mouse = { x: -1000, y: -1000 };

    interface NodeParticle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
    }

    const nodes: NodeParticle[] = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.7,
      vy: (Math.random() - 0.5) * 0.7,
      radius: 1.5 + Math.random() * 1.5,
    }));

    const handleResize = () => {
      if (!container || !canvas) return;
      width = canvas.width = container.clientWidth;
      height = canvas.height = container.clientHeight;
    };

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };

    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    window.addEventListener("resize", handleResize);
    container.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("mouseleave", handleMouseLeave);

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Cập nhật và vẽ các hạt
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 0 || node.x > width) node.vx *= -1;
        if (node.y < 0 || node.y > height) node.vy *= -1;

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fillStyle = particleColor;
        ctx.fill();

        // Nối dây giữa các hạt gần nhau
        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j];
          const dx = other.x - node.x;
          const dy = other.y - node.y;
          const dist = Math.hypot(dx, dy);

          if (dist < maxDistance) {
            ctx.beginPath();
            ctx.moveTo(node.x, node.y);
            ctx.lineTo(other.x, other.y);
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 1 - dist / maxDistance;
            ctx.stroke();
          }
        }

        // Tương tác hút nhẹ với con trỏ chuột
        const dmx = mouse.x - node.x;
        const dmy = mouse.y - node.y;
        const distMouse = Math.hypot(dmx, dmy);
        if (distMouse < maxDistance * 1.3) {
          ctx.beginPath();
          ctx.moveTo(node.x, node.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.strokeStyle = "rgba(43, 111, 184, 0.25)";
          ctx.lineWidth = 1.2 - distMouse / (maxDistance * 1.3);
          ctx.stroke();
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      container.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, [particleCount, maxDistance, particleColor, lineColor]);

  return (
    <div ref={containerRef} className={cn("absolute inset-0 overflow-hidden pointer-events-auto", className)}>
      <canvas ref={canvasRef} className="block w-full h-full" />
    </div>
  );
}
