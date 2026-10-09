# Classroom Attendance Web App

## Attendance Workflow and API Blueprint

## 1. Purpose

This document defines the detailed attendance workflow and the API boundaries required to implement it.

The goal is to ensure QR scanning and manual Student ID entry behave consistently.

## 2. Attendance Lifecycle

The complete lifecycle is:

```text
Classroom
    ↓
Start Attendance
    ↓
Create Session
    ↓
Create PENDING records
    ↓
Accept QR / Manual input
    ↓
Mark PRESENT
    ↓
Review
    ↓
Finalize
    ↓
PENDING -> ABSENT
    ↓
Session FINALIZED
    ↓
Export
```

## 3. Start Session

The user opens a classroom.

They select:

`Check Attendance`

The frontend sends a request to create a session.

Example:

```http
POST /api/classrooms/{classroom_id}/attendance-sessions
```

The backend must verify:

- User is authenticated.
- Classroom exists.
- User owns the classroom.
- No conflicting active session exists if the system chooses to allow only one.
- Classroom has eligible members.

## 4. Session Creation

The service creates:

```text
AttendanceSession
status = ACTIVE
```

It then loads classroom members.

For every member:

```text
AttendanceRecord
status = PENDING
```

The operation should be transactional.

## 5. Initial Attendance Screen

The frontend receives the session.

Example:

```text
BSIT-2B
Attendance
October 3, 2026

Present: 0
Pending: 35

[Scan QR]
[Enter Student ID]
[End Attendance]
```

The checklist displays all members.

## 6. QR Scanner Flow

The QR scanner detects:

```text
25-09759
```

The frontend does not directly mark the student.

It sends:

```http
POST /api/attendance-sessions/{session_id}/scan
```

Request:

```json
{
  "student_id": "25-09759"
}
```

## 7. Manual Entry Flow

The user types:

```text
25-09759
```

The frontend sends the same logical request.

It may use:

```http
POST /api/attendance-sessions/{session_id}/manual
```

Request:

```json
{
  "student_id": "25-09759"
}
```

The service can call the same internal method as QR attendance while setting:

```text
method = MANUAL
```

## 8. Shared Attendance Service

Both routes should converge on:

```text
AttendanceService.mark_present(
    session_id,
    student_id,
    method
)
```

Possible methods:

```text
QR
MANUAL
```

This is one of the most important architectural rules.

## 9. Mark Present Validation

The service should perform:

```text
1. Find session.
2. Verify session exists.
3. Verify session is ACTIVE.
4. Verify current user owns classroom.
5. Find student.
6. Verify student exists.
7. Verify student belongs to classroom.
8. Find attendance record.
9. Verify record is not already PRESENT.
10. Mark PRESENT.
11. Store marked_at.
12. Store method.
13. Commit.
```

## 10. Successful Response

Example:

```json
{
  "student_id": "25-09759",
  "student_name": "Clarenze Kenshien A. Alao",
  "status": "PRESENT",
  "method": "QR",
  "marked_at": "2026-10-03T08:14:23+08:00"
}
```

The frontend can immediately display:

```text
✓ PRESENT
Clarenze Kenshien A. Alao
25-09759
08:14 AM
```

## 11. Duplicate Scan

If the same QR is scanned again:

```text
25-09759
```

The backend finds the existing record.

It must not insert another record.

Possible response:

```json
{
  "student_id": "25-09759",
  "status": "PRESENT",
  "already_marked": true
}
```

The frontend can display:

```text
Already marked present
```

## 12. Unknown Student

If:

```text
25-99999
```

does not exist:

```text
404 Not Found
```

Response:

```json
{
  "code": "STUDENT_NOT_FOUND",
  "message": "Student was not found."
}
```

The frontend should show a short actionable message.

## 13. Student Outside Classroom

If a valid student belongs to another classroom:

```text
Student exists
Student is not a member of BSIT-2B
```

The request must be rejected.

Example:

