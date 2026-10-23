import { create } from 'zustand';
import { TikTokChannel } from '@/types';

const DEFAULT_REAL_CHANNELS: TikTokChannel[] = [
  {
    id: 'tiktok_tiktok',
    username: '@tiktok',
    displayName: 'TikTok',
    avatarUrl: 'https://p19-common-sign.tiktokcdn.com/tos-maliva-avt-0068/ba67b11de451691939223e9d978e613a~tplv-tiktokx-cropcenter:1080:1080.jpeg?dr=14579&refresh_token=4d8eded9&x-expires=1792821600&x-signature=%2FmKx6rmQJvr3Z1GQMNyiyk4xM8A%3D&t=4d5b0474&ps=13740610&shp=a5d48078&shcp=81f88b70&idc=my2',
    bio: 'Your next discovery is waiting on TikTok.',
    followersCount: 96400000,
    followingCount: 1,
    likesCount: 466000000,
    videoCount: 1513,
    engagementRate: 7.8,
    connectedAt: '2026-10-22',
    status: 'connected',
    niche: 'TikTok Official',
    primaryAudience: 'TikTok Community',
    region: 'VN',
  },
];

interface CreatorState {
  currentWorkspace: string;
  channels: TikTokChannel[];
  activeChannelId: string;
  isCreateModalOpen: boolean;
  createModalInitialTab: 'idea' | 'script' | 'video' | 'schedule';
  activeJobsCount: number;
  
  // Actions
  setWorkspace: (ws: string) => void;
  setChannels: (channels: TikTokChannel[]) => void;
  setActiveChannelId: (id: string) => void;
  openCreateModal: (tab?: 'idea' | 'script' | 'video' | 'schedule') => void;
  closeCreateModal: () => void;
  setActiveJobsCount: (count: number) => void;
}

export const useCreatorStore = create<CreatorState>((set) => ({
  currentWorkspace: 'default_ws',
  channels: DEFAULT_REAL_CHANNELS,
  activeChannelId: 'tiktok_tiktok',
  isCreateModalOpen: false,
  createModalInitialTab: 'idea',
  activeJobsCount: 2,
  
  setWorkspace: (ws) => set({ currentWorkspace: ws }),
  setChannels: (channels) => set({ channels, activeChannelId: channels[0]?.id || 'tiktok_tiktok' }),
  setActiveChannelId: (id) => set({ activeChannelId: id }),
  openCreateModal: (tab = 'idea') => set({ isCreateModalOpen: true, createModalInitialTab: tab }),
  closeCreateModal: () => set({ isCreateModalOpen: false }),
  setActiveJobsCount: (count) => set({ activeJobsCount: count }),
}));
