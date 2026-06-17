export type Project = {
  id: string;
  name: string;
  description: string;
  target_task: string;
  languages: string;
  dataset_size: number;
  output_schema: string;
};

export type ModelProvider = {
  id: string;
  name: string;
  endpoint: string;
  provider_type: "openai";
  api_key_secret: string;
};

export type ModelConfig = {
  id: string;
  role: "Generator" | "Judge" | "Validator" | "Embedding";
  alias: string;
  model: string;
  endpoint: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  parallel: number;
};

export type ColumnConfig = {
  id: string;
  type: "Sampler" | "Generated Column" | "Derived Column" | "Retrieval Column" | "Judge Score" | "Static";
  name: string;
  depends: string;
  prompt: string;
};

export type PreviewRecord = {
  id: string;
  data: Record<string, unknown>;
  judge: string;
  status: "Approved" | "Needs review" | "Rejected";
};

export type Job = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  target_records?: number;
  completed_records?: number;
  samples_per_second?: number;
  acceptance_rate?: number;
  average_judge_score?: number;
  error?: string | null;
  records?: PreviewRecord[];
};

export type ReviewRecord = {
  id: string;
  title: string;
  detail: string;
  status: "Needs edit" | "Reject" | "Accept";
};

export type StudioState = {
  project: Project;
  model_providers: ModelProvider[];
  models: ModelConfig[];
  columns: ColumnConfig[];
  preview_records: PreviewRecord[];
  generation_job: Job | null;
  reviews: ReviewRecord[];
  analytics: {
    task_distribution: Record<string, number>;
    score_distribution: Record<string, number>;
    duplicate_groups: number;
    largest_cluster: string;
    diversity_score: number;
  };
  yaml: string;
};

const API_BASE = "/api/studio";

export async function studioFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path.replace(/^\/api/, "")}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function downloadUrl(path: string) {
  return `${API_BASE}${path.replace(/^\/api/, "")}`;
}