```text
403 Forbidden
```

or a domain-specific conflict depending on the API contract.

The important rule is that the attendance record is not changed.

## 14. Session Not Active

If the session has already been finalized:

```text
POST /attendance-sessions/{id}/scan
```

must fail.

Example:

```text
409 Conflict
```

Response:

```json
{
  "code": "SESSION_NOT_ACTIVE",
  "message": "Attendance session is already finalized."
}
```

## 15. Review State

The frontend should retrieve the session:

```http
GET /api/attendance-sessions/{session_id}
```

Response should include:

- Session status
- Classroom
- Date
- Counts
- Student attendance records

Example:

```text
Present: 31
Pending: 4
Absent: 0
```

Before finalization, pending is visible.

## 16. End Attendance

The user clicks:

`End Attendance`

The frontend should first show confirmation.

Example:

```text
End attendance?

4 students are still pending.
They will be marked ABSENT.

[Cancel]
[Finalize Attendance]
```

This prevents accidental finalization.

## 17. Finalize Endpoint

Recommended endpoint:

```http
POST /api/attendance-sessions/{session_id}/finalize
```

The backend verifies:

- Authentication
- Ownership
- Session existence
- Session is active

Then performs the finalization transaction.

## 18. Finalization Operation

Conceptually:

```text
BEGIN

PENDING -> ABSENT

Session:
ACTIVE -> FINALIZED

Set finalized_at

COMMIT
```

The entire operation should succeed or fail as one transaction.

## 19. Finalized Response

Example:

```json
{
  "session_id": "500",
  "status": "FINALIZED",
  "present_count": 31,
  "absent_count": 4,
  "finalized_at": "2026-10-03T09:00:00+08:00"
}
```

## 20. Post-Finalization State

After finalization:

```text
Present: 31
Absent: 4
Pending: 0
```

There should be no pending records remaining.

## 21. Export Endpoint

Recommended:

```http
GET /api/attendance-sessions/{session_id}/export
```

The backend must verify:

- User owns the classroom.
- Session exists.
- Session is finalized.

The endpoint reads final records and generates XLSX.

## 22. Export Rule

Export does not modify:

```text
AttendanceRecord
AttendanceSession
```

It only reads them.

This keeps reporting separate from state transitions.

## 23. Excel Columns

Recommended columns:

```text
Student ID
Student Name
Program
Classroom
Date
Status
Marked Time
Method
```

Example:

```text
25-09759
Clarenze Kenshien A. Alao
BSIT
BSIT-2B
2026-10-03
PRESENT
08:14 AM
QR
```

An absent record may contain:

```text
Status: ABSENT
Marked Time: -
Method: -
```

## 24. Classroom API

Potential endpoints:

```text
GET    /api/classrooms
POST   /api/classrooms
GET    /api/classrooms/{id}
PATCH  /api/classrooms/{id}
DELETE /api/classrooms/{id}
```

Deletion may be disabled initially to protect history.

## 25. Student API

Potential endpoints:

```text
GET    /api/students
POST   /api/students
GET    /api/students/{id}
PATCH  /api/students/{id}
```

Classroom membership endpoints:

```text
POST   /api/classrooms/{id}/students
DELETE /api/classrooms/{id}/students/{student_id}
```

## 26. Session API

Potential endpoints:

```text
POST /api/classrooms/{id}/attendance-sessions
GET  /api/attendance-sessions/{id}
POST /api/attendance-sessions/{id}/scan
POST /api/attendance-sessions/{id}/manual
POST /api/attendance-sessions/{id}/finalize
GET  /api/attendance-sessions/{id}/export
```

The scan and manual endpoints can alternatively be merged if the request includes a `method` field.

## 27. Recommended Endpoint Separation

For readability:

```text
/scan
/manual
```

is easy for beginners to understand.

Internally both should call:

```text
mark_present()
```

This gives clear HTTP behavior without duplicating business logic.

## 28. Authentication API

Potential endpoints:

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

