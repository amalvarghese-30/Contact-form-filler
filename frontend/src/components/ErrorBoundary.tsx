import * as React from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || "Unexpected rendering error" };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border bg-white p-8 text-center">
          <AlertTriangle className="h-8 w-8 text-rose-500" />
          <h2 className="mt-3 text-base font-semibold text-slate-900">Something went wrong</h2>
          <p className="mt-1 text-sm text-slate-500">{this.state.message}</p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => this.setState({ hasError: false, message: "" })}
          >
            Try Again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
