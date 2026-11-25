import { Badge } from "@/components/ui/badge";

const STATUS_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" | "outline" }
> = {
  success: { label: "Success", variant: "success" },
  completed: { label: "Completed", variant: "success" },
  scraped: { label: "Form Found", variant: "success" },
  scanned: { label: "Scanned", variant: "default" },
  running: { label: "Running", variant: "default" },
  scraping: { label: "Scraping", variant: "default" },
  clustering: { label: "Clustering", variant: "default" },
  filling: { label: "Filling", variant: "default" },
  queued: { label: "Queued", variant: "secondary" },
  draft: { label: "Draft", variant: "secondary" },
  pending: { label: "Pending", variant: "secondary" },
  paused: { label: "Paused", variant: "warning" },
  captcha: { label: "CAPTCHA", variant: "warning" },
  unconfirmed: { label: "Manual Review", variant: "warning" },
  sent_unverified: { label: "Manual Review", variant: "warning" },
  noform: { label: "No Form", variant: "outline" },
  nofill: { label: "No Fill", variant: "outline" },
  failed: { label: "Failed", variant: "destructive" },
  error: { label: "Failed", variant: "destructive" },
  timeout: { label: "Timeout", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "outline" },
};

export function StatusBadge({ status }: { status?: string | null }) {
  const key = String(status || "pending").toLowerCase();
  const cfg = STATUS_MAP[key] || { label: key, variant: "outline" as const };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}
