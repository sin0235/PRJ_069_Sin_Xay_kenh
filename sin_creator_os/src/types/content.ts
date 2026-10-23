export type EvidenceSourceType =
  | 'tiktok_video'
  | 'competitor_post'
  | 'trend_audio'
  | 'hashtag_spike'
  | 'creator_analysis';

export interface EvidenceSource {
  id: string;
  sourceType: EvidenceSourceType;
  sourceUrl: string;
  sourceName: string;
  author: string;
  authorAvatar?: string;
  authorFollowers?: number;
  collectedAt: string;
  publishedAt: string;
  metricsSnapshot: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
    engagementRate: number;
    completionRate?: number;
    watchTimeSec?: number;
  };
  confidence: number; // 0-100%
  reason: string;
}

export type ContentStatus =
  | 'idea'
  | 'script'
  | 'production'
  | 'review'
  | 'scheduled'
  | 'published';

export type ContentBadge =
  | 'trending'
  | 'high_engagement'
  | 'fast_growth'
  | 'evergreen';

export interface ContentItem {
  id: string;
  title: string;
  caption: string;
  thumbnailUrl: string;
  videoUrl?: string;
  channelId: string;
  channelName: string;
  channelAvatar: string;
  status: ContentStatus;
  publishDate?: string;
  durationSec: number;
  contentPillar: string;
  hook: string;
  isAiGenerated: boolean;
  badges: ContentBadge[];
  metrics?: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
    engagementRate: number;
    watchTimeSec: number;
    completionRate: number;
  };
  evidence: EvidenceSource[];
  detectedTopic: string;
  audienceSignal: string;
  growthVelocity: string;
  soundName?: string;
  hashtags?: string[];
}

export interface ContentAnalysisReport {
  contentId: string;
  title: string;
  creator: {
    username: string;
    avatar: string;
    followers: number;
    niche: string;
  };
  metrics: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
    engagementRate: number;
    completionRate: number;
    watchTimeSec: number;
  };
  hookAnalysis: {
    type: string;
    text: string;
    visualOpening: string;
    dropoffRateAt3s: number;
    hookScore: number;
  };
  structureBreakdown: {
    section: 'Hook' | 'Setup' | 'Core Value' | 'Proof' | 'Call to Action';
    timestamp: string;
    retentionEstimate: number;
    description: string;
  }[];
  aiBreakdown: {
    topic: string;
    format: string;
    storyStructure: string;
    cta: string;
    emotion: string;
    targetAudience: string;
    editingStyle: string;
    videoLength: string;
    speechPaceWpm: number;
  };
  whyItWorks: string[];
  reusablePatterns: {
    patternName: string;
    category: 'hook' | 'format' | 'storytelling' | 'cta';
    formula: string;
    practicalExample: string;
  }[];
}
