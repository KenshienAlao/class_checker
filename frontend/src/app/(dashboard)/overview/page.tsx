"use client";

import { useMemo, useState, type FormEvent } from "react";
import { z } from "zod";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  CalendarCheckIcon,
  ChevronRightIcon,
  ClockIcon,
  InboxIcon,
  MenuIcon,
  PersonIcon,
  PlusIcon,
  SchoolIcon,
  SearchIcon,
  UserPlusIcon,
  UsersIcon,
} from "@/components/icons";

/* ── Data ───────────────────────────────────────────────────────── */

type Classroom = {
  id: string;
  name: string;
  section: string;
  grade: string;
  students: number;
  schedule: string;
  room: string;
  attendanceRate: number | null;
};

const MOCK: Classroom[] = [
  {
    id: "c1",
    name: "Mathematics 10",
    section: "Section Rizal",
    grade: "Grade 10",
    students: 38,
    schedule: "Mon/Wed/Fri · 8:00 AM",
    room: "Room 204",
    attendanceRate: 94,
  },
  {
    id: "c2",
    name: "Earth Science",
    section: "Section Mabini",
    grade: "Grade 9",
    students: 41,
    schedule: "Tue/Thu · 10:30 AM",
    room: "Lab 2",
    attendanceRate: 89,
  },
  {
    id: "c3",
    name: "English Literature",
    section: "Section Bonifacio",
    grade: "Grade 10",
    students: 36,
    schedule: "Mon/Wed · 1:00 PM",
    room: "Room 110",
    attendanceRate: 97,
  },
  {
    id: "c4",
    name: "Filipino 8",
    section: "Section Luna",
    grade: "Grade 8",
    students: 40,
    schedule: "Daily · 9:00 AM",
    room: "Room 301",
    attendanceRate: 91,
  },
  {
    id: "c5",
    name: "Research Club",
    section: "Elective",
    grade: "Grade 11",
    students: 0,
    schedule: "Fri · 3:00 PM",
    room: "Library",
    attendanceRate: null,
  },
];

const GRADES = [
  "All",
  "Grade 8",
  "Grade 9",
  "Grade 10",
  "Grade 11",
  "Grade 12",
];

const ROSTER_FIELDS = [
  "Student ID",
  "First name",
  "Middle name",
  "Last name",
  "Suffix",
  "Email",
  "Contact no.",
];

const createSchema = z.object({
  name: z.string().trim().min(1, "Classroom name is required").max(80),
  section: z.string().trim().min(1, "Section is required").max(60),
  grade: z.string().min(1, "Choose a grade"),
});

