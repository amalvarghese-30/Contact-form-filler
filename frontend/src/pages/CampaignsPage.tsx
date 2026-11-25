import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  Copy,
  Edit,
  Eye,
  Megaphone,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";

export function CampaignsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("all");
  const [sortBy, setSortBy] = React.useState("newest");

  const { data, isLoading } = useQuery({
    queryKey: ["campaigns", search, status, sortBy],
    queryFn: () => api.listCampaigns({ search, status, sort_by: sortBy }),
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "start" | "pause" | "resume" | "restart" | "delete" | "duplicate" }) => {
      if (action === "start") return api.startCampaign(id);
      if (action === "pause") return api.pauseCampaign(id);
      if (action === "resume") return api.resumeCampaign(id);
      if (action === "restart") return api.restartCampaign(id);
      if (action === "duplicate") return api.duplicateCampaign(id);
      return api.deleteCampaign(id);
    },
    onSuccess: (res, vars) => {
      toast.success(`Campaign ${vars.action} succeeded`);
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      if (vars.action === "duplicate" && res?.campaignId) {
        navigate(`/campaigns/${res.campaignId}/edit`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Campaigns</h1>
          <p className="text-sm text-slate-500">Create, schedule, monitor, and control automated form submission campaigns.</p>
        </div>
        <Link to="/campaigns/new">
          <Button size="sm">
            <Plus className="h-4 w-4" /> Create Campaign
          </Button>
        </Link>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search campaigns..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="all">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="name">Name (A–Z)</option>
            </select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={Megaphone}
                title="No campaigns found"
                description="Use the Campaign Wizard to configure target websites, field mappings, and launch."
                action={
                  <Link to="/campaigns/new">
                    <Button size="sm">
                      <Plus className="h-4 w-4" /> Create Campaign
                    </Button>
                  </Link>
                }
              />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50/80 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Campaign</th>
                  <th className="px-4 py-3">Targets</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Success / Failed</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((c: any) => {
                  const active = ["running", "queued", "scraping", "filling", "clustering"].includes(
                    String(c.status).toLowerCase()
                  );
                  const paused = String(c.status).toLowerCase() === "paused";
                  const draft = String(c.status).toLowerCase() === "draft";

                  return (
                    <tr key={c.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <Link to={`/campaigns/${c.id}`} className="font-medium text-blue-600 hover:underline">
                          {c.name}
                        </Link>
                        {c.description && (
                          <div className="max-w-xs truncate text-xs text-slate-400">{c.description}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{c.targets}</td>
                      <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                      <td className="px-4 py-3 w-36">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 rounded-full bg-slate-200 overflow-hidden">
                            <div
                              className="h-full bg-blue-600 transition-all"
                              style={{ width: `${c.progress_pct || 0}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-500 w-9 text-right">{c.progress_pct || 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <span className="text-emerald-600 font-medium">{c.results_success ?? 0}</span>
                        {" / "}
                        <span className="text-rose-600 font-medium">{c.results_failed ?? 0}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{formatDate(c.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          <Link to={`/campaigns/${c.id}`}>
                            <Button variant="ghost" size="icon" title="Live monitor">
                              <Eye className="h-4 w-4 text-slate-500" />
                            </Button>
                          </Link>
                          {draft && (
                            <Link to={`/campaigns/${c.id}/edit`}>
                              <Button variant="ghost" size="icon" title="Edit draft">
                                <Edit className="h-4 w-4 text-slate-500" />
                              </Button>
                            </Link>
                          )}
                          {!active && !paused && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Start"
                              onClick={() => actionMutation.mutate({ id: c.id, action: "start" })}
                            >
                              <Play className="h-4 w-4 text-emerald-600" />
                            </Button>
                          )}
                          {active && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Pause"
                              onClick={() => actionMutation.mutate({ id: c.id, action: "pause" })}
                            >
                              <Pause className="h-4 w-4 text-amber-600" />
                            </Button>
                          )}
                          {paused && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Resume"
                              onClick={() => actionMutation.mutate({ id: c.id, action: "resume" })}
                            >
                              <Play className="h-4 w-4 text-blue-600" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Restart"
                            onClick={() => actionMutation.mutate({ id: c.id, action: "restart" })}
                          >
                            <RotateCcw className="h-4 w-4 text-slate-500" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Duplicate"
                            onClick={() => actionMutation.mutate({ id: c.id, action: "duplicate" })}
                          >
                            <Copy className="h-4 w-4 text-slate-500" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Delete"
                            onClick={() => {
                              if (window.confirm(`Delete campaign "${c.name}"?`)) {
                                actionMutation.mutate({ id: c.id, action: "delete" });
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-rose-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </Card>
    </div>
  );
}
