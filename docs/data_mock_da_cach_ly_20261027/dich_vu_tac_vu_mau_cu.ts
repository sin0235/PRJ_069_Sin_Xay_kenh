import { AIJob } from '@/types';
import { mockAIJobs } from '@/data/mock-creator-data';

export class JobService {
  private static jobs: AIJob[] = [...mockAIJobs];

  static async getJobs(): Promise<AIJob[]> {
    return Promise.resolve([...this.jobs]);
  }

  static async createJob(job: Omit<AIJob, 'id' | 'createdAt' | 'status' | 'progress'>): Promise<AIJob> {
    const newJob: AIJob = {
      ...job,
      id: `job_${Date.now()}`,
      status: 'queued',
      progress: 0,
      createdAt: new Date().toISOString(),
    };
    this.jobs.unshift(newJob);
    return Promise.resolve(newJob);
  }

  static async retryJob(id: string): Promise<boolean> {
    const job = this.jobs.find((j) => j.id === id);
    if (job) {
      job.status = 'processing';
      job.progress = 10;
      job.error = undefined;
      return Promise.resolve(true);
    }
    return Promise.resolve(false);
  }
}
