import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Pause, Play, RotateCcw, Square } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";

export function CampaignDetailsPage() {
  const { id } = useParams();
  const campaignId = Number(id);
  const qc = useQueryClient();

  const { data: campaign, isLoading } = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => api.getCampaign(campaignId),
    enabled: Boolean(campaignId),
  });

  const { data: statusData } = useQuery({
    queryKey: ["campaign-status", campaignId],
    queryFn: () => api.getCampaignStatus(campaignId),
    enabled: Boolean(campaignId),
    refetchInterval: (query) => {
      const d: any = query.state.data;
      return d?.running ? 2000 : false;
    },
  });

  const ctrlMutation = useMutation({
    mutationFn: (action: "start" | "pause" | "resume" | "restart" | "cancel") => {
      if (action === "start") return api.startCampaign(campaignId);
      if (action === "pause") return api.pauseCampaign(campaignId);
      if (action === "resume") return api.resumeCampaign(campaignId);
      if (action === "restart") return api.restartCampaign(campaignId);
      return api.cancelCampaign(campaignId);
    },
    onSuccess: (_, action) => {
      toast.success(`Campaign ${action} requested`);
      qc.invalidateQueries({ queryKey: ["campaign", campaignId] });
      qc.invalidateQueries({ queryKey: ["campaign-status", campaignId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!campaign) {
    return <p className="text-sm text-slate-500">Campaign not found.</p>;
  }

  const st = statusData || {};
  const websites = st.websites || campaign.websites || [];
  const total = Number(st.total ?? campaign.targets ?? websites.length ?? 0);
  const results = st.results || {};
  const processed = Number(results.processed ?? st.progress ?? 0);
  const remaining = Math.max(0, total - processed);
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

  const currentStatus = String(st.status || campaign.status || "draft").toLowerCase();
  const isRunning = Boolean(st.running) || ["queued", "running", "scraping", "clustering", "filling"].includes(currentStatus);
  const isPaused = currentStatus === "paused";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link to="/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 mb-1">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Campaigns
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{campaign.name}</h1>
            <StatusBadge status={currentStatus} />
          </div>
          {campaign.description && <p className="text-sm text-slate-500 mt-0.5">{campaign.description}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!isRunning && !isPaused && (
            <Button size="sm" onClick={() => ctrlMutation.mutate("start")} disabled={ctrlMutation.isPending}>
              <Play className="h-4 w-4" /> Start
            </Button>
          )}
          {isRunning && (
            <Button size="sm" variant="outline" onClick={() => ctrlMutation.mutate("pause")} disabled={ctrlMutation.isPending}>
              <Pause className="h-4 w-4" /> Pause
            </Button>
          )}
          {isPaused && (
            <Button size="sm" onClick={() => ctrlMutation.mutate("resume")} disabled={ctrlMutation.isPending}>
              <Play className="h-4 w-4" /> Resume
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => ctrlMutation.mutate("restart")} disabled={ctrlMutation.isPending || isRunning}>
            <RotateCcw className="h-4 w-4" /> Restart
          </Button>
          {isRunning && (
            <Button size="sm" variant="destructive" onClick={() => ctrlMutation.mutate("cancel")} disabled={ctrlMutation.isPending}>
              <Square className="h-4 w-4" /> Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Live Progress Card */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-6">
            <div>
              <p className="text-xs text-slate-500">Processed</p>
              <p className="text-xl font-semibold text-slate-900">{processed} / {total}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Remaining</p>
              <p className="text-xl font-semibold text-slate-900">{remaining}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Success</p>
              <p className="text-xl font-semibold text-emerald-600">{results.success ?? campaign.results_success ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Failed</p>
              <p className="text-xl font-semibold text-rose-600">{results.failed ?? campaign.results_failed ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">CAPTCHA</p>
              <p className="text-xl font-semibold text-amber-600">{results.captcha ?? campaign.results_captcha ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">No Form</p>
              <p className="text-xl font-semibold text-slate-600">{results.noform ?? 0}</p>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Overall Progress</span>
              <span>{pct}%</span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-blue-600 transition-all duration-300" style={{ width: `${pct}%` }} />
            </div>
          </div>

          {st.error && (
            <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              <strong>Run Error:</strong> {st.error}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Per-website live feed */}
      <Card>
        <CardHeader>
          <CardTitle>Target Websites ({websites.length})</CardTitle>
          <CardDescription>Real-time per-website processing status and error details.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50 text-left text-xs font-medium uppercase text-slate-500">
                <th className="px-3 py-2.5">#</th>
                <th className="px-3 py-2.5">Website URL</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Updated</th>
                <th className="px-3 py-2.5">Notes / Error</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {websites.map((w: any, idx: number) => (
                <tr key={w.id || idx} className="hover:bg-slate-50/70">
                  <td className="px-3 py-2.5 text-xs text-slate-400">{idx + 1}</td>
                  <td className="px-3 py-2.5 font-medium text-slate-800 max-w-xs truncate">{w.website_url}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={w.status || "pending"} /></td>
                  <td className="px-3 py-2.5 text-xs text-slate-500">{formatDate(w.processed_at)}</td>
                  <td className="px-3 py-2.5 text-xs text-slate-600 max-w-md truncate">{w.error || "—"}</td>
                </tr>
              ))}
              {websites.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-sm text-slate-400">No target websites in this campaign.</td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
