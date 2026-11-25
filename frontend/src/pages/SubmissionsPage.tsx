import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Eye, FileCheck2, Search } from "lucide-react";
import { api, getExportUrl } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";

export function SubmissionsPage() {
  const [status, setStatus] = React.useState("all");
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(0);
  const [selected, setSelected] = React.useState<any | null>(null);
  const limit = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["submissions", page, status, search],
    queryFn: () => api.listSubmissions({ skip: page * limit, limit, status, search }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Submissions</h1>
          <p className="text-sm text-slate-500">Audit all form submission attempts, HTTP responses, and manual review items.</p>
        </div>
        <a href={getExportUrl(`/form-submissions/export-csv${status !== "all" ? `?status=${status}` : ""}`)} download>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4" /> Export CSV
          </Button>
        </a>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                className="pl-9"
                placeholder="Search by URL or error..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
              />
            </div>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(0);
              }}
            >
              <option value="all">All Statuses</option>
              <option value="success">Successful</option>
              <option value="failed">Failed</option>
              <option value="captcha">CAPTCHA</option>
              <option value="pending">Pending / Manual Review</option>
              <option value="noform">No Form</option>
            </select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={FileCheck2}
                title="No submissions found"
                description="Submissions will appear here once you scan or run a campaign."
              />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50/80 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Website URL</th>
                  <th className="px-4 py-3">Campaign</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Filled Fields</th>
                  <th className="px-4 py-3">HTTP</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3 text-right sticky right-0 bg-slate-50/95">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((sub: any) => (
                  <tr key={sub.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 max-w-xs truncate font-medium text-slate-900">{sub.url}</td>
                    <td className="px-4 py-3 text-slate-600">{sub.campaign_name || (sub.campaign_id ? `#${sub.campaign_id}` : "Ad-hoc")}</td>
                    <td className="px-4 py-3"><StatusBadge status={sub.status} /></td>
                    <td className="px-4 py-3">{sub.filled_fields}</td>
                    <td className="px-4 py-3 font-mono text-xs">{sub.details?.status_code || "—"}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(sub.created_at)}</td>
                    <td className="px-4 py-3 text-right sticky right-0 bg-white">
                      <Button variant="ghost" size="icon" onClick={() => setSelected(sub)}>
                        <Eye className="h-4 w-4 text-slate-500" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-slate-500">
          <span>
            Showing {total === 0 ? 0 : page * limit + 1}–{Math.min(total, (page + 1) * limit)} of {total}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span>Page {page + 1} of {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      </Card>

      <Dialog
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={`Submission #${selected?.id || ""}`}
        description={selected?.url}
        maxWidthClass="max-w-2xl"
      >
        {selected && (
          <div className="space-y-4 text-sm max-h-[70vh] overflow-y-auto">
            <div className="flex items-center gap-3">
              <StatusBadge status={selected.status} />
              <span className="text-xs text-slate-500">{formatDate(selected.created_at)}</span>
              {selected.details?.status_code && (
                <span className="font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">
                  HTTP {selected.details.status_code}
                </span>
              )}
            </div>
            {selected.error && (
              <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                <strong>Error / Message:</strong> {selected.error}
              </div>
            )}
            {selected.details?.request_url && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Request Endpoint</p>
                <code className="block rounded bg-slate-100 p-2 text-xs break-all">{selected.details.request_url}</code>
              </div>
            )}
            {selected.details?.response_json && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Captured Response</p>
                <pre className="rounded bg-slate-900 text-slate-100 p-3 text-xs overflow-x-auto">
                  {selected.details.response_json}
                </pre>
              </div>
            )}
          </div>
        )}
      </Dialog>
    </div>
  );
}
