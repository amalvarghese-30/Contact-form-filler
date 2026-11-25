import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";

const CONCEPTS = [
  "full_name",
  "first_name",
  "last_name",
  "email",
  "phone",
  "company",
  "subject",
  "message",
  "website",
  "address",
  "city",
  "state",
  "zip_code",
  "country",
  "consent",
  "unknown",
];

export function WebsiteDetailsPage() {
  const { id } = useParams();
  const websiteId = Number(id);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["website", websiteId],
    queryFn: () => api.getWebsiteDetails(websiteId),
    enabled: Boolean(websiteId),
  });

  const scanMutation = useMutation({
    mutationFn: () => api.scanWebsite(websiteId),
    onSuccess: (res) => {
      toast.success(`Scan finished: ${res.result?.status || "done"}`);
      qc.invalidateQueries({ queryKey: ["website", websiteId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const fieldMutation = useMutation({
    mutationFn: ({ fieldId, clusterKey }: { fieldId: number; clusterKey: string }) =>
      api.updateWebsiteField(websiteId, fieldId, clusterKey),
    onSuccess: () => {
      toast.success("Field mapping updated");
      qc.invalidateQueries({ queryKey: ["website", websiteId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-sm text-slate-500">Website not found.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link to="/websites" className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 mb-1">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Websites
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{data.domain || data.url}</h1>
          <p className="text-sm text-slate-500 break-all">{data.url}</p>
        </div>
        <Button size="sm" onClick={() => scanMutation.mutate()} disabled={scanMutation.isPending}>
          <RefreshCw className={`h-4 w-4 ${scanMutation.isPending ? "animate-spin" : ""}`} />
          {scanMutation.isPending ? "Scanning..." : "Rescan Website"}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">Scan Status</p>
            <div className="mt-1.5"><StatusBadge status={data.is_dead ? "failed" : data.scan_status} /></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">Contact Form</p>
            <div className="mt-1.5"><StatusBadge status={data.form_found ? "scraped" : "noform"} /></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">CAPTCHA</p>
            <div className="mt-1.5">
              {data.has_captcha ? <StatusBadge status="captcha" /> : <span className="text-sm font-medium text-slate-700">None</span>}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-slate-500">Last Scanned</p>
            <p className="mt-1.5 text-sm font-medium text-slate-800">{formatDate(data.last_scanned)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Detected Fields */}
      <Card>
        <CardHeader>
          <CardTitle>Detected Form Fields ({data.fields?.length || 0})</CardTitle>
          <CardDescription>Inspect extracted inputs and override normalised concepts if needed.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {(data.fields || []).length === 0 ? (
            <p className="text-sm text-slate-500">No form fields detected yet. Run a scan to discover fields.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50 text-left text-xs font-medium uppercase text-slate-500">
                  <th className="px-3 py-2.5">Tag / Type</th>
                  <th className="px-3 py-2.5">Field Name / ID</th>
                  <th className="px-3 py-2.5">Placeholder</th>
                  <th className="px-3 py-2.5">Mapped Concept</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.fields.map((f: any) => (
                  <tr key={f.id}>
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-600">
                      {f.tag_name} / {f.field_type || "text"}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="font-medium text-slate-900">{f.field_name || "—"}</span>
                      {f.field_id && <span className="ml-2 text-xs text-slate-400">#{f.field_id}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{f.placeholder || "—"}</td>
                    <td className="px-3 py-2.5">
                      <select
                        className="h-8 rounded-md border border-input bg-white px-2 text-xs font-medium"
                        value={f.cluster_key || "unknown"}
                        onChange={(e) => fieldMutation.mutate({ fieldId: f.id, clusterKey: e.target.value })}
                      >
                        {CONCEPTS.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Submission History */}
      <Card>
        <CardHeader>
          <CardTitle>Previous Submission History</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {(data.submissions || []).length === 0 ? (
            <p className="text-sm text-slate-500">No submissions recorded for this website.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50 text-left text-xs font-medium uppercase text-slate-500">
                  <th className="px-3 py-2.5">Date</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5">Filled Fields</th>
                  <th className="px-3 py-2.5">HTTP</th>
                  <th className="px-3 py-2.5">Notes / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.submissions.map((s: any) => (
                  <tr key={s.id}>
                    <td className="px-3 py-2.5 text-xs text-slate-500">{formatDate(s.created_at)}</td>
                    <td className="px-3 py-2.5"><StatusBadge status={s.status} /></td>
                    <td className="px-3 py-2.5">{s.filled_fields}</td>
                    <td className="px-3 py-2.5">{s.status_code || "—"}</td>
                    <td className="px-3 py-2.5 text-xs text-slate-600 max-w-md truncate">{s.error || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
