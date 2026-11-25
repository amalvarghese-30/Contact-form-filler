import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Plus, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export function NotificationsPage() {
  const qc = useQueryClient();
  const [newEmail, setNewEmail] = React.useState("");
  const [smtpHost, setSmtpHost] = React.useState("smtp.gmail.com");
  const [smtpPort, setSmtpPort] = React.useState(587);
  const [smtpUser, setSmtpUser] = React.useState("");
  const [smtpPassword, setSmtpPassword] = React.useState("");
  const [fromName, setFromName] = React.useState("Contact Form Filler");
  const [isEnabled, setIsEnabled] = React.useState(false);

  const { data: recipientsData, isLoading: recLoading } = useQuery({
    queryKey: ["notification-emails"],
    queryFn: () => api.listNotificationEmails(),
  });

  const { data: cfgData, isLoading: cfgLoading } = useQuery({
    queryKey: ["email-config"],
    queryFn: () => api.getEmailConfig(),
  });

  React.useEffect(() => {
    if (!cfgData) return;
    if (cfgData.smtp_host) setSmtpHost(cfgData.smtp_host);
    if (cfgData.smtp_port) setSmtpPort(Number(cfgData.smtp_port));
    if (cfgData.smtp_user) setSmtpUser(cfgData.smtp_user);
    if (cfgData.smtp_password) setSmtpPassword(cfgData.smtp_password);
    if (cfgData.from_name) setFromName(cfgData.from_name);
    if (typeof cfgData.is_enabled === "boolean") setIsEnabled(cfgData.is_enabled);
  }, [cfgData]);

  const addEmailMutation = useMutation({
    mutationFn: () => api.addNotificationEmail(newEmail),
    onSuccess: () => {
      toast.success("Recipient added");
      setNewEmail("");
      qc.invalidateQueries({ queryKey: ["notification-emails"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: number) => api.toggleNotificationEmail(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification-emails"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteNotificationEmail(id),
    onSuccess: () => {
      toast.success("Recipient deleted");
      qc.invalidateQueries({ queryKey: ["notification-emails"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveCfgMutation = useMutation({
    mutationFn: () =>
      api.updateEmailConfig({
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_user: smtpUser,
        smtp_password: smtpPassword || undefined,
        from_name: fromName,
        is_enabled: isEnabled,
      }),
    onSuccess: () => {
      toast.success("SMTP configuration saved");
      qc.invalidateQueries({ queryKey: ["email-config"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const testMutation = useMutation({
    mutationFn: () => api.sendTestEmail(),
    onSuccess: (res) => {
      if (res.ok) toast.success(res.message || "Test email sent");
      else toast.error(res.message || "Failed to send test email");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Email Notifications</h1>
          <p className="text-sm text-slate-500">Configure SMTP settings and manage recipients notified on successful submissions.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
          <Send className="h-4 w-4" />
          {testMutation.isPending ? "Sending..." : "Send Test Email"}
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recipients */}
        <Card>
          <CardHeader>
            <CardTitle>Notification Recipients</CardTitle>
            <CardDescription>Active recipients receive an email summary after each verified submission.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (newEmail.trim()) addEmailMutation.mutate();
              }}
            >
              <Input
                type="email"
                placeholder="recipient@company.com"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
              />
              <Button type="submit" size="sm" disabled={addEmailMutation.isPending}>
                <Plus className="h-4 w-4" /> Add
              </Button>
            </form>

            <div className="divide-y rounded-md border">
              {recLoading ? (
                <div className="p-4 space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
              ) : (recipientsData?.items || []).length === 0 ? (
                <p className="p-4 text-sm text-slate-400">No recipients configured.</p>
              ) : (
                recipientsData.items.map((r: any) => (
                  <div key={r.id} className="flex items-center justify-between px-3 py-2.5 text-sm">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Mail className="h-4 w-4 text-slate-400 shrink-0" />
                      <span className="truncate text-slate-800">{r.email}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleMutation.mutate(r.id)}
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium border ${
                          r.is_active
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-slate-100 text-slate-500 border-slate-200"
                        }`}
                      >
                        {r.is_active ? "Active" : "Paused"}
                      </button>
                      <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(r.id)}>
                        <Trash2 className="h-4 w-4 text-rose-500" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* SMTP Settings */}
        <Card>
          <CardHeader>
            <CardTitle>SMTP Configuration</CardTitle>
            <CardDescription>Credentials are stored securely on the backend and masked in API responses.</CardDescription>
          </CardHeader>
          <CardContent>
            {cfgLoading ? (
              <div className="space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
            ) : (
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  saveCfgMutation.mutate();
                }}
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <label className="text-xs font-medium text-slate-700">SMTP Host</label>
                    <Input className="mt-1" value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} required />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700">Port</label>
                    <Input className="mt-1" type="number" value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} required />
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-slate-700">SMTP Username</label>
                    <Input className="mt-1" value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} required />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-700">SMTP Password</label>
                    <Input className="mt-1" type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder="••••••••" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-700">Sender Display Name</label>
                  <Input className="mt-1" value={fromName} onChange={(e) => setFromName(e.target.value)} />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input type="checkbox" checked={isEnabled} onChange={(e) => setIsEnabled(e.target.checked)} className="rounded border-slate-300" />
                  Enable email notifications
                </label>
                <div className="flex justify-end">
                  <Button type="submit" disabled={saveCfgMutation.isPending}>
                    {saveCfgMutation.isPending ? "Saving..." : "Save Configuration"}
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
