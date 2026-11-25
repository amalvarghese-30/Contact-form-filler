import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_MAP: Record<
  string,
  {
    label: string;
    variant: "default" | "secondary" | "success" | "warning" | "destructive" | "outline";
    dotClass: string;
    pulse?: boolean;
  }
> = {
  success: { label: "Success", variant: "success", dotClass: "bg-emerald-500" },
  completed: { label: "Completed", variant: "success", dotClass: "bg-emerald-500" },
  scraped: { label: "Form Found", variant: "success", dotClass: "bg-emerald-500" },
  scanned: { label: "Scanned", variant: "default", dotClass: "bg-indigo-500" },
  running: { label: "Running", variant: "default", dotClass: "bg-indigo-500", pulse: true },
  scraping: { label: "Scraping", variant: "default", dotClass: "bg-indigo-500", pulse: true },
  clustering: { label: "Clustering", variant: "default", dotClass: "bg-indigo-500", pulse: true },
  filling: { label: "Filling", variant: "default", dotClass: "bg-indigo-500", pulse: true },
  queued: { label: "Queued", variant: "secondary", dotClass: "bg-slate-400" },
  draft: { label: "Draft", variant: "secondary", dotClass: "bg-slate-400" },
  pending: { label: "Pending", variant: "secondary", dotClass: "bg-slate-400" },
  paused: { label: "Paused", variant: "warning", dotClass: "bg-amber-500" },
  captcha: { label: "CAPTCHA", variant: "warning", dotClass: "bg-amber-500" },
  unconfirmed: { label: "Manual Review", variant: "warning", dotClass: "bg-amber-500" },
  sent_unverified: { label: "Manual Review", variant: "warning", dotClass: "bg-amber-500" },
  noform: { label: "No Form", variant: "outline", dotClass: "bg-slate-400" },
  nofill: { label: "No Fill", variant: "outline", dotClass: "bg-slate-400" },
  failed: { label: "Failed", variant: "destructive", dotClass: "bg-rose-500" },
  error: { label: "Failed", variant: "destructive", dotClass: "bg-rose-500" },
  timeout: { label: "Timeout", variant: "destructive", dotClass: "bg-rose-500" },
  cancelled: { label: "Cancelled", variant: "outline", dotClass: "bg-slate-400" },
};

export function StatusBadge({ status }: { status?: string | null }) {
  const key = String(status || "pending").toLowerCase();
  const cfg = STATUS_MAP[key] || { label: key, variant: "outline" as const, dotClass: "bg-slate-400" };
  return (
    <Badge variant={cfg.variant} className="gap-1.5 rounded-full px-2.5 py-0.5 font-medium">
      <span className={cn("h-1.5 w-1.5 rounded-full", cfg.dotClass, cfg.pulse && "animate-pulse")} />
      {cfg.label}
    </Badge>
  );
}
