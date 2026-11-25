import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FileCheck2,
  Globe,
  Megaphone,
  Plus,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";

export function DashboardPage() {
  const [days, setDays] = React.useState(30);
  const { data: overview, isLoading, isError, error } = useQuery({
    queryKey: ["analytics-overview", days],
    queryFn: () => api.getAnalyticsOverview(days),
  });

  const { data: recentSubs } = useQuery({
    queryKey: ["recent-submissions"],
    queryFn: () => api.listSubmissions({ limit: 6, skip: 0 }),
  });

  const w = overview?.websites || {};
  const c = overview?.campaigns || {};
  const s = overview?.submissions || {};

  const kpis = [
    { label: "Total Websites", value: w.total ?? 0, sub: `${w.scanned ?? 0} scanned`, icon: Globe, color: "text-blue-600" },
    { label: "Forms Discovered", value: w.with_forms ?? 0, sub: `${w.without_forms ?? 0} without forms`, icon: FileCheck2, color: "text-emerald-600" },
    { label: "CAPTCHA Protected", value: w.captcha ?? 0, sub: "Marked for review", icon: ShieldAlert, color: "text-amber-600" },
    { label: "Campaigns", value: c.total ?? 0, sub: `${c.active ?? 0} active · ${c.completed ?? 0} done`, icon: Megaphone, color: "text-indigo-600" },
    { label: "Successful Submissions", value: s.success ?? 0, sub: `${s.total ?? 0} total (${days}d)`, icon: CheckCircle2, color: "text-emerald-600" },
    { label: "Failed Submissions", value: s.failed ?? 0, sub: `${s.captcha ?? 0} CAPTCHA blocked`, icon: XCircle, color: "text-rose-600" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Overview of website discovery, campaigns, and form submissions.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Timeframe"
            className="h-8 rounded-md border border-input bg-white px-2.5 text-xs font-medium text-slate-700"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
            <option value={365}>Last 365 Days</option>
          </select>
          <Link to="/websites">
            <Button variant="outline" size="sm">
              <Plus className="h-4 w-4" /> Add Websites
            </Button>
          </Link>
          <Link to="/campaigns/new">
            <Button size="sm">
              <Plus className="h-4 w-4" /> Create Campaign
            </Button>
          </Link>
          <Link to="/submissions">
            <Button variant="outline" size="sm">View Submissions</Button>
          </Link>
          <Link to="/analytics">
            <Button variant="outline" size="sm">
              <BarChart3 className="h-4 w-4" /> Analytics
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Grid */}
      {isError && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <strong>Backend Notice:</strong> {(error as Error)?.message || "Unable to load dashboard metrics."}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <Card key={k.label}>
              <CardContent className="p-5">
                {isLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-7 w-16" />
                    <Skeleton className="h-3 w-36" />
                  </div>
                ) : (
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{k.label}</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-900">{Number(k.value).toLocaleString()}</p>
                      <p className="mt-1 text-xs text-slate-500">{k.sub}</p>
                    </div>
                    <div className={`rounded-md bg-slate-50 p-2 border ${k.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Submission Activity ({days} Days)</CardTitle>
            <CardDescription>Daily form submission outcomes from database records</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (overview?.daily_activity || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No submission activity recorded in the last {days} days.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={overview.daily_activity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="success" stroke="#10b981" fill="#10b981" fillOpacity={0.15} name="Success" />
                  <Area type="monotone" dataKey="failed" stroke="#ef4444" fill="#ef4444" fillOpacity={0.12} name="Failed" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Campaign Performance</CardTitle>
            <CardDescription>Success vs failed vs CAPTCHA across recent campaigns</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (overview?.campaign_performance || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No campaigns created yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overview.campaign_performance.slice(0, 6)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                  <Tooltip />
                  <Bar dataKey="success" fill="#10b981" radius={[3, 3, 0, 0]} name="Success" />
                  <Bar dataKey="failed" fill="#ef4444" radius={[3, 3, 0, 0]} name="Failed" />
                  <Bar dataKey="captcha" fill="#f59e0b" radius={[3, 3, 0, 0]} name="CAPTCHA" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom 3-column summary: Recent Campaigns, Recent Submissions, Recent Errors */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Recent Campaigns</CardTitle>
            <Link to="/campaigns" className="text-xs font-medium text-blue-600 hover:underline inline-flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {(overview?.campaign_performance || []).slice(0, 5).map((camp: any) => (
              <Link
                key={camp.id}
                to={`/campaigns/${camp.id}`}
                className="flex items-center justify-between rounded-md border p-3 hover:bg-slate-50 transition-colors"
              >
                <div className="min-w-0 pr-2">
                  <p className="truncate text-sm font-medium text-slate-900">{camp.name}</p>
                  <p className="text-xs text-slate-500">{camp.targets} targets</p>
                </div>
                <StatusBadge status={camp.status} />
              </Link>
            ))}
            {(overview?.campaign_performance || []).length === 0 && (
              <p className="text-sm text-slate-400">No campaigns yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Recent Submissions</CardTitle>
            <Link to="/submissions" className="text-xs font-medium text-blue-600 hover:underline inline-flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {(recentSubs?.items || []).slice(0, 5).map((sub: any) => (
              <div key={sub.id} className="flex items-center justify-between rounded-md border p-3">
                <div className="min-w-0 pr-2">
                  <p className="truncate text-sm font-medium text-slate-900">{sub.url}</p>
                  <p className="text-xs text-slate-500">{formatDate(sub.created_at)}</p>
                </div>
                <StatusBadge status={sub.status} />
              </div>
            ))}
            {(recentSubs?.items || []).length === 0 && (
              <p className="text-sm text-slate-400">No submissions recorded yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="inline-flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-500" /> Recent Errors
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(overview?.recent_errors || []).slice(0, 5).map((err: any) => (
              <div key={err.id} className="rounded-md border border-rose-100 bg-rose-50/40 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-medium text-slate-900">{err.url}</p>
                  <StatusBadge status={err.status} />
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-rose-700">{err.error}</p>
              </div>
            ))}
            {(overview?.recent_errors || []).length === 0 && (
              <p className="text-sm text-slate-400">No recent errors.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