export default function OverviewPage() {
  const [classrooms, setClassrooms] = useState<Classroom[]>(MOCK);
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("All");
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<Classroom | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return classrooms.filter(
      (c) =>
        (grade === "All" || c.grade === grade) &&
        (!q || `${c.name} ${c.section} ${c.room}`.toLowerCase().includes(q)),
    );
  }, [classrooms, query, grade]);

  const totalStudents = classrooms.reduce((s, c) => s + c.students, 0);
  const rated = classrooms.filter((c) => c.attendanceRate !== null);
  const avgRate = rated.length
    ? Math.round(
        rated.reduce((s, c) => s + (c.attendanceRate ?? 0), 0) / rated.length,
      )
    : null;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card animate-fade-in">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Link
                  href="/settings"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  aria-label="Profile settings"
                >
                  <PersonIcon className="h-5 w-5" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="bottom">Profile</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <div className="flex items-center gap-1">
            {/* Create classroom — always visible */}
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => setCreateOpen(true)}
                    className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label="Add classroom"
                  >
                    <PlusIcon className="h-5 w-5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom">Add classroom</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Desktop nav */}
            <nav
              aria-label="Main"
              className="hidden items-center gap-1 text-sm sm:flex"
            >
              <span
                aria-current="page"
                className="rounded-md bg-muted px-3 py-1.5 font-medium text-foreground"
              >
                Overview
              </span>
              <Link
                href="/"
                className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Log out
              </Link>
            </nav>

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileNavOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:hidden"
              aria-label="Open navigation menu"
            >
              <MenuIcon className="h-6 w-6" />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile navigation sheet */}
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="right" className="w-64">
          <SheetHeader>
            <SheetTitle>Navigation</SheetTitle>
            <SheetDescription className="sr-only">
              Main navigation menu
            </SheetDescription>
          </SheetHeader>
          <nav aria-label="Mobile" className="mt-6 flex flex-col gap-2 px-4">
            <span className="rounded-md bg-muted px-3 py-2 text-sm font-medium text-foreground">
              Overview
            </span>
            <Link
              href="/"
              onClick={() => setMobileNavOpen(false)}
              className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              Log out
            </Link>
          </nav>
        </SheetContent>
      </Sheet>

      {/* ── Main ────────────────────────────────────────────────── */}
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="animate-fade-in" style={{ animationDelay: "50ms" }}>
          <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">
            Overview
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Good to see you. Here&apos;s how your classes are doing today.
          </p>
        </div>

        <p
          className="mt-4 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground animate-fade-in"
          style={{ animationDelay: "100ms" }}
        >
          Demo data — nothing here is saved. Changes reset when you reload.
        </p>

        {/* ── Stats ──────────────────────────────────────────── */}
        <section
          aria-label="Summary"
          className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          <StatCard
            icon={SchoolIcon}
            label="Total classrooms"
            value={String(classrooms.length)}
            delay={0}
          />
          <StatCard
            icon={UsersIcon}
            label="Total students"
            value={String(totalStudents)}
            delay={1}
          />
          <StatCard
            icon={CalendarCheckIcon}
            label="Avg. attendance"
            value={avgRate === null ? "—" : `${avgRate}%`}
            hint={avgRate === null ? "No records yet" : "Across active classes"}
            delay={2}
          />
        </section>

        {/* ── Classrooms ─────────────────────────────────────── */}
        <section aria-labelledby="classrooms-heading" className="mt-10">
          <div
            className="grid grid-cols-1 gap-3 md:flex md:items-center md:justify-between animate-fade-in"
            style={{ animationDelay: "200ms" }}
          >
            <h2
              id="classrooms-heading"
              className="text-lg font-semibold text-foreground"
            >
              Your classrooms{" "}
              <span className="font-normal text-muted-foreground">
                ({filtered.length})
              </span>
            </h2>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative sm:w-64">
                <Label htmlFor="search" className="sr-only">
                  Search classrooms
                </Label>
                <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="search"
                  type="search"
                  placeholder="Search by name, section, room"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Label htmlFor="grade" className="sr-only">
                Filter by grade
              </Label>
              <select
                id="grade"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                className="h-9 rounded-md border border-input bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {GRADES.map((g) => (
                  <option key={g} value={g}>
                    {g === "All" ? "All grades" : g}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {classrooms.length === 0 ? (
            <EmptyState
              title="No classrooms yet"
              text="Create your first classroom to start adding students and taking attendance."
              action={
                <Button onClick={() => setCreateOpen(true)}>
                  <PlusIcon className="h-4 w-4" /> Create your first classroom
                </Button>
              }
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="No matching classrooms"
              text="Try a different search or grade filter."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setQuery("");
                    setGrade("All");
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ) : (
            <ul className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((c, i) => (
                <li
                  key={c.id}
                  className="animate-fade-up"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <ClassroomCard c={c} onOpen={() => setSelected(c)} />
                </li>
              ))}
            </ul>
          )}

          {classrooms.length > 0 && (
            <div className="mt-6 text-right">
              <button
                onClick={() => setClassrooms([])}
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              >
                Preview empty state
              </button>
            </div>
          )}
        </section>
      </main>

      <CreateClassroomDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={(c) => setClassrooms((prev) => [c, ...prev])}
      />
      <RosterPreview classroom={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────────── */

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  delay,
}: {
  icon: ({ className }: { className?: string }) => React.JSX.Element;
  label: string;
  value: string;
  hint?: string;
  delay: number;
}) {
  return (
    <div
      className="rounded-lg border bg-card p-4 animate-scale-in"
      style={{ animationDelay: `${120 + delay * 80}ms` }}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ClassroomCard({ c, onOpen }: { c: Classroom; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      aria-label={`Open ${c.name}, ${c.section} — view student roster`}
      className="group flex h-full w-full flex-col rounded-lg border bg-card p-4 text-left transition-[border-color,transform] duration-150 hover:-translate-y-0.5 hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:translate-y-0"
    >
      <div className="flex w-full items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-foreground">
            {c.section}
          </h3>
        </div>
        <span className="shrink-0 rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
          {c.grade}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Students</dt>
          <dd className="font-medium text-foreground">{c.students}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Attendance</dt>
          <dd className="font-medium text-foreground">
            {c.attendanceRate === null ? "—" : `${c.attendanceRate}%`}
          </dd>
        </div>
      </dl>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
        <ClockIcon className="h-3.5 w-3.5 shrink-0" />{" "}
        <span className="truncate">
          {c.schedule} · {c.room}
        </span>
      </p>
      <span className="mt-4 flex items-center gap-1 border-t pt-3 text-sm font-medium text-primary">
        View roster{" "}
        <ChevronRightIcon className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}

function EmptyState({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action: React.ReactNode;
}) {
  return (
    <div className="mt-4 flex flex-col items-center rounded-lg border border-dashed bg-card px-6 py-12 text-center animate-fade-in">
      <span className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <InboxIcon className="h-5 w-5" />
      </span>
      <h3 className="mt-3 font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{text}</p>
      <div className="mt-4">{action}</div>
    </div>
  );
}

function CreateClassroomDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreate: (c: Classroom) => void;
}) {
  const [form, setForm] = useState({ name: "", section: "", grade: "" });
  const [errors, setErrors] = useState<{
    name?: string | undefined;
    section?: string | undefined;
    grade?: string | undefined;
  }>({});

  function submit(e: FormEvent) {
    e.preventDefault();
    const r = createSchema.safeParse(form);
    if (!r.success) {
      const f = r.error.flatten().fieldErrors;
      setErrors({
        name: f.name?.[0],
        section: f.section?.[0],
        grade: f.grade?.[0],
      });
      return;
    }
    onCreate({
      id: crypto.randomUUID(),
      ...r.data,
      students: 0,
      schedule: "Schedule not set",
      room: "No room",
      attendanceRate: null,
    });
    setForm({ name: "", section: "", grade: "" });
    setErrors({});
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create classroom</DialogTitle>
          <DialogDescription>
            Demo only — this classroom won&apos;t be saved.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="space-y-4">
          <Field id="cname" label="Classroom name" error={errors.name}>
            <Input
              id="cname"
              value={form.name}
              placeholder="e.g. Biology 9"
              aria-invalid={!!errors.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field id="csection" label="Section" error={errors.section}>
            <Input
              id="csection"
              value={form.section}
              placeholder="e.g. Section Aguinaldo"
              aria-invalid={!!errors.section}
              onChange={(e) => setForm({ ...form, section: e.target.value })}
            />
          </Field>
          <Field id="cgrade" label="Grade" error={errors.grade}>
            <select
              id="cgrade"
              value={form.grade}
              aria-invalid={!!errors.grade}
              onChange={(e) => setForm({ ...form, grade: e.target.value })}
              className="h-9 w-full rounded-md border border-input bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Choose a grade</option>
              {GRADES.slice(1).map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}

function RosterPreview({
  classroom,
  onClose,
}: {
  classroom: Classroom | null;
  onClose: () => void;
}) {
  return (
    <Sheet open={!!classroom} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-xl">
        {classroom && (
          <>
            <SheetHeader>
              <SheetTitle>{classroom.name}</SheetTitle>
              <SheetDescription>
                {classroom.section} · {classroom.grade} · {classroom.students}{" "}
                students
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6 px-4">
              <p className="mb-2 text-xs text-muted-foreground">
                Roster preview — the full spreadsheet view comes in the next
                step.
              </p>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-140 text-left text-xs">
                  <thead className="bg-muted">
                    <tr>
                      {ROSTER_FIELDS.map((f) => (
                        <th
                          key={f}
                          scope="col"
                          className="border-r px-2 py-2 font-medium text-foreground last:border-r-0"
                        >
                          {f}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[0, 1, 2].map((r) => (
                      <tr key={r} className="border-t">
                        {ROSTER_FIELDS.map((f) => (
                          <td
                            key={f}
                            className="h-8 border-r last:border-r-0"
                          />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {classroom.students === 0 && (
                <div className="mt-6 rounded-md border border-dashed p-6 text-center">
                  <p className="text-sm text-foreground">
                    Looks like this classroom is empty. Would you like to add
                    some students?
                  </p>
                  <Button
                    className="mt-4"
                    disabled
                    title="Coming in a later step"
                  >
                    <UserPlusIcon className="h-4 w-4" /> Add students
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
