/**
 * Toán học và giải thuật chuyển động (Motion Math Primitives)
 * PRJ_069_Sin_Xay_kenh - Ponytail Minimalist
 */

export type ConfettiShape = "star" | "diamond" | "ribbon" | "circle";

export interface ConfettiParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  rotation: number;
  rotationSpeed: number;
  size: number;
  color: string;
  shape: ConfettiShape;
  opacity: number;
  decay: number;
}

export const BRAND_CONFETTI_COLORS = [
  "#2b6fb8", // primary blue
  "#60a5fa", // sky blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#f43f5e", // rose
];

/**
 * Hàm easing Exponential Out: tăng tốc cực nhanh ban đầu và hãm phanh mượt mà
 */
export function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

/**
 * Tính toán góc nghiêng 3D (Tilt) và tỉ lệ phần trăm tọa độ chuột so với kích thước khung
 */
export function calculateTiltAngles(
  mouseX: number,
  mouseY: number,
  width: number,
  height: number,
  maxTilt: number
): { tiltX: number; tiltY: number; percentageX: number; percentageY: number } {
  const percentageX = (mouseX / width) * 2 - 1; // -1 to 1
  const percentageY = (mouseY / height) * 2 - 1; // -1 to 1
  let tiltX = -(percentageY * maxTilt);
  let tiltY = percentageX * maxTilt;

  // Triệt tiêu -0 trong JavaScript
  if (Object.is(tiltX, -0)) tiltX = 0;
  if (Object.is(tiltY, -0)) tiltY = 0;

  return { tiltX, tiltY, percentageX, percentageY };
}

/**
 * Sinh danh sách hạt pháo hoa vector hình học (100% tuân thủ nguyên tắc không dùng emoji)
 * Bắn hình nón chếch lên trên (Upward celebratory fountain burst)
 */
export function generateVectorConfettiParticles(
  originX: number,
  originY: number,
  count = 60
): ConfettiParticle[] {
  const shapes: ConfettiShape[] = ["star", "diamond", "ribbon", "circle"];
  const particles: ConfettiParticle[] = [];

  for (let i = 0; i < count; i++) {
    // Góc bắn hướng lên trên (-90 độ kèm độ phân kỳ 140 độ)
    const angle = -Math.PI / 2 + ((i / count) - 0.5) * (Math.PI * 0.78) + (Math.random() - 0.5) * 0.2;
    const speed = 5 + Math.random() * 9;
    particles.push({
      x: originX,
      y: originY,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed, // Luôn âm (hướng lên trên)
      rotation: Math.random() * 360,
      rotationSpeed: (Math.random() - 0.5) * 14,
      size: 6 + Math.random() * 8,
      color: BRAND_CONFETTI_COLORS[Math.floor(Math.random() * BRAND_CONFETTI_COLORS.length)],
      shape: shapes[Math.floor(Math.random() * shapes.length)],
      opacity: 1,
      decay: 0.012 + Math.random() * 0.01,
    });
  }

  return particles;
}
