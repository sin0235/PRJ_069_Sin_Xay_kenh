export type ScriptBlockType = 'HOOK' | 'SETUP' | 'VALUE' | 'PROOF' | 'CTA';

export interface ScriptBlock {
  id: string;
  type: ScriptBlockType;
  title: string;
  content: string;
  durationSec: number;
  visualCue: string;
  audioCue?: string;
}

export interface ScriptContext {
  ideaTitle: string;
  oneLineConcept: string;
  targetAudience: string;
  brandVoice: string;
  referenceLinks: { title: string; url: string; note: string }[];
  keyTakeaway: string;
}

export interface Script {
  id: string;
  ideaId?: string;
  title: string;
  niche: string;
  targetDurationSec: number;
  estimatedWpm: number;
  status: 'draft' | 'reviewed' | 'approved' | 'in_production';
  context: ScriptContext;
  blocks: ScriptBlock[];
  updatedAt: string;
}
