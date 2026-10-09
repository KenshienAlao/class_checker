# Classroom Attendance Web App Documentation

This directory contains the initial architecture and requirements blueprint.

## Documents

1. `01-project-overview.md` — project concept, domain model, scope, and success criteria.
2. `02-requirements.md` — functional and non-functional requirements.
3. `03-architecture.md` — application layers, responsibilities, security boundaries, and structure.
4. `04-database-erd.md` — database entities, relationships, constraints, and ERD.
5. `05-attendance-workflow-api.md` — attendance lifecycle, QR/manual flow, finalization, export, and API blueprint.

## Core rule

```text
Classroom
  ↓
Attendance Session
  ↓
PENDING
  ├── QR / MANUAL → PRESENT
  └── Finalize → ABSENT
  ↓
Finalized Records
  ↓
Excel Export
```

The database is the source of truth. Excel is a report generated from finalized records.
