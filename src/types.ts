export type Provenance = {
  source?: string;
  author?: string;
  license?: string;
  cloud_analysis?: boolean;
  training?: boolean;
  redistribution?: boolean;
};
export type PreparationJob = Pick<
  Job,
  "id" | "status" | "progress" | "message"
>;
export type Asset = {
  id: string;
  name: string;
  frames: number;
  duration: number;
  status: string;
  error?: string;
  provenance: Provenance;
  preparation_job: PreparationJob | null;
};
export type Moment = {
  id: string;
  asset_id: string;
  start_frame: number;
  end_frame: number;
  description: string;
  source: string;
  uncertainty?: string;
  score?: number;
};
export type Selection = {
  id: string;
  asset_id: string;
  moment_id: string | null;
  start_frame: number;
  end_frame: number;
  note: string;
};
export type Section = {
  id: string;
  title: string;
  purpose: string;
  selections: Selection[];
};
export type ProposalSection = {
  title: string;
  purpose: string;
  candidate_ids: string[];
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  message: string;
  result: null | {
    url?: string;
    sections?: ProposalSection[];
    candidate_ids?: string[];
    explanation?: string;
    diagnostics?: {
      version: 1;
      stages: Record<
        string,
        | { status: "running" }
        | { status: "complete"; elapsed_seconds: number; output_bytes: number | null }
        | {
            status: "failed" | "cancelled";
            elapsed_seconds: number;
            error_type: string;
          }
      >;
      render_parts?: {
        status: "running" | "complete" | "failed" | "cancelled";
        attempted_parts: number;
        completed_parts: number;
        elapsed_seconds: number;
        output_bytes: number;
        max_part_seconds: number;
        slowest_parts: {
          index: number;
          elapsed_seconds: number;
          output_bytes: number | null;
        }[];
        failed_part: number | null;
        failed_part_seconds?: number;
      };
    };
  };
};
export type Project = {
  id: string;
  name: string;
  brief: string;
  revision: number;
  board: Section[];
  assets: Asset[];
  moments: Moment[];
  jobs: Job[];
};
export type Status = {
  ai_ready: boolean;
  key_present: boolean;
  pricing_confirmed: boolean;
  model: string;
  spend: number;
  limit: number;
  ffmpeg: boolean;
};
