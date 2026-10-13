import Link from "next/link";

import { ROUTES } from "@/config/routes.config";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Class Checker</h1>
        <p className="text-gray-600">
          Simple classroom attendance with QR codes and manual entry.
        </p>
      </div>
      <div className="flex gap-3">
        <Link
          href={ROUTES.AUTH.SIGNIN}
          className="rounded-md bg-blue-500 px-4 py-2 text-white"
        >
          Log in
        </Link>
        <Link
          href={ROUTES.AUTH.SIGNUP}
          className="rounded-md border border-gray-300 px-4 py-2"
        >
          Get started
        </Link>
      </div>
    </main>
  );
}
