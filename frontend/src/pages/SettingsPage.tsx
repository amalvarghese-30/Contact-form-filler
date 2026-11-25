import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";

export function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
  });

  const [headless, setHeadless] = React.useState(true);
  const [concurrency, setConcurrency] = React.useState(2);
  const [timeoutSec, setTimeoutSec] = React.useState(60);
  const [actionMs, setActionMs] = React.useState(10000);
  const [waitMs, setWaitMs] = React.useState(8000);
  const [delayMs, setDelayMs] = React.useState(500);
  const [retries, setRetries] = React.useState(2);
  const [dryRun, setDryRun] = React.useState(false);

  React.useEffect(() => {
    const a = data?.automation;
    if (!a) return;
    setHeadless(Boolean(a.headless));
    setConcurrency(Number(a.concurrency ?? 2));
    setTimeoutSec(Number(a.per_website_timeout_sec ?? 60));
    setActionMs(Number(a.action_timeout_ms ?? 10000));
    setWaitMs(Number(a.post_submit_wait_ms ?? 8000));
    setDelayMs(Number(a.polite_delay_ms ?? 500));
    setRetries(Number(a.max_retries ?? 2));
    setDryRun(Boolean(a.dry_run));
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateSettings({
        headless,
        concurrency,
        per_website_timeout_sec: timeoutSec,
        action_timeout_ms: actionMs,
        post_submit_wait_ms: waitMs,
        polite_delay_ms: delayMs,
        max_retries: retries,
        dry_run: dryRun,
      }),
    onSuccess: () => {
      toast.success("Runtime automation settings updated");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const st = data?.status || {};
  const app = data?.app || {};

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">System health, database connectivity, and Playwright automation parameters.</p>
      </div>

      {/* System Status */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">Backend API</p>
            <div className="mt-1.5"><StatusBadge status={st.backend === "connected" ? "success" : "failed"} /></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">MySQL Database</p>
            <div className="mt-1.5 flex items-center gap-2">
              <StatusBadge status={st.database === "connected" ? "success" : "failed"} />
              <span className="text-xs text-slate-500">{st.database_name}@{st.database_host}:{st.database_port}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">Application</p>
            <p className="mt-1.5 text-sm font-medium text-slate-900">{app.name} ({app.environment})</p>
          </CardContent>
        </Card>
      </div>

      {/* Automation Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Automation & Browser Settings</CardTitle>
          <CardDescription>Adjust Playwright execution timeouts, polite rate limiting, and dry-run mode.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              saveMutation.mutate();
            }}
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-medium text-slate-700">Concurrency (1–10)</label>
                <Input className="mt-1" type="number" min={1} max={10} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Per-Website Timeout (sec)</label>
                <Input className="mt-1" type="number" min={10} max={300} value={timeoutSec} onChange={(e) => setTimeoutSec(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Action Timeout (ms)</label>
                <Input className="mt-1" type="number" min={1000} max={60000} value={actionMs} onChange={(e) => setActionMs(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Post-Submit Network Wait (ms)</label>
                <Input className="mt-1" type="number" min={500} max={30000} value={waitMs} onChange={(e) => setWaitMs(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Polite Delay Between Sites (ms)</label>
                <Input className="mt-1" type="number" min={0} max={10000} value={delayMs} onChange={(e) => setDelayMs(Number(e.target.value))} />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Max Retries (0–5)</label>
                <Input className="mt-1" type="number" min={0} max={5} value={retries} onChange={(e) => setRetries(Number(e.target.value))} />
              </div>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} className="rounded border-slate-300" />
                Run Chromium in Headless Mode
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="rounded border-slate-300" />
                Dry-Run Mode (fill forms without clicking submit)
              </label>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
