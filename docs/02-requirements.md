# Classroom Attendance Web App

## System Requirements

## 1. Purpose

This document defines what the attendance application must do.

It separates functional requirements from quality requirements so implementation decisions can be traced back to a specific need.

## 2. Actors

The initial system has one primary authenticated actor:

`User`

The user represents the classroom owner or teacher using the application.

Students do not need application accounts in the initial version.

Students are represented as records in the classroom roster.

## 3. Authentication Requirements

### FR-AUTH-001

The system shall allow a user to register an account.

### FR-AUTH-002

The system shall allow a registered user to log in.

### FR-AUTH-003

The system shall reject invalid credentials.

### FR-AUTH-004

Protected application resources shall require authentication.

### FR-AUTH-005

The system shall maintain the authenticated user's identity for protected requests.

### FR-AUTH-006

A user shall only access classrooms they own or are explicitly authorized to access.

### FR-AUTH-007

The system shall allow the user to log out.

### FR-AUTH-008

Passwords shall never be stored as plaintext.

## 4. Classroom Requirements

### FR-CLASS-001

An authenticated user shall be able to create a classroom.

### FR-CLASS-002

A classroom shall have a human-readable name.

Example:

```text
BSIT-2B
```

### FR-CLASS-003

A classroom shall belong to one account.

### FR-CLASS-004

A user shall be able to view their classrooms.

### FR-CLASS-005

A user shall be able to open a classroom.

### FR-CLASS-006

A user shall be able to rename a classroom.

### FR-CLASS-007

The system shall preserve attendance history when a classroom name changes.

### FR-CLASS-008

A classroom shall contain student memberships.

## 5. Student Requirements

### FR-STUDENT-001

The system shall allow creation of a reusable student record.

### FR-STUDENT-002

A student shall have a Student ID.

### FR-STUDENT-003

Student ID shall be unique.

### FR-STUDENT-004

A student shall have a full name.

### FR-STUDENT-005

A student may have a program.

### FR-STUDENT-006

A student may have additional academic information required by the application.

### FR-STUDENT-007

The system shall allow an existing student to be added to a classroom.

### FR-STUDENT-008

The system shall prevent duplicate membership in the same classroom.

### FR-STUDENT-009

The system shall allow student search.

### FR-STUDENT-010

The system shall display students belonging to the selected classroom.

## 6. QR Requirements

### FR-QR-001

The system shall generate a QR representation for each student.

### FR-QR-002

The QR shall represent the student's Student ID or a stable identifier that resolves to the student.

### FR-QR-003

The QR shall not contain passwords.

### FR-QR-004

The QR shall not contain attendance status.

### FR-QR-005

The QR shall not contain session-specific information.

### FR-QR-006

The user shall be able to display a student's QR code.

### FR-QR-007

The system should support downloading or printing student QR codes.

### FR-QR-008

The scanner shall extract the identifier from a QR code.

## 7. Attendance Session Requirements

### FR-SESSION-001

The user shall be able to start attendance for a classroom.

### FR-SESSION-002

Starting attendance shall create an attendance session.

### FR-SESSION-003

A session shall reference exactly one classroom.

### FR-SESSION-004

A session shall have a date.

### FR-SESSION-005

A session shall have a lifecycle state.

### FR-SESSION-006

An active session shall accept attendance input.

### FR-SESSION-007

A finalized session shall reject new attendance input.

### FR-SESSION-008

The system shall prevent unauthorized users from modifying another user's session.

## 8. Attendance Record Requirements

### FR-ATT-001

Every classroom member included in an attendance session shall have an initial pending state.

### FR-ATT-002

A valid QR scan shall mark the student present.

### FR-ATT-003

A valid manual Student ID shall mark the student present.

### FR-ATT-004

A student shall only have one attendance record per session.

### FR-ATT-005

Repeated scans shall not create duplicate records.

### FR-ATT-006

A student must belong to the classroom before being marked present.

### FR-ATT-007

An attendance record shall store the current status.

### FR-ATT-008

An attendance record should store when the student was marked present.

### FR-ATT-009

An attendance record should store the input method.

### FR-ATT-010

The input method shall distinguish QR from manual entry.

## 9. Finalization Requirements

### FR-FINAL-001

The user shall be able to review attendance before finalization.

### FR-FINAL-002

The user shall explicitly confirm finalization.

### FR-FINAL-003

Finalization shall change all remaining pending records to absent.

### FR-FINAL-004

Finalization shall close the session.

### FR-FINAL-005

A finalized session shall remain available in attendance history.

### FR-FINAL-006

A finalized session shall not accept normal attendance input.

### FR-FINAL-007

