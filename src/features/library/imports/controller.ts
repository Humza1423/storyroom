import type { Asset } from "../../../types";
import { ApiError, type api } from "../../../lib/api";

export type ImportResult = {
  id: string;
  job_id: string | null;
  duplicate: boolean;
};
export type UploadRow = {
  id: string;
  name: string;
  file?: File;
  state: "waiting" | "uploading" | "accepted" | "rejected" | "uncertain";
  assetId?: string;
  jobId?: string | null;
  duplicate?: boolean;
  message?: string;
};
export type ImportBatch = {
  id: string;
  projectId: string;
  projectName: string;
  paused: boolean;
  reason?: string;
  rows: UploadRow[];
};
type Snapshot = {
  batches: ImportBatch[];
  busy: boolean;
  owner: string | null;
  errors: Record<string, string>;
};
type Dependencies = {
  request: typeof api;
  refresh: (pid: string) => Promise<Asset[]>;
};

/** A mounted app owns one controller: no parallel uploads, even across projects.
 * Only server asset/job IDs are durable; File objects never leave browser memory.
 */
export class ImportController {
  private state: Snapshot = {
    batches: [],
    busy: false,
    owner: null,
    errors: {},
  };
  private listeners = new Set<() => void>();
  private disposed = false;
  constructor(private deps: Dependencies) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  dispose() {
    this.disposed = true;
    this.listeners.clear();
    this.state = { batches: [], busy: false, owner: null, errors: {} };
  }
  private publish(patch: Partial<Snapshot>) {
    if (this.disposed) return;
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }
  private batch(id: string) {
    return this.state.batches.find((b) => b.id === id);
  }
  private change(id: string, update: (batch: ImportBatch) => ImportBatch) {
    this.publish({
      batches: this.state.batches.map((b) => (b.id === id ? update(b) : b)),
    });
  }
  private row(batchId: string, rowId: string, patch: Partial<UploadRow>) {
    this.change(batchId, (b) => ({
      ...b,
      rows: b.rows.map((r) => (r.id === rowId ? { ...r, ...patch } : r)),
    }));
  }
  private pause(id: string, reason: string) {
    this.change(id, (b) => ({ ...b, paused: true, reason }));
  }
  private async reconcile(batchId: string) {
    const batch = this.batch(batchId);
    if (!batch || this.disposed) return;
    const assets = await this.deps.refresh(batch.projectId);
    // Never infer success by filename: uncertain rows without an ID stay uncertain.
    this.change(batchId, (b) => ({
      ...b,
      rows: b.rows.map((r) => {
        const asset = assets.find((a) => a.id === r.assetId);
        return asset
          ? { ...r, jobId: asset.preparation_job?.id ?? r.jobId }
          : r;
      }),
    }));
  }
  async start(projectId: string, projectName: string, files: File[]) {
    if (this.disposed || this.state.busy || !files.length) return;
    const batch: ImportBatch = {
      id: crypto.randomUUID(),
      projectId,
      projectName,
      paused: false,
      rows: files.map((file) => ({
        id: crypto.randomUUID(),
        name: file.name,
        file,
        state: "waiting",
      })),
    };
    this.publish({ batches: [...this.state.batches, batch] });
    return this.run(batch.id);
  }
  async resume(batchId: string) {
    if (this.disposed || this.state.busy || !this.batch(batchId)) return;
    this.change(batchId, (b) => ({ ...b, paused: false, reason: undefined }));
    await this.run(batchId);
  }
  async retryUpload(batchId: string, rowId: string) {
    if (this.disposed || this.state.busy) return;
    const row = this.batch(batchId)?.rows.find((r) => r.id === rowId);
    if (!row?.file || !["rejected", "uncertain"].includes(row.state)) return;
    this.row(batchId, rowId, { state: "waiting", message: undefined });
    // Retry only this file. Waiting files still require an explicit Resume.
    await this.run(batchId, rowId);
  }
  clear(batchId: string) {
    if (this.state.busy) return;
    // Drops File references; this method never makes a delete request.
    this.publish({
      batches: this.state.batches.filter((b) => b.id !== batchId),
    });
  }
  private async run(batchId: string, onlyRow?: string) {
    const projectId = this.batch(batchId)?.projectId;
    if (!projectId || this.disposed || this.state.busy) return;
    // Keep identifiers across awaits, not a second snapshot retaining every File.
    const rowIds = this.batch(batchId)!.rows.map((row) => row.id);
    this.publish({ busy: true, owner: projectId });
    try {
      for (const rowId of rowIds) {
        if (this.disposed) break;
        if (onlyRow ? rowId !== onlyRow : this.batch(batchId)?.paused) continue;
        const row = this.batch(batchId)?.rows.find((r) => r.id === rowId);
        if (row?.state !== "waiting" || !row.file) continue;
        this.row(batchId, row.id, { state: "uploading" });
        const data = new FormData();
        data.append("file", row.file);
        try {
          const result = await this.deps.request<ImportResult>(
            `/projects/${projectId}/import`,
            "POST",
            data,
          );
          if (
            typeof result.id !== "string" ||
            !result.id ||
            typeof result.duplicate !== "boolean"
          )
            throw new ApiError("Upload response was incomplete.", 0);
          this.row(batchId, row.id, {
            state: "accepted",
            assetId: result.id,
            jobId: result.job_id,
            duplicate: result.duplicate,
            file: undefined,
            message: undefined,
          });
        } catch (error) {
          const definiteFileError =
            error instanceof ApiError &&
            error.scope === "file" &&
            ["file_invalid", "file_too_large"].includes(error.code || "") &&
            !error.uncertain;
          const uncertain = !(error instanceof ApiError) || error.uncertain;
          const message =
            error instanceof Error
              ? error.message
              : "Upload could not be confirmed.";
          this.row(batchId, row.id, {
            state: uncertain ? "uncertain" : "rejected",
            message,
            file: definiteFileError ? undefined : row.file,
          });
          if (!definiteFileError) this.pause(batchId, message);
        }
        if (this.disposed) break;
        try {
          await this.reconcile(batchId);
        } catch {
          this.pause(
            batchId,
            "Could not refresh this project's saved footage. Check the server before resuming.",
          );
        }
        if (this.batch(batchId)?.paused && !onlyRow) break;
      }
    } finally {
      if (this.batch(batchId)?.rows.every((row) => !row.file)) {
        this.change(batchId, (batch) => ({
          ...batch,
          paused: false,
          reason: undefined,
        }));
      }
      this.publish({ busy: false, owner: null });
    }
  }
  async retryPreparation(projectId: string, assetId: string) {
    if (this.disposed || this.state.busy) return;
    this.publish({
      busy: true,
      owner: projectId,
      errors: { ...this.state.errors, [projectId]: "" },
    });
    try {
      const assets = await this.deps.refresh(projectId);
      if (this.disposed) return;
      const asset = assets.find((a) => a.id === assetId);
      const job = asset?.preparation_job;
      if (!asset || !job)
        throw new Error(
          "No preparation job found. Refresh the project and check Processing.",
        );
      if (
        asset.status !== "ready" &&
        ["failed", "cancelled"].includes(job.status)
      ) {
        const result = await this.deps.request<{ job_id: string }>(
          `/jobs/${job.id}/retry`,
          "POST",
        );
        this.publish({
          batches: this.state.batches.map((b) =>
            b.projectId !== projectId
              ? b
              : {
                  ...b,
                  rows: b.rows.map((r) =>
                    r.assetId === assetId ? { ...r, jobId: result.job_id } : r,
                  ),
                },
          ),
        });
      }
      if (!this.disposed) await this.deps.refresh(projectId);
    } catch (error) {
      this.publish({
        errors: {
          ...this.state.errors,
          [projectId]:
            error instanceof Error
              ? error.message
              : "Preparation retry failed.",
        },
      });
    } finally {
      this.publish({ busy: false, owner: null });
    }
  }
}
