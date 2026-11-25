import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Download,
  ExternalLink,
  Globe,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { api, getExportUrl } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";

export function WebsitesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [scanStatus, setScanStatus] = React.useState("all");
  const [formFound, setFormFound] = React.useState("all");
  const [hasCaptcha, setHasCaptcha] = React.useState("all");
  const [page, setPage] = React.useState(0);
  const limit = 20;

  const [addOpen, setAddOpen] = React.useState(false);
  const [singleUrl, setSingleUrl] = React.useState("");
  const [bulkUrls, setBulkUrls] = React.useState("");
  const [bulkMode, setBulkMode] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["websites", page, search, scanStatus, formFound, hasCaptcha],
    queryFn: () =>
      api.listWebsites({
        skip: page * limit,
        limit,
        search,
        scan_status: scanStatus,
        form_found: formFound,
        has_captcha: hasCaptcha,
      }),
  });

  const addMutation = useMutation({
    mutationFn: (url: string) => api.addWebsite(url),
    onSuccess: () => {
      toast.success("Website added");
      setSingleUrl("");
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["websites"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const bulkMutation = useMutation({
    mutationFn: (urls: string[]) => api.bulkImportWebsites(urls),
    onSuccess: (res) => {
      toast.success(`Added ${res.added} website(s) (${res.duplicates} duplicates, ${res.invalid.length} invalid)`);
      setBulkUrls("");
      setAddOpen(false);
      qc.invalidateQueries({ queryKey: ["websites"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const scanMutation = useMutation({
    mutationFn: (id: number) => api.scanWebsite(id),
    onSuccess: (res) => {
      toast.success(`Scan complete: ${res.result?.status || "done"}`);
      qc.invalidateQueries({ queryKey: ["websites"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteWebsite(id),
    onSuccess: () => {
      toast.success("Website removed");
      qc.invalidateQueries({ queryKey: ["websites"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const { data: batchStatus } = useQuery({
    queryKey: ["batch-scan-status"],
    queryFn: () => api.getBatchScanStatus(),
    refetchInterval: (query) => ((query.state.data as any)?.running ? 2000 : false),
  });

  React.useEffect(() => {
    if (batchStatus?.running) {
      qc.invalidateQueries({ queryKey: ["websites"] });
    }
  }, [batchStatus?.processed, batchStatus?.running, qc]);

  const batchScanMutation = useMutation({
    mutationFn: ({ mode, lim }: { mode: "pending" | "pending_and_noform" | "all"; lim?: number }) =>
      api.startBatchScan(mode, lim, 3),
    onSuccess: (res) => {
      toast.success(`Batch scan started (${res.mode})`);
      qc.invalidateQueries({ queryKey: ["batch-scan-status"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const stopBatchMutation = useMutation({
    mutationFn: () => api.stopBatchScan(),
    onSuccess: () => {
      toast.info("Stopping batch scan after active items finish...");
      qc.invalidateQueries({ queryKey: ["batch-scan-status"] });
    },
  });

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await api.importWebsitesCsv(file);
      toast.success(`Imported ${res.added} website(s) from CSV (${res.duplicates} duplicates)`);
      qc.invalidateQueries({ queryKey: ["websites"] });
    } catch (err: any) {
      toast.error(err.message || "CSV import failed");
    } finally {
      e.target.value = "";
    }
  };

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Websites</h1>
          <p className="text-sm text-slate-500">Manage target websites, trigger form discovery scans, and inspect fields.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleCsvUpload} />
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4" /> Import CSV
          </Button>
          <a href={getExportUrl("/websites/export-csv")} download>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> Export CSV
            </Button>
          </a>
          <Button
            variant="outline"
            size="sm"
            disabled={Boolean(batchStatus?.running) || batchScanMutation.isPending}
            onClick={() => batchScanMutation.mutate({ mode: "pending" })}
          >
            <RefreshCw className="h-4 w-4" /> Scan Pending
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={Boolean(batchStatus?.running) || batchScanMutation.isPending}
            onClick={() => batchScanMutation.mutate({ mode: "pending_and_noform" })}
          >
            <RefreshCw className="h-4 w-4" /> Scan Pending + No Form
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" /> Add Websites
          </Button>
        </div>
      </div>

      {batchStatus?.running && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-2 text-sm font-medium text-blue-900">
                <RefreshCw className="h-4 w-4 animate-spin text-blue-600" />
                <span>
                  Batch Scan ({batchStatus.mode}): {batchStatus.processed} / {batchStatus.total} processed
                </span>
                <span className="text-xs text-slate-600">
                  (Forms: {batchStatus.form_found} · No Form: {batchStatus.no_form} · CAPTCHA: {batchStatus.captcha} · Failed: {batchStatus.failed})
                </span>
              </div>
              {batchStatus.current_url && (
                <p className="text-xs text-slate-500 truncate">Current: {batchStatus.current_url}</p>
              )}
              <div className="h-1.5 w-full rounded-full bg-blue-100 overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all"
                  style={{
                    width: `${batchStatus.total ? Math.round((batchStatus.processed / batchStatus.total) * 100) : 0}%`,
                  }}
                />
              </div>
            </div>
            <Button size="sm" variant="destructive" onClick={() => stopBatchMutation.mutate()}>
              Stop Scan
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search domain or URL..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
                className="pl-9"
              />
            </div>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={scanStatus}
              onChange={(e) => {
                setScanStatus(e.target.value);
                setPage(0);
              }}
            >
              <option value="all">All Scan Statuses</option>
              <option value="scanned">Scanned</option>
              <option value="unscanned">Pending Scan</option>
            </select>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={formFound}
              onChange={(e) => {
                setFormFound(e.target.value);
                setPage(0);
              }}
            >
              <option value="all">All Form Availability</option>
              <option value="yes">Form Detected</option>
              <option value="no">No Form</option>
            </select>
            <select
              className="h-9 rounded-md border border-input bg-white px-3 text-sm"
              value={hasCaptcha}
              onChange={(e) => {
                setHasCaptcha(e.target.value);
                setPage(0);
              }}
            >
              <option value="all">All CAPTCHA States</option>
              <option value="yes">CAPTCHA Protected</option>
              <option value="no">No CAPTCHA</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-6">
              <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <strong>Unable to load websites:</strong> {(error as Error)?.message || "Database unavailable."}
              </div>
            </div>
          ) : items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={Globe}
                title="No websites found"
                description="Add a website URL or import a CSV to begin discovering contact forms."
                action={
                  <Button size="sm" onClick={() => setAddOpen(true)}>
                    <Plus className="h-4 w-4" /> Add Website
                  </Button>
                }
              />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50/80 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Website</th>
                  <th className="px-4 py-3">Scan Status</th>
                  <th className="px-4 py-3">Contact Form</th>
                  <th className="px-4 py-3">Fields</th>
                  <th className="px-4 py-3">CAPTCHA</th>
                  <th className="px-4 py-3">Last Scanned</th>
                  <th className="px-4 py-3 text-right sticky right-0 bg-slate-50/95">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {items.map((w: any) => (
                  <tr key={w.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <Link to={`/websites/${w.id}`} className="font-medium text-blue-600 hover:underline">
                        {w.domain || w.url}
                      </Link>
                      <div className="max-w-xs truncate text-xs text-slate-400">{w.url}</div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={w.is_dead ? "failed" : w.scan_status} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={w.form_found ? "scraped" : "noform"} />
                    </td>
                    <td className="px-4 py-3 text-slate-700">{w.fields_count}</td>
                    <td className="px-4 py-3">
                      {w.has_captcha ? <StatusBadge status="captcha" /> : <span className="text-xs text-slate-400">None</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(w.last_scanned)}</td>
                    <td className="px-4 py-3 text-right sticky right-0 bg-white">
                      <div className="inline-flex items-center gap-1">
                        <Link to={`/websites/${w.id}`}>
                          <Button variant="ghost" size="icon" title="Inspect details">
                            <ExternalLink className="h-4 w-4 text-slate-500" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Scan website"
                          disabled={scanMutation.isPending}
                          onClick={() => scanMutation.mutate(w.id)}
                        >
                          <RefreshCw className={`h-4 w-4 text-slate-500 ${scanMutation.isPending ? "animate-spin" : ""}`} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Remove website"
                          onClick={() => {
                            if (window.confirm(`Remove ${w.url}?`)) deleteMutation.mutate(w.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-rose-500" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-slate-500">
          <span>
            Showing {total === 0 ? 0 : page * limit + 1}–{Math.min(total, (page + 1) * limit)} of {total}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span>
              Page {page + 1} of {totalPages}
            </span>
            <Button variant="outline" size="sm" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      </Card>

      {/* Add Website Dialog */}
      <Dialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add Websites"
        description="Add a single URL or paste multiple URLs (one per line)."
      >
        <div className="flex gap-2 mb-4">
          <Button variant={!bulkMode ? "default" : "outline"} size="sm" onClick={() => setBulkMode(false)}>
            Single URL
          </Button>
          <Button variant={bulkMode ? "default" : "outline"} size="sm" onClick={() => setBulkMode(true)}>
            Bulk Import
          </Button>
        </div>

        {!bulkMode ? (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              addMutation.mutate(singleUrl);
            }}
          >
            <div>
              <label className="text-xs font-medium text-slate-700">Website URL</label>
              <Input
                className="mt-1"
                placeholder="https://example.com"
                value={singleUrl}
                onChange={(e) => setSingleUrl(e.target.value)}
                required
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={addMutation.isPending}>
                {addMutation.isPending ? "Adding..." : "Add Website"}
              </Button>
            </div>
          </form>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              const urls = bulkUrls
                .split(/\r?\n/)
                .map((u) => u.trim())
                .filter(Boolean);
              if (urls.length > 0) bulkMutation.mutate(urls);
            }}
          >
            <div>
              <label className="text-xs font-medium text-slate-700">URLs (one per line)</label>
              <Textarea
                className="mt-1 min-h-[140px]"
                placeholder={"https://example.com\nhttps://another-site.org"}
                value={bulkUrls}
                onChange={(e) => setBulkUrls(e.target.value)}
                required
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={bulkMutation.isPending}>
                {bulkMutation.isPending ? "Importing..." : "Import URLs"}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </div>
  );
}
