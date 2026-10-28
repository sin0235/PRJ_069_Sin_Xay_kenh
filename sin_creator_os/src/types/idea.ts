import { EvidenceSource } from './content';

export type IdeaStatus =
  | 'draft'
  | 'validated'
  | 'ready_to_script'
  | 'in_script'
  | 'archived'
  | 'READY_FOR_REVIEW'
  | 'NEEDS_EVIDENCE'
  | 'APPROVED'
  | 'REJECTED'
  | 'DRAFT';

export interface IdeaScores {
  relevance?: number;
  trend?: number;
  audienceFit?: number;
  novelty?: number;
  productionDifficulty?: 'easy' | 'medium' | 'hard';
  overall?: number;
}

export interface ContentIdea {
  id: string;
  version?: number;
  title: string;
  oneLineConcept: string;
  hook: string;
  targetViewer: string;
  painOrDesire: string;
  contentAngle: string;
  videoStructure: {
    hook: string;
    setup: string;
    value: string;
    proof: string;
    cta: string;
  };
  cta: string;
  topic: string;
  contentPillar: string;
  audience: string;
  format?: 'Talking Head' | 'Tutorial / How-to' | 'POV / Skit' | 'Listicle' | 'Storytime' | 'Before / After' | 'Visual B-Roll';
  expectedObjective?: 'Reach & Awareness' | 'High Engagement' | 'Follower Conversion' | 'Link Clicks';
  status: IdeaStatus;
  createdBy: string;
  scores?: IdeaScores;
  freshness?: 'Breaking' | 'Rising' | 'Stable';
  estimatedProductionEffort: string;
  whyThisIdea: string;
  evidence: EvidenceSource[];
  relatedSuccessfulContent: {
    title: string;
    views: string;
    creator: string;
    url: string;
  }[];
  reviewerNotes?: string;
  reviewReason?: string;
  createdAt: string;
}

export interface IdeaReviewPayload {
  action: 'APPROVE' | 'REJECT' | 'REQUEST_EVIDENCE' | 'REOPEN';
  expected_status: string;
  expected_version: number;
  reviewer_notes?: string;
  review_reason?: string;
}

export interface IdeaGenerationConfig {
  niche: string;
  targetAudience?: string;
  channelObjective?: string;
  language?: string;
  country?: string;
  contentPillar?: string;
  tone?: string;
  videoLength?: string;
  targetLengthSec?: number;
  desiredQuantity?: number;
  dataSources?: {
    tiktokTrends?: boolean;
    competitorVideos?: boolean;
    savedResearch?: boolean;
    channelHistory?: boolean;
    manualReferences?: boolean;
  };
}
