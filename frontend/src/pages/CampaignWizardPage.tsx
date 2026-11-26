import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Plus, Search, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";

const DEFAULT_CONCEPTS = [
  { key: "full_name", label: "Full Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "company", label: "Company" },
  { key: "subject", label: "Subject" },
  { key: "message", label: "Message" },
];

export function CampaignWizardPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = React.useState(1);

  // Step 1
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [senderName, setSenderName] = React.useState("");
  const [senderEmail, setSenderEmail] = React.useState("");
  const [subjectLine, setSubjectLine] = React.useState("");
  const [messageBody, setMessageBody] = React.useState("");
  const [maxWebsites, setMaxWebsites] = React.useState(500);

  // Step 2
  const [siteSearch, setSiteSearch] = React.useState("");
  const [selectedUrls, setSelectedUrls] = React.useState<string[]>([]);
  const [manualUrls, setManualUrls] = React.useState("");
  const [newSiteUrl, setNewSiteUrl] = React.useState("");
  const csvFileRef = React.useRef<HTMLInputElement>(null);

  // Step 3
  const [strategies, setStrategies] = React.useState<Record<string, { strategy: string; value: string }>>({
    full_name: { strategy: "constant", value: "" },
    email: { strategy: "constant", value: "" },
    phone: { strategy: "random", value: "" },
    company: { strategy: "random", value: "" },
    subject: { strategy: "constant", value: "" },
    message: { strategy: "constant", value: "" },
  });

  // Step 4
  const [approved, setApproved] = React.useState(false);

  const { data: existing } = useQuery({
    queryKey: ["campaign-edit", id],
    queryFn: () => api.getCampaign(Number(id)),
    enabled: isEdit,
  });

  const { data: sitesData } = useQuery({
    queryKey: ["wizard-websites", siteSearch],
    queryFn: () => api.listWebsites({ limit: 100, skip: 0, search: siteSearch }),
  });

  const { data: templateData } = useQuery({
    queryKey: ["fill-form-template"],
    queryFn: () => api.getFillFormTemplate(),
  });

  React.useEffect(() => {
    if (!existing) return;
    setName(existing.name || "");
    setDescription(existing.description || "");
    setSenderName(existing.sender_name || "");
    setSenderEmail(existing.sender_email || "");
    setSubjectLine(existing.subject_line || "");
    setMessageBody(existing.message_body || "");
    setMaxWebsites(existing.max_websites || 500);
    setSelectedUrls((existing.websites || []).map((w: any) => w.website_url).filter(Boolean));
    const map: Record<string, { strategy: string; value: string }> = {};
    (existing.fieldStrategies || []).forEach((s: any) => {
      map[s.field_concept] = { strategy: s.strategy || "constant", value: s.constant_value || "" };
    });
    if (Object.keys(map).length > 0) setStrategies((prev) => ({ ...prev, ...map }));
  }, [existing]);

  // Sync Step 1 defaults into Step 3 constant values if empty
  React.useEffect(() => {
    setStrategies((prev) => ({
      ...prev,
      full_name: { ...prev.full_name, value: prev.full_name?.value || senderName },
      email: { ...prev.email, value: prev.email?.value || senderEmail },
      subject: { ...prev.subject, value: prev.subject?.value || subjectLine },
      message: { ...prev.message, value: prev.message?.value || messageBody },
    }));
  }, [senderName, senderEmail, subjectLine, messageBody]);

  const uniqueSites = React.useMemo(() => {
    const items = sitesData?.items || [];
    const byUrl = new Map<string, any>();
    const rank = (w: any) => (w.form_found ? 3 : w.has_captcha ? 2 : w.scan_status === "scanned" ? 1 : 0);
    for (const w of items) {
      const key = String(w.url || "").trim().replace(/\/+$/, "").toLowerCase();
      const existing = byUrl.get(key);
      if (!existing || rank(w) > rank(existing)) {
        byUrl.set(key, w);
      }
    }
    return Array.from(byUrl.values());
  }, [sitesData?.items]);

  const conceptList = React.useMemo(() => {
    const map = templateData?.canonicalConcepts;
    if (!map) return DEFAULT_CONCEPTS;
    return Object.entries(map).map(([key, label]) => ({ key, label: String(label) }));
  }, [templateData]);

  const allTargetUrls = React.useMemo(() => {
    const extra = manualUrls
      .split(/\r?\n/)
      .map((u) => u.trim())
      .filter(Boolean);
    return Array.from(new Set([...selectedUrls, ...extra]));
  }, [selectedUrls, manualUrls]);

  const saveMutation = useMutation({
    mutationFn: async (launchAfter: boolean) => {
      const payload = {
        name,
        description,
        senderName,
        senderEmail,
        subjectLine,
        messageBody,
        maxWebsites,
        websiteIds: allTargetUrls,
        fieldStrategies: strategies,
        approved: launchAfter,
      };
      const res = isEdit
        ? await api.updateCampaign(Number(id), payload)
        : await api.createCampaign(payload);
      const cid = res.campaignId || Number(id);
      if (launchAfter) {
        await api.startCampaign(cid);
      }
      return { cid, launchAfter };
    },
    onSuccess: ({ cid, launchAfter }) => {
      toast.success(launchAfter ? "Campaign approved and launched" : "Campaign saved as draft");
      navigate(`/campaigns/${cid}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleUrl = (url: string) => {
    setSelectedUrls((prev) => (prev.includes(url) ? prev.filter((u) => u !== url) : [...prev, url]));
  };

  const addSingleSiteMutation = useMutation({
    mutationFn: (raw: string) => api.addWebsite(raw.trim()),
    onSuccess: (res) => {
      const addedUrl = res.url || newSiteUrl.trim();
      setSelectedUrls((prev) => Array.from(new Set([addedUrl, ...prev])));
      setNewSiteUrl("");
      qc.invalidateQueries({ queryKey: ["wizard-websites"] });
      toast.success(`Added and selected ${addedUrl}`);
    },
    onError: (e: Error) => {
      if (e.message.toLowerCase().includes("already exists")) {
        const candidate = newSiteUrl.trim().includes("://") ? newSiteUrl.trim() : `https://${newSiteUrl.trim()}`;
        setSelectedUrls((prev) => Array.from(new Set([candidate, ...prev])));
        setNewSiteUrl("");
        toast.info("Website already in database — selected for this campaign");
      } else {
        toast.error(e.message);
      }
    },
  });

  const handleWizardCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const urls = text
        .split(/\r?\n/)
        .map((line) => line.split(",")[0]?.trim() || "")
        .filter((cell, idx) => cell && !(idx === 0 && ["url", "website", "websites", "website_url"].includes(cell.toLowerCase())));
      if (urls.length === 0) {
        toast.error("No valid URLs found in CSV");
        return;
      }
      const res = await api.bulkImportWebsites(urls);
      setSelectedUrls((prev) => Array.from(new Set([...prev, ...urls.map((u) => (u.includes("://") ? u : `https://${u}`))])))
      qc.invalidateQueries({ queryKey: ["wizard-websites"] });
      toast.success(`Imported ${res.added} new website(s) & selected ${urls.length} URL(s)`);
    } catch (err: any) {
      toast.error(err.message || "CSV import failed");
    } finally {
      e.target.value = "";
    }
  };

  const canProceedStep1 = name.trim().length > 0 && senderEmail.trim().length > 0 && messageBody.trim().length > 0;
  const canProceedStep2 = allTargetUrls.length > 0;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <button
          type="button"
          onClick={() => navigate("/campaigns")}
          className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800 mb-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Campaigns
        </button>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {isEdit ? "Edit Campaign" : "Create Campaign"}
        </h1>
        <p className="text-sm text-slate-500">Configure campaign details, select target websites, and review before launch.</p>
      </div>

      {/* Stepper */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { n: 1, label: "Campaign Info" },
          { n: 2, label: "Select Websites" },
          { n: 3, label: "Form Fields" },
          { n: 4, label: "Review & Approve" },
        ].map((s) => (
          <button
            key={s.n}
            type="button"
            onClick={() => s.n < step && setStep(s.n)}
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
              step === s.n
                ? "border-blue-600 bg-blue-50 text-blue-700"
                : step > s.n
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "bg-white text-slate-500"
            }`}
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full border text-[11px]">
              {step > s.n ? <Check className="h-3 w-3" /> : s.n}
            </span>
            <span className="hidden sm:inline truncate">{s.label}</span>
          </button>
        ))}
      </div>

      {/* Step 1 */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 1: Campaign Information</CardTitle>
            <CardDescription>Define sender identity and message content for authorised outreach.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-medium text-slate-700">Campaign Name *</label>
                <Input className="mt-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q4 Partner Outreach" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Max Websites Limit</label>
                <Input
                  className="mt-1"
                  type="number"
                  min={1}
                  value={maxWebsites}
                  onChange={(e) => setMaxWebsites(Number(e.target.value) || 50)}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Sender Name</label>
                <Input className="mt-1" value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="Alex Morgan" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700">Sender Email *</label>
                <Input className="mt-1" type="email" value={senderEmail} onChange={(e) => setSenderEmail(e.target.value)} placeholder="alex@company.com" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Description</label>
              <Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional notes about this campaign" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Subject Line</label>
              <Input className="mt-1" value={subjectLine} onChange={(e) => setSubjectLine(e.target.value)} placeholder="Partnership Inquiry" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700">Message Body *</label>
              <Textarea className="mt-1 min-h-[120px]" value={messageBody} onChange={(e) => setMessageBody(e.target.value)} placeholder="Write your message..." />
            </div>
            <div className="flex justify-end">
              <Button disabled={!canProceedStep1} onClick={() => setStep(2)}>
                Next: Select Websites <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Select Target Websites ({allTargetUrls.length} selected)</CardTitle>
            <CardDescription>Choose existing websites from your database or paste new URLs below.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Direct Add New Website */}
            <div className="flex flex-col sm:flex-row gap-2 rounded-lg border border-slate-200/80 bg-slate-50/70 p-3">
              <Input
                className="flex-1 bg-white"
                placeholder="Add a new website URL directly (e.g. https://example.com)"
                value={newSiteUrl}
                onChange={(e) => setNewSiteUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newSiteUrl.trim()) {
                    e.preventDefault();
                    addSingleSiteMutation.mutate(newSiteUrl);
                  }
                }}
              />
              <Button
                type="button"
                size="sm"
                disabled={!newSiteUrl.trim() || addSingleSiteMutation.isPending}
                onClick={() => addSingleSiteMutation.mutate(newSiteUrl)}
              >
                <Plus className="h-4 w-4" />
                {addSingleSiteMutation.isPending ? "Adding..." : "Add Website"}
              </Button>
              <input ref={csvFileRef} type="file" accept=".csv" className="hidden" onChange={handleWizardCsvUpload} />
              <Button type="button" variant="outline" size="sm" onClick={() => csvFileRef.current?.click()}>
                <Upload className="h-4 w-4" /> Import CSV
              </Button>
            </div>

            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  className="pl-9"
                  placeholder="Filter existing websites..."
                  value={siteSearch}
                  onChange={(e) => setSiteSearch(e.target.value)}
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const urls = uniqueSites.map((w: any) => w.url);
                  setSelectedUrls(Array.from(new Set([...selectedUrls, ...urls])));
                }}
              >
                Select All Shown
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedUrls([])}>
                Clear
              </Button>
            </div>

            <div className="max-h-60 overflow-y-auto rounded-md border divide-y">
              {uniqueSites.map((w: any) => {
                const checked = selectedUrls.includes(w.url);
                return (
                  <label key={w.id} className="flex items-center justify-between px-3 py-2 text-sm hover:bg-slate-50 cursor-pointer">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <input type="checkbox" checked={checked} onChange={() => toggleUrl(w.url)} className="rounded border-slate-300" />
                      <span className="truncate text-slate-800">{w.url}</span>
                    </div>
                    <StatusBadge status={w.has_captcha ? "captcha" : w.form_found ? "scraped" : "pending"} />
                  </label>
                );
              })}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700">Or Import Additional URLs (one per line)</label>
              <Textarea
                className="mt-1 min-h-[90px]"
                placeholder="https://example.com/contact"
                value={manualUrls}
                onChange={(e) => setManualUrls(e.target.value)}
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              <Button disabled={!canProceedStep2} onClick={() => setStep(3)}>
                Next: Configure Fields <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3 */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Configure Form Fields</CardTitle>
            <CardDescription>Choose constant, custom, or random-pool values for each detected concept.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {conceptList.map((c) => {
              const cfg = strategies[c.key] || { strategy: "random", value: "" };
              return (
                <div key={c.key} className="grid grid-cols-1 gap-2 sm:grid-cols-12 items-center rounded-md border p-3">
                  <div className="sm:col-span-3">
                    <p className="text-sm font-medium text-slate-900">{c.label}</p>
                    <p className="text-[11px] font-mono text-slate-400">{c.key}</p>
                  </div>
                  <div className="sm:col-span-3">
                    <select
                      className="h-9 w-full rounded-md border border-input bg-white px-2.5 text-sm"
                      value={cfg.strategy}
                      onChange={(e) =>
                        setStrategies((prev) => ({
                          ...prev,
                          [c.key]: { ...cfg, strategy: e.target.value },
                        }))
                      }
                    >
                      <option value="constant">Constant Value</option>
                      <option value="random">Random Pool</option>
                      <option value="custom">Custom Value</option>
                    </select>
                  </div>
                  <div className="sm:col-span-6">
                    {cfg.strategy === "random" ? (
                      <div className="h-9 flex items-center rounded-md bg-slate-50 px-3 text-xs text-slate-500 border border-dashed">
                        Will pick randomly from approved "{c.key}" value pool
                      </div>
                    ) : (
                      <Input
                        placeholder={`Enter ${c.label.toLowerCase()}...`}
                        value={cfg.value}
                        onChange={(e) =>
                          setStrategies((prev) => ({
                            ...prev,
                            [c.key]: { ...cfg, value: e.target.value },
                          }))
                        }
                      />
                    )}
                  </div>
                </div>
              );
            })}

            <div className="flex justify-between pt-3">
              <Button variant="outline" onClick={() => setStep(2)}>
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              <Button onClick={() => setStep(4)}>
                Next: Review & Approve <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4 */}
      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Step 4: Review & Approval</CardTitle>
            <CardDescription>Verify campaign settings and explicitly approve before launching.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 rounded-md border bg-slate-50 p-4 text-sm">
              <div><span className="text-slate-500">Campaign Name:</span> <strong>{name}</strong></div>
              <div><span className="text-slate-500">Target Websites:</span> <strong>{allTargetUrls.length}</strong></div>
              <div><span className="text-slate-500">Sender:</span> <strong>{senderName || "—"} ({senderEmail})</strong></div>
              <div><span className="text-slate-500">Subject:</span> <strong>{subjectLine || "—"}</strong></div>
            </div>

            <label className="flex items-start gap-2.5 rounded-md border border-blue-200 bg-blue-50/60 p-4 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
                className="mt-1 rounded border-slate-300"
              />
              <span className="text-slate-700">
                I confirm these target websites are authorised for contact form submission, and I approve launching this campaign.
              </span>
            </label>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
              <Button variant="outline" onClick={() => setStep(3)}>
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              <div className="flex items-center gap-2">
                <Button variant="outline" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate(false)}>
                  Save as Draft
                </Button>
                <Button disabled={!approved || saveMutation.isPending} onClick={() => saveMutation.mutate(true)}>
                  <CheckCircle2 className="h-4 w-4" />
                  {saveMutation.isPending ? "Launching..." : "Approve & Launch Campaign"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
