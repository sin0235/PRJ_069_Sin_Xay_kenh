export type AIJobType =
  | 'content_research'
  | 'idea_generation'
  | 'script_generation'
  | 'image_generation'
  | 'tts'
  | 'video_generation'
  | 'render';

export type AIJobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface AIJob {
  id: string;
  type: AIJobType;
  title: string;
  status: AIJobStatus;
  progress: number; // 0 - 100
  createdAt: string;
  completedAt?: string;
  error?: string;
  costCredits: number;
  meta?: Record<string, any>;
}
