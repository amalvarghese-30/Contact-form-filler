import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Layout } from "@/components/Layout";
import { Skeleton } from "@/components/ui/skeleton";

const DashboardPage = React.lazy(() => import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const WebsitesPage = React.lazy(() => import("@/pages/WebsitesPage").then((m) => ({ default: m.WebsitesPage })));
const WebsiteDetailsPage = React.lazy(() => import("@/pages/WebsiteDetailsPage").then((m) => ({ default: m.WebsiteDetailsPage })));
const CampaignsPage = React.lazy(() => import("@/pages/CampaignsPage").then((m) => ({ default: m.CampaignsPage })));
const CampaignWizardPage = React.lazy(() => import("@/pages/CampaignWizardPage").then((m) => ({ default: m.CampaignWizardPage })));
const CampaignDetailsPage = React.lazy(() => import("@/pages/CampaignDetailsPage").then((m) => ({ default: m.CampaignDetailsPage })));
const SubmissionsPage = React.lazy(() => import("@/pages/SubmissionsPage").then((m) => ({ default: m.SubmissionsPage })));
const AnalyticsPage = React.lazy(() => import("@/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })));
const FieldsPage = React.lazy(() => import("@/pages/FieldsPage").then((m) => ({ default: m.FieldsPage })));
const NotificationsPage = React.lazy(() => import("@/pages/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const SettingsPage = React.lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function PageLoader() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <BrowserRouter>
          <React.Suspense fallback={<PageLoader />}>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/websites" element={<WebsitesPage />} />
                <Route path="/websites/:id" element={<WebsiteDetailsPage />} />
                <Route path="/campaigns" element={<CampaignsPage />} />
                <Route path="/campaigns/new" element={<CampaignWizardPage />} />
                <Route path="/campaigns/:id/edit" element={<CampaignWizardPage />} />
                <Route path="/campaigns/:id" element={<CampaignDetailsPage />} />
                <Route path="/submissions" element={<SubmissionsPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/fields" element={<FieldsPage />} />
                <Route path="/notifications" element={<NotificationsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </React.Suspense>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
