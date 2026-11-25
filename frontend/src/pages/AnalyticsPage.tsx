import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const PIE_COLORS = ["#10b981", "#ef4444", "#f59e0b", "#64748b", "#3b82f6", "#8b5cf6"];

export function AnalyticsPage() {
  const [days, setDays] = React.useState(30);
  const [campaignId, setCampaignId] = React.useState<string>("all");

  const { data: campaignsData } = useQuery({
    queryKey: ["campaigns-filter"],
    queryFn: () => api.listCampaigns(),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["analytics-detail", days, campaignId],
    queryFn: () => api.getAnalyticsOverview(days, campaignId === "all" ? undefined : Number(campaignId)),
  });

  const rates = data?.rates || {};
  const websites = data?.websites || {};

  const rateCards = [
    { label: "Processed Websites", value: `${websites.scanned ?? 0} / ${websites.total ?? 0}` },
    { label: "Form Discovery Rate", value: `${rates.form_discovery_rate ?? 0}%` },
    { label: "Submission Success Rate", value: `${rates.submission_success_rate ?? 0}%` },
    { label: "Failure Rate", value: `${rates.failure_rate ?? 0}%` },
    { label: "CAPTCHA Rate", value: `${rates.captcha_rate ?? 0}%` },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Analytics</h1>
          <p className="text-sm text-slate-500">Metrics calculated directly from database submission and discovery records.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border border-input bg-white px-3 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
            <option value={365}>Last 365 Days</option>
          </select>
          <select
            className="h-9 rounded-md border border-input bg-white px-3 text-sm"
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
          >
            <option value="all">All Campaigns</option>
            {(campaignsData?.items || []).map((c: any) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Rate KPIs */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {rateCards.map((r) => (
          <Card key={r.label}>
            <CardContent className="p-4">
              <p className="text-xs font-medium text-slate-500">{r.label}</p>
              {isLoading ? (
                <Skeleton className="mt-2 h-7 w-16" />
              ) : (
                <p className="mt-1.5 text-2xl font-semibold text-slate-900">{r.value}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily Submission Activity</CardTitle>
            <CardDescription>Trend of successful, failed, and CAPTCHA outcomes</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (data?.daily_activity || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">No data for selected range.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.daily_activity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="success" stroke="#10b981" strokeWidth={2} name="Success" />
                  <Line type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={2} name="Failed" />
                  <Line type="monotone" dataKey="captcha" stroke="#f59e0b" strokeWidth={2} name="CAPTCHA" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status & Error Distribution</CardTitle>
            <CardDescription>Breakdown of submission statuses in selected period</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (data?.status_distribution || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">No submission records.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.status_distribution}
                    dataKey="count"
                    nameKey="status"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={(e: any) => `${e.status} (${e.count})`}
                  >
                    {data.status_distribution.map((_: any, i: number) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Common Detected Field Concepts</CardTitle>
            <CardDescription>Most frequent semantic concepts extracted across forms</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (data?.field_concepts || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">No field data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.field_concepts} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="concept" type="category" width={100} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2563eb" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Campaign Comparison</CardTitle>
            <CardDescription>Targets and outcomes across recent campaigns</CardDescription>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (data?.campaign_performance || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">No campaigns found.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.campaign_performance}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="targets" fill="#94a3b8" name="Targets" />
                  <Bar dataKey="success" fill="#10b981" name="Success" />
                  <Bar dataKey="failed" fill="#ef4444" name="Failed" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
