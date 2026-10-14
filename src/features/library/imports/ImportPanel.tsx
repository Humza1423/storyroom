import { useSyncExternalStore } from "react";
import type { Asset } from "../../../types";
import { ImportController } from "./controller";
import { preparationState, rowStatus } from "./presentation";

export function ImportPanel({
  controller,
  projectId,
  assets,
}: {
  controller: ImportController;
  projectId: string;
  assets: Asset[];
}) {
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
  );
  const batches = state.batches.filter((b) => b.projectId === projectId);
  const visibleIds = new Set(
    batches.flatMap((b) => b.rows.map((r) => r.assetId)),
  );
  const retry = (asset: Asset) => (
    <button
      className="text-button"
      disabled={state.busy}
      onClick={() => void controller.retryPreparation(projectId, asset.id)}
    >
      Retry preparation
    </button>
  );
  return (
    <section className="import-panel" aria-label="Import outcomes">
      <p className="subtle">
        Registered clips stay saved. Waiting files and upload outcomes are kept
        only in this tab; after reload, select any unuploaded files again.
      </p>
      {state.busy && state.owner !== projectId && (
        <p role="status">
          An upload or retry is continuing for another project. Return there to
          see its outcomes.
        </p>
      )}
      {state.errors[projectId] && <p role="alert">{state.errors[projectId]}</p>}
      {batches.map((batch) => (
        <div className="import-batch" key={batch.id}>
          <div role="status" aria-label="Batch summary">
            {batch.rows.filter((r) => r.state === "accepted").length} uploads
            accepted · {batch.rows.filter((r) => r.state === "rejected").length}{" "}
            rejected ·{" "}
            {batch.rows.filter((r) => r.state === "uncertain").length}{" "}
            unconfirmed ·{" "}
            {batch.rows.filter((r) => r.state === "waiting").length} waiting ·{" "}
            {batch.rows.filter((r) => r.state === "uploading").length} uploading
            {batch.paused && <p>Batch paused. {batch.reason}</p>}
          </div>
          <ul>
            {batch.rows.map((row) => {
              const asset = assets.find((a) => a.id === row.assetId);
              return (
                <li className="import-row" key={row.id}>
                  <strong>{row.name}</strong>
                  <span>{rowStatus(row, assets)}</span>
                  {row.duplicate && (
                    <span className="duplicate-badge">Already imported</span>
                  )}
                  {row.message && <p>{row.message}</p>}
                  {row.state === "uncertain" && (
                    <p>
                      Check saved footage. Retry upload checks the file's
                      content for duplicates; filenames do not confirm success.
                    </p>
                  )}
                  {["rejected", "uncertain"].includes(row.state) &&
                    (row.file ? (
                      <button
                        className="text-button"
                        disabled={state.busy}
                        onClick={() =>
                          void controller.retryUpload(batch.id, row.id)
                        }
                      >
                        Retry upload
                      </button>
                    ) : (
                      <small>
                        Select a corrected supported file to try again.
                      </small>
                    ))}
                  {asset && preparationState(asset) === "failed" && (
                    <>
                      <p>{asset.error || asset.preparation_job?.message}</p>
                      {retry(asset)}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
          {batch.paused && batch.rows.some((r) => r.state === "waiting") && (
            <button
              className="secondary"
              disabled={state.busy}
              onClick={() => void controller.resume(batch.id)}
            >
              Resume remaining files
            </button>
          )}
          <button
            className="text-button"
            disabled={state.busy}
            onClick={() => controller.clear(batch.id)}
          >
            {batch.rows.some((r) => r.file)
              ? "Discard local queue and outcomes"
              : "Clear outcomes"}
          </button>
        </div>
      ))}
      {assets
        .filter(
          (a) => !visibleIds.has(a.id) && preparationState(a) === "failed",
        )
        .map((asset) => (
          <div className="import-row" key={asset.id}>
            <strong>{asset.name}</strong>
            <span>Preparation failed or cancelled</span>
            <p>{asset.error || asset.preparation_job?.message}</p>
            {retry(asset)}
          </div>
        ))}
    </section>
  );
}
