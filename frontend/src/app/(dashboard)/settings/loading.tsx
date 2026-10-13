export default function SettingsLoading() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4 py-8 sm:px-6 sm:py-12">
      <div className="w-full max-w-md">
        <div className="sm:rounded-xl sm:border sm:bg-card sm:p-8 sm:shadow-sm">
          <div className="flex flex-col items-center">
            <div className="size-24 animate-pulse rounded-full bg-muted sm:size-28" />
            <div className="mt-4 h-6 w-36 animate-pulse rounded bg-muted" />
            <div className="mt-2 h-4 w-48 animate-pulse rounded bg-muted" />
          </div>
          <div className="mt-8 space-y-3">
            <div className="h-11 w-full animate-pulse rounded-md bg-muted sm:h-10" />
            <div className="h-11 w-full animate-pulse rounded-md bg-muted sm:h-10" />
          </div>
        </div>
      </div>
    </main>
  );
}
