import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api, getExportUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export function FieldsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [conceptFilter, setConceptFilter] = React.useState("all");
  const [newConcept, setNewConcept] = React.useState("full_name");
  const [newValue, setNewValue] = React.useState("");
  const [importConcept, setImportConcept] = React.useState("full_name");
  const fileRef = React.useRef<HTMLInputElement>(null);

  const { data: mappingsData, isLoading: mapLoading } = useQuery({
    queryKey: ["field-mappings-details", search, conceptFilter],
    queryFn: () => api.listFieldMappingDetails({ search, concept: conceptFilter, limit: 100 }),
  });

  const { data: poolData, isLoading: poolLoading } = useQuery({
    queryKey: ["random-values", conceptFilter],
    queryFn: () => api.listRandomValues({ concept: conceptFilter === "unmapped" ? "all" : conceptFilter, limit: 100 }),
  });

  const updateMappingMutation = useMutation({
    mutationFn: ({ label, concept }: { label: string; concept: string }) =>
      api.updateFieldMapping(label, concept),
    onSuccess: () => {
      toast.success("Concept mapping updated");
      qc.invalidateQueries({ queryKey: ["field-mappings-details"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const addValueMutation = useMutation({
    mutationFn: () => api.addRandomValue(newConcept, newValue),
    onSuccess: () => {
      toast.success("Value added to pool");
      setNewValue("");
      qc.invalidateQueries({ queryKey: ["random-values"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteValueMutation = useMutation({
    mutationFn: (id: number) => api.deleteRandomValue(id),
    onSuccess: () => {
      toast.success("Value removed");
      qc.invalidateQueries({ queryKey: ["random-values"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await api.importRandomValuesCsv(importConcept, file);
      toast.success(`Imported ${res.imported} values for ${res.fieldconcept}`);
      qc.invalidateQueries({ queryKey: ["random-values"] });
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      e.target.value = "";
    }
  };

  const canonicalConcepts: Record<string, string> = mappingsData?.canonicalConcepts || {};
  const conceptKeys = Object.keys(canonicalConcepts);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Field Mapping & Value Pools</h1>
          <p className="text-sm text-slate-500">Manage normalized field concepts and random value pools used during form filling.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border border-input bg-white px-3 text-sm"
            value={importConcept}
            onChange={(e) => setImportConcept(e.target.value)}
          >
            {(conceptKeys.length ? conceptKeys : ["full_name", "email", "phone", "company", "subject", "message"]).map((k) => (
              <option key={k} value={k}>{canonicalConcepts[k] || k}</option>
            ))}
          </select>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCsvImport} />
          <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4" /> Import Pool CSV
          </Button>
          <a href={getExportUrl("/random-values/export-csv")} download>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> Export Pool CSV
            </Button>
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input className="pl-9" placeholder="Search normalized field labels..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select
          className="h-9 rounded-md border border-input bg-white px-3 text-sm"
          value={conceptFilter}
          onChange={(e) => setConceptFilter(e.target.value)}
        >
          <option value="all">All Concepts</option>
          <option value="unmapped">Unmapped Only</option>
          {conceptKeys.map((k) => (
            <option key={k} value={k}>{canonicalConcepts[k]} ({k})</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Concept Mappings */}
        <Card>
          <CardHeader>
            <CardTitle>Concept Mappings ({mappingsData?.total ?? 0})</CardTitle>
            <CardDescription>Override automatic mapping of normalized labels to canonical concepts.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[480px] overflow-y-auto">
            {mapLoading ? (
              <div className="space-y-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
            ) : (mappingsData?.items || []).length === 0 ? (
              <p className="text-sm text-slate-400">No field mappings found.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs font-medium uppercase text-slate-500">
                    <th className="py-2">Normalized Label</th>
                    <th className="py-2">Canonical Concept</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {mappingsData.items.map((m: any) => (
                    <tr key={m.id}>
                      <td className="py-2.5 font-mono text-xs text-slate-800">{m.normalized_label}</td>
                      <td className="py-2.5">
                        <select
                          className="h-8 rounded-md border border-input bg-white px-2 text-xs"
                          value={m.canonical_concept || ""}
                          onChange={(e) => updateMappingMutation.mutate({ label: m.normalized_label, concept: e.target.value })}
                        >
                          <option value="" disabled>Unmapped</option>
                          {conceptKeys.map((k) => (
                            <option key={k} value={k}>{canonicalConcepts[k]}</option>
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

        {/* Random Value Pool */}
        <Card>
          <CardHeader>
            <CardTitle>Random Value Pool ({poolData?.total ?? 0})</CardTitle>
            <CardDescription>Values used when a campaign field strategy is set to Random Pool.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (newValue.trim()) addValueMutation.mutate();
              }}
            >
              <select
                className="h-9 rounded-md border border-input bg-white px-2.5 text-sm"
                value={newConcept}
                onChange={(e) => setNewConcept(e.target.value)}
              >
                {(conceptKeys.length ? conceptKeys : ["full_name", "email", "phone", "company", "subject", "message"]).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
              <Input
                placeholder="Add pool value..."
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                required
              />
              <Button type="submit" size="sm" disabled={addValueMutation.isPending}>
                <Plus className="h-4 w-4" /> Add
              </Button>
            </form>

            <div className="max-h-[380px] overflow-y-auto divide-y rounded-md border">
              {poolLoading ? (
                <div className="p-4 space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
              ) : (poolData?.items || []).length === 0 ? (
                <p className="p-4 text-sm text-slate-400">No values in pool.</p>
              ) : (
                poolData.items.map((v: any) => (
                  <div key={v.id} className="flex items-center justify-between px-3 py-2 text-sm">
                    <div className="min-w-0 pr-2">
                      <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600 mr-2">
                        {v.field_concept}
                      </span>
                      <span className="text-slate-800 break-all">{v.value}</span>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => deleteValueMutation.mutate(v.id)}>
                      <Trash2 className="h-4 w-4 text-rose-500" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
