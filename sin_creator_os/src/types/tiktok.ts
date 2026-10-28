export interface TikTokChannel {
  id: string;
  username: string;
  displayName: string;
  avatarUrl: string;
  bio: string;
  followersCount: number | null;
  followingCount: number | null;
  likesCount: number | null;
  videoCount: number | null;
  engagementRate: number | null;
  connectedAt: string;
  status: 'connected' | 'expired' | 'error';
  niche: string;
  primaryAudience: string;
  region: string;
}

export interface ChannelMetricPoint {
  date: string;
  views: number;
  followers: number;
  engagementRate: number;
  watchTimeSec: number;
  completionRate: number;
}

export interface AudienceDemographic {
  ageGroups: { bracket: string; percentage: number }[];
  genderSplit: { male: number; female: number; other: number };
  topLocations: { country: string; percentage: number }[];
  activeHours: { hour: number; activityLevel: number }[];
}

export interface ChannelKPIs {
  followers: { value: number | null; changePercent?: number };
  views: { value: number | null; changePercent?: number };
  engagement: { value: number | null; changePercent?: number };
  posts: { value: number | null; changePercent?: number };
  avgWatchTime: { value: number | null; changePercent?: number };
  growthRate: { value: number | null; changePercent?: number };
}
