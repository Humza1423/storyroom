import type { Asset } from "../../../types";
import type { UploadRow } from "./controller";

export function preparationState(
  asset: Asset,
): "ready" | "preparing" | "failed" | "unknown" {
  if (asset.status === "ready") return "ready";
  if (
    asset.status === "failed" ||
    ["failed", "cancelled"].includes(asset.preparation_job?.status || "")
  )
    return "failed";
  if (asset.status === "processing") return "preparing";
  return "unknown";
}
export function footageSummary(assets: Asset[]): string {
  if (!assets.length) return "No clips yet";
  const counts = { ready: 0, preparing: 0, failed: 0, unknown: 0 };
  assets.forEach((a) => counts[preparationState(a)]++);
  return Object.entries(counts)
    .filter(([, n]) => n)
    .map(([state, n]) => `${n} ${state}`)
    .join(" · ");
}
export function rowStatus(row: UploadRow, assets: Asset[]): string {
  if (row.state === "waiting") return "Waiting to upload";
  if (row.state === "uploading") return "Uploading";
  if (row.state === "uncertain")
    return "Upload unconfirmed — it may have reached the server";
  if (row.state === "rejected") return "Upload rejected";
  const asset = assets.find((a) => a.id === row.assetId);
  if (!asset) return "Registered — checking preparation";
  const state = preparationState(asset);
  return {
    ready: "Ready to use",
    preparing: "Preparing media",
    failed: "Preparation failed or cancelled",
    unknown: "Registered — preparation status unknown",
  }[state];
}