The exact session or token implementation can be finalized separately.

## 29. Authorization Dependency

Protected endpoints should resolve:

```text
current_user
```

before performing classroom operations.

A route should never trust a user ID supplied by the frontend.

## 30. Error Contract

Use a consistent error format.

Example:

```json
{
  "code": "STUDENT_NOT_IN_CLASSROOM",
  "message": "Student does not belong to this classroom."
}
```

Possible codes:

```text
INVALID_CREDENTIALS
CLASSROOM_NOT_FOUND
STUDENT_NOT_FOUND
STUDENT_NOT_IN_CLASSROOM
SESSION_NOT_FOUND
SESSION_NOT_ACTIVE
SESSION_ALREADY_FINALIZED
ATTENDANCE_ALREADY_MARKED
UNAUTHORIZED
FORBIDDEN
VALIDATION_ERROR
```

## 31. HTTP Status Guidelines

Use:

```text
200 OK
201 Created
204 No Content
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Entity
500 Internal Server Error
```

The exact use of `400` versus `422` depends on the validation approach.

## 32. Security Boundary

The browser is not trusted.

A malicious user could manually send:

```text
POST /api/attendance-sessions/123/finalize
```

Therefore the backend must independently verify every authorization condition.

## 33. QR Security Boundary

A QR code is an identifier, not proof that the person holding it is the student.

The application should treat the QR as an attendance input mechanism.

The initial project does not need to claim identity verification beyond the provided QR.

## 34. Scanner Failure

If camera access fails, the interface should keep manual Student ID input available.

Possible message:

```text
Camera unavailable.
Enter the Student ID manually.
```

This prevents the attendance workflow from depending entirely on camera hardware.

## 35. Network Failure

If a scan request fails because of a network problem, the frontend should not assume attendance was saved.

The interface should show:

```text
Unable to save attendance.
Please retry.
```

A success state should only appear after a successful backend response.

## 36. Repeated Requests

The backend must safely handle repeated requests.

The database constraint:

```text
UNIQUE(session_id, student_id)
```

protects against duplicate insertion.

The service should return a useful response rather than an unhandled database error.

## 37. Session Concurrency

If two users attempt to modify the same session in a future multi-user version, the service must still enforce session state and database constraints.

The initial application can keep one classroom owner as the primary operator.

## 38. Attendance Counts

Counts should preferably be derived from database records.

Example:

```text
PRESENT = count(status = PRESENT)
ABSENT = count(status = ABSENT)
PENDING = count(status = PENDING)
```

Avoid storing redundant counters unless performance later requires them.

## 39. Checklist Behavior

The classroom attendance screen should display:

```text
✓ PRESENT
○ PENDING
✕ ABSENT
```

During an active session:

```text
PRESENT
PENDING
```

will normally be visible.

After finalization:

```text
PRESENT
ABSENT
```

will be visible.

## 40. Final User Flow

```text
LOGIN
  ↓
DASHBOARD
  ↓
BSIT-2B
  ↓
CHECK ATTENDANCE
  ↓
CREATE SESSION
  ↓
PENDING FOR ALL MEMBERS
  ↓
┌────────────────────────────┐
│ Scan QR OR Enter Student ID│
└──────────────┬─────────────┘
               ↓
        Validate Student
               ↓
        Mark PRESENT
               ↓
          Continue
               ↓
        Review Checklist
               ↓
        End Attendance
               ↓
          Confirmation
               ↓
           FINALIZE
               ↓
       PENDING -> ABSENT
               ↓
       FINAL ATTENDANCE
               ↓
         EXPORT EXCEL
```

## 41. Architectural Outcome

The API should preserve a single business rule:

```text
Only valid classroom members can become PRESENT in an active session.
```

QR and manual input are simply different ways to provide the Student ID.

Finalization is the only normal operation that changes remaining pending records to absent.

Export only reports the finalized result.

This keeps the attendance system predictable, testable, and maintainable.