Export shall not be responsible for finalizing a session.

## 10. Attendance History Requirements

### FR-HISTORY-001

The classroom shall display previous attendance sessions.

### FR-HISTORY-002

A session history entry shall identify its classroom.

### FR-HISTORY-003

A session history entry shall show the attendance date.

### FR-HISTORY-004

The system shall display present and absent counts.

### FR-HISTORY-005

The user shall be able to open a finalized session.

### FR-HISTORY-006

The user shall be able to view student-level attendance results.

## 11. Export Requirements

### FR-EXPORT-001

The system shall export finalized attendance data to Excel.

### FR-EXPORT-002

Export shall read the database's finalized records.

### FR-EXPORT-003

Export shall include Student ID.

### FR-EXPORT-004

Export shall include student name.

### FR-EXPORT-005

Export shall include classroom information.

### FR-EXPORT-006

Export shall include attendance status.

### FR-EXPORT-007

Export should include marked time when applicable.

### FR-EXPORT-008

Export should include attendance input method.

### FR-EXPORT-009

Export should use a predictable filename.

Example:

```text
BSIT-2B_Attendance_2026-10-03.xlsx
```

## 12. Validation Requirements

### FR-VAL-001

Required fields shall be validated.

### FR-VAL-002

Student ID shall be validated before lookup.

### FR-VAL-003

Malformed QR content shall be rejected.

### FR-VAL-004

Unknown Student IDs shall return a useful error.

### FR-VAL-005

Students outside the current classroom shall be rejected.

### FR-VAL-006

Attendance input for finalized sessions shall be rejected.

### FR-VAL-007

Duplicate attendance shall be rejected or treated as already present.

## 13. Security Requirements

### NFR-SEC-001

Passwords shall be securely hashed.

### NFR-SEC-002

Authentication credentials shall not be exposed to the frontend unnecessarily.

### NFR-SEC-003

Authorization shall be checked on the server.

### NFR-SEC-004

Database queries shall use parameterized mechanisms provided by the database library.

### NFR-SEC-005

User-controlled data shall be validated.

### NFR-SEC-006

Sensitive errors shall not expose internal implementation details.

### NFR-SEC-007

Session ownership shall be verified before modification.

## 14. Data Integrity Requirements

### NFR-DATA-001

Student IDs shall be unique.

### NFR-DATA-002

Classroom memberships shall not be duplicated.

### NFR-DATA-003

Attendance records shall not be duplicated for one student and session.

### NFR-DATA-004

Foreign key relationships shall be enforced.

### NFR-DATA-005

Finalized attendance history shall remain consistent.

## 15. Usability Requirements

### NFR-UX-001

The attendance workflow should require few interactions.

### NFR-UX-002

The scanner should provide immediate feedback.

### NFR-UX-003

Manual Student ID entry should be available as a fallback.

### NFR-UX-004

Present, pending, and absent states should be visually distinguishable.

### NFR-UX-005

The finalization action should clearly warn the user that pending students will become absent.

### NFR-UX-006

The interface should work on common desktop and mobile screen sizes.

## 16. Performance Requirements

### NFR-PERF-001

Normal student lookups should be fast.

### NFR-PERF-002

Attendance marking should not require a full page reload.

### NFR-PERF-003

The scanner interface should remain responsive during repeated scans.

### NFR-PERF-004

Attendance history should use pagination when records become large.

## 17. Reliability Requirements

### NFR-REL-001

Attendance creation should be atomic.

### NFR-REL-002

A failed database transaction shall not leave partial attendance data.

### NFR-REL-003

Finalization shall update pending records consistently.

### NFR-REL-004

Export failures shall not modify attendance records.

## 18. Scope Rules

The first version focuses on:

- Accounts
- Classrooms
- Students
- QR codes
- Attendance sessions
- Attendance records
- Attendance history
- Excel export

The first version does not require:

- Student login
- Facial recognition
- GPS
- Biometrics
- Complex grading
- Automated schedule generation

## 19. Acceptance Criteria

The core feature is complete when a user can perform:

```text
Register
 ↓
Login
 ↓
Create BSIT-2B
 ↓
Add students
 ↓
Generate QR
 ↓
Start attendance
 ↓
Scan or enter Student ID
 ↓
Present
 ↓
Review pending
 ↓
Finalize
 ↓
Pending becomes absent
 ↓
Export Excel
```

All historical records must remain accessible after export.

## 20. Requirement Traceability

The architecture document should explain how these requirements are implemented.

The database document should map requirements to entities.

The API document should map requirements to endpoints.

The workflow document should map requirements to user interactions.

This keeps implementation decisions traceable.
