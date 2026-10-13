import type { ReactNode } from "react";

import { QueryProvider } from "@/provider/query-provider";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <div>{children}</div>
    </QueryProvider>
  );
}
