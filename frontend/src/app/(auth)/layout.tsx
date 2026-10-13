import type { ReactNode } from "react";

import { QueryProvider } from "@/provider/query-provider";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <div className="flex flex-1 items-center justify-center">{children}</div>
    </QueryProvider>
  );
}
