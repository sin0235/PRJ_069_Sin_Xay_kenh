import {
  TikTokChannel,
  ChannelKPIs,
  ChannelMetricPoint,
  ContentItem,
  ContentAnalysisReport,
  ContentIdea,
  Script,
  AIJob,
  EvidenceSource,
} from '@/types';

export const mockChannels: TikTokChannel[] = [];

export const mockKPIs: ChannelKPIs = {
  followers: { value: 0, changePercent: 0 },
  views: { value: 0, changePercent: 0 },
  engagement: { value: 0, changePercent: 0 },
  posts: { value: 0, changePercent: 0 },
  avgWatchTime: { value: 0, changePercent: 0 },
  growthRate: { value: 0, changePercent: 0 },
};

export const mockGrowthData: ChannelMetricPoint[] = [];

export const mockAIRecommendations: Array<{
  id: string;
  category: string;
  title: string;
  description: string;
  impact: string;
  ctaAction: string;
  badge: string;
}> = [];

export const mockEvidences: EvidenceSource[] = [];

export const mockRecentVideos: ContentItem[] = [];

export const mockIdeas: ContentIdea[] = [];

export const mockScriptDetail: Script = {
  id: '',
  title: '',
  niche: '',
  targetDurationSec: 0,
  estimatedWpm: 140,
  status: 'draft',
  context: {
    ideaTitle: '',
    oneLineConcept: '',
    targetAudience: '',
    brandVoice: '',
    referenceLinks: [],
    keyTakeaway: '',
  },
  blocks: [],
  updatedAt: new Date().toISOString(),
};

export const mockContentAnalysis: ContentAnalysisReport = {
  contentId: '',
  title: '',
  creator: {
    username: '',
    avatar: '',
    followers: 0,
    niche: '',
  },
  metrics: {
    views: 0,
    likes: 0,
    comments: 0,
    shares: 0,
    engagementRate: 0,
    completionRate: 0,
    watchTimeSec: 0,
  },
  hookAnalysis: {
    type: '',
    text: '',
    visualOpening: '',
    dropoffRateAt3s: 0,
    hookScore: 0,
  },
  structureBreakdown: [],
  aiBreakdown: {
    topic: '',
    format: '',
    storyStructure: '',
    cta: '',
    emotion: '',
    targetAudience: '',
    editingStyle: '',
    videoLength: '',
    speechPaceWpm: 0,
  },
  whyItWorks: [],
  reusablePatterns: [],
};

export const mockAIJobs: AIJob[] = [];

export const mockTrends: Array<{
  id: string;
  title: string;
  type: string;
  momentum: string;
  views: string;
  sampleVideo: string;
  opportunityScore: number;
  description: string;
  stage: string;
  actionRecommendation: string;
}> = [];

export const mockCompetitors: Array<{
  id: string;
  channel: string;
  avatar: string;
  followers: string;
  growth: string;
  topPillars: string[];
  postingRate: string;
  avgViews: string;
  contentGaps: string[];
}> = [];
