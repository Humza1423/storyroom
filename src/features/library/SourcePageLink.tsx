import { ExternalLink } from "lucide-react";

export function sourcePageHref(source?: string): string | null {
  if (!source?.trim()) return null;

  try {
    const url = new URL(source.trim());
    if (
      (url.protocol !== "http:" && url.protocol !== "https:") ||
      !url.hostname ||
      url.username ||
      url.password
    ) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

export function SourcePageLink({
  source,
  assetName,
}: {
  source?: string;
  assetName?: string;
}) {
  const href = sourcePageHref(source);
  if (!href) return null;

  return (
    <a
      className="asset-source-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open full video source${assetName ? ` for ${assetName}` : ""}`}
    >
      <ExternalLink size={12} aria-hidden="true" />
      Open full video source
    </a>
  );
}
