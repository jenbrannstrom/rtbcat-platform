import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ title = "Error", message, onRetry }: ErrorProps) {
  return (
    <div className="rounded-lg bg-red-50 p-4">
      <div className="flex">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <div className="ml-3">
          <h3 className="text-sm font-medium text-red-800">{title}</h3>
          <p className="mt-1 text-sm text-red-700">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 inline-flex items-center text-sm font-medium text-red-700 hover:text-red-600"
            >
              <RefreshCw className="mr-1 h-4 w-4" />
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function ErrorPage({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
      <AlertCircle className="h-12 w-12 text-red-400" />
      <h2 className="mt-4 text-lg font-semibold text-gray-900">{title}</h2>
      <p className="mt-2 text-sm text-gray-600 text-center max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-primary mt-4">
          <RefreshCw className="mr-2 h-4 w-4" />
          Try again
        </button>
      )}
    </div>
  );
}
