# Classroom Attendance Web App

## System Architecture

## 1. Architectural Goal

The system should be simple enough for a classroom project while following professional separation of concerns.

The recommended flow is:

```text
Client
  ↓
API Router
  ↓
Application Service
  ↓
Repository
  ↓
Database
```

Each layer has a specific responsibility.

## 2. High-Level Architecture

```text
┌──────────────────────────────┐
│          Web Client          │
│ Dashboard / Classroom / QR   │
└──────────────┬───────────────┘
               │ HTTP
               ▼
┌──────────────────────────────┐
│          FastAPI API         │
│ Routers / Validation / Auth  │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│       Application Layer      │
│ Attendance / Classroom /     │
│ Student / Authentication     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│       Repository Layer       │
│ Student / Classroom /        │
│ Attendance persistence       │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│         PostgreSQL           │
└──────────────────────────────┘
```

## 3. Frontend Responsibility

The frontend is responsible for:

- Rendering pages
- Form input
- QR camera access
- Loading states
- Error presentation
- Attendance status presentation
- Calling backend APIs
- Maintaining local UI state

The frontend should not decide whether a student belongs to a classroom.

The backend must decide that.

## 4. Backend Responsibility

The backend is responsible for:

- Authentication
- Authorization
- Input validation
- Business rules
- Attendance state transitions
- Duplicate prevention
- Classroom membership checks
- Database operations
- Excel generation

The backend is the source of truth.

## 5. Router Layer

Routers define HTTP endpoints.

Example:

```text
POST /api/auth/login
POST /api/classrooms
GET  /api/classrooms
GET  /api/classrooms/{id}
POST /api/attendance-sessions
POST /api/attendance-sessions/{id}/scan
POST /api/attendance-sessions/{id}/manual
POST /api/attendance-sessions/{id}/finalize
GET  /api/attendance-sessions/{id}
GET  /api/attendance-sessions/{id}/export
```

Routers should remain thin.

## 6. Service Layer

Services contain application rules.

Example service:

```text
AttendanceService
```

Possible methods:

```text
create_session()
mark_present()
finalize_session()
get_session()
export_session()
```

The service coordinates repositories.

## 7. Repository Layer

Repositories isolate database access.

Example:

```text
StudentRepository
ClassroomRepository
MembershipRepository
AttendanceSessionRepository
AttendanceRepository
UserRepository
```

A repository should answer persistence questions.

It should not decide whether a session may be finalized.

## 8. Authentication Service

Authentication handles:

- Registration
- Password hashing
- Login
- Token or session creation
- Logout
- Current user resolution

Authorization is a separate concern.

## 9. Authorization

Every protected classroom operation should verify ownership.

Example:

```text
Request
 ↓
Authenticated User
 ↓
Classroom ID
 ↓
Check classroom.owner_id == current_user.id
 ↓
Allow or reject
```

Do not rely on the frontend to hide unauthorized classrooms.

## 10. Classroom Service

Classroom service responsibilities:

- Create classroom
- Rename classroom
- List classrooms
- Get classroom details
- Add student membership
- Remove membership when allowed

It should not directly implement QR scanning.

## 11. Student Service

Student service responsibilities:

- Create student
- Search students
- Update student
- Retrieve student
- Generate QR representation

Student identity should remain reusable.

## 12. Attendance Service

Attendance service is the core business layer.

Responsibilities:

- Create session
- Initialize pending records
- Mark student present
- Validate membership
- Prevent duplicate attendance
- Finalize session
- Convert pending to absent
- Retrieve records

## 13. Single Attendance Path

QR and manual input should converge.

```text
QR Scanner
    ↓
extract_student_id()
    ↓
mark_present()

Manual Input
    ↓
validate_student_id()
    ↓
mark_present()
```

The service method `mark_present()` should contain the shared business logic.

## 14. Attendance State Machine

```text
                 ┌───────────┐
                 │  PENDING  │
                 └─────┬─────┘
                       │
              QR / MANUAL
                       │
                       ▼
                 ┌───────────┐
                 │  PRESENT  │
                 └───────────┘

PENDING
   │
   │ finalize
   ▼
 ABSENT
```

There should be no normal transition from present back to pending.

## 15. Finalization Transaction

Finalization should happen transactionally.

Conceptually:

```text
BEGIN
 ↓
Verify session ownership
 ↓
Verify session is active
 ↓
Update pending -> absent
 ↓
Update session -> finalized
 ↓
COMMIT
```

If an error occurs, the transaction should roll back.

## 16. Database as Source of Truth

The frontend may display:

```text
Present: 31
Pending: 4
```

but the database remains authoritative.

A refresh should reproduce the same state from the backend.

## 17. QR Scanner Architecture

The scanner belongs primarily to the frontend.

The frontend:

1. Requests camera permission.
2. Detects QR content.
3. Extracts Student ID.
4. Sends Student ID to backend.
5. Displays response.

The frontend should not directly modify attendance state.

## 18. QR Validation

The backend should validate:

- Session exists
- Session is active
- Student exists
- Student belongs to classroom
- Student has not already been marked present

Only then should attendance be recorded.

## 19. Manual Input Architecture

Manual input follows the same path.

```text
Input Student ID
       ↓
Frontend validation
       ↓
API request
       ↓
AttendanceService.mark_present()
       ↓
Database
```

Frontend validation is for usability.

Backend validation is for correctness.

## 20. Excel Architecture

Excel generation belongs outside the attendance state transition.

```text
Finalized Session
      ↓
Query records
      ↓
Transform rows
      ↓
Generate XLSX
      ↓
Return file
```

Export should not perform:

```text
PENDING -> ABSENT
```

That belongs to finalization.

## 21. Suggested Backend Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── classrooms.py
│   │   ├── students.py
│   │   └── attendance.py
│   ├── schemas/
│   ├── models/
│   ├── services/
│   ├── repositories/
│   └── exports/
└── tests/
```

This structure can evolve without changing the domain model.

## 22. Suggested Frontend Structure

```text
frontend/
├── app/
│   ├── login/
│   ├── register/
│   ├── dashboard/
│   ├── classrooms/
│   └── attendance/
├── components/
│   ├── classroom/
│   ├── student/
│   ├── attendance/
│   └── qr/
├── lib/
│   ├── api/
│   ├── validation/
│   └── utils/
└── types/
```

## 23. API Boundary

The frontend should communicate through documented API contracts.

Example request:

```json
{
  "student_id": "25-09759"
}
```

Example success response:

```json
{
  "student_id": "25-09759",
  "status": "PRESENT",
  "method": "MANUAL"
}
```

The exact response envelope can be standardized later.

## 24. Error Handling

Expected errors should be represented clearly.

Examples:

```text
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
```

A duplicate attendance can reasonably use `409 Conflict` or an idempotent success response, depending on the chosen API contract.

## 25. Domain Errors

The service layer can use domain-specific errors such as:

```text
ClassroomNotFound
StudentNotFound
StudentNotInClassroom
SessionNotActive
AttendanceAlreadyMarked
SessionAlreadyFinalized
```

The API layer converts these into HTTP responses.

## 26. Data Ownership

The ownership hierarchy is:

```text
User
  ↓
Classroom
  ↓
AttendanceSession
```

Student records may be reusable.

Classroom membership determines whether a student is eligible for a session.

## 27. Auditability

Attendance records should retain:

- Status
- Marked timestamp
- Input method
- Session ID
- Student ID

Optional future audit fields:

- Updated timestamp
- Updated by
- Correction reason

## 28. Concurrency

The backend must assume that two requests can arrive close together.

Example:

```text
QR scan
Manual input
```

Both may attempt to mark the same student.

Database uniqueness should protect the record.

The service should handle the resulting conflict cleanly.

## 29. Idempotency

Repeated scans should not create multiple attendance records.

A repeated scan can return:

```text
Already present
```

instead of creating another row.

This makes the attendance operation predictable.

## 30. Session Isolation

Each attendance session is independent.

Example:

```text
October 1
Session A
25-09759 PRESENT

October 3
Session B
25-09759 ABSENT
```

A student's previous attendance must not affect the initial state of a new session.

## 31. Historical Integrity

Finalized sessions should preserve historical results.

Deleting or editing a student should not silently rewrite old attendance data.

The implementation should use stable foreign keys and appropriate deletion rules.

## 32. Soft Deletion

For important historical entities, soft deletion may be preferable.

For example:

```text
Student.active = false
```

instead of physically deleting the record.

This can be decided during database implementation.

## 33. Scalability

The initial architecture should support:

- Multiple classrooms
- Hundreds of students
- Many attendance sessions
- Long-term attendance history

Pagination and indexes should be introduced where needed.

## 34. Indexing

Likely indexes include:

```text
users.email
students.student_id
classroom_students.classroom_id
classroom_students.student_id
attendance_sessions.classroom_id
attendance_sessions.created_at
attendance_records.session_id
attendance_records.student_id
```

The unique session/student constraint also creates an important lookup path.

## 35. Testing Architecture

Tests should exist at multiple levels.

Unit tests:

- Attendance state transitions
- Validation
- Duplicate detection

Integration tests:

- API + database
- Authentication
- Session finalization

End-to-end tests:

- Login
- Create classroom
- Start attendance
- Scan/manual entry
- Finalize
- Export

## 36. Architectural Rule

No frontend feature should become the source of truth.

No router should become the business layer.

No repository should become the business layer.

No export function should modify attendance state.

No QR code should directly create database records without validation.

## 37. Final Architecture

The intended architecture is:

```text
                    WEB CLIENT
                        │
                        ▼
                  API ROUTERS
                        │
                        ▼
                 APPLICATION SERVICES
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
      DOMAIN RULES             REPOSITORIES
                                    │
                                    ▼
                                POSTGRESQL
```

This gives the project a clean separation of responsibilities while keeping the implementation understandable.
