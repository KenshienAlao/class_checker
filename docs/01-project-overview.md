# Classroom Attendance Web App

## Project Overview

- Project type: Classroom attendance management web application
- Primary purpose: Manage classroom rosters and record attendance efficiently
- Primary attendance methods: QR scanning and manual Student ID entry
- Primary output: Persistent attendance history and Excel reports
- Authentication: Account-based login
- Classroom ownership: Each classroom belongs to an authenticated account
- Student identity: Student ID is the unique business identifier
- QR identity: QR code represents the student's Student ID
- Attendance model: Session-based
- Attendance states: `PENDING`, `PRESENT`, `ABSENT`
- Finalization rule: Unscanned pending students become absent when a session is finalized
- Export rule: Excel export reads finalized attendance records
- Architectural goal: Clean separation between presentation, application logic, persistence, and database
- Documentation goal: Provide a stable blueprint before implementation

## 1. Problem

Manual classroom attendance can be slow, repetitive, and difficult to preserve as a reliable historical record.

A teacher may need to:

1. Maintain a list of students.
2. Remember or repeatedly type Student IDs.
3. Record who is present.
4. Determine who was not recorded.
5. Prepare a final attendance list.
6. Keep previous attendance records organized.
7. Produce a spreadsheet for submission or storage.

The application addresses these tasks through a reusable classroom roster and attendance sessions.

## 2. Core Idea

The classroom is the central workspace.

A user creates a classroom such as:

`BSIT-2B`

The user then adds students to that classroom.

Each student has:

- Full name
- Student ID
- Program
- Section or classroom membership
- Generated QR representation of the Student ID

When attendance is needed, the user starts an attendance session.

During the session, a student can be recorded through:

- QR scanning
- Manual Student ID entry

Both methods use the same backend attendance logic.

## 3. Main Entities

The initial domain contains:

- User
- Classroom
- Student
- ClassroomStudent
- AttendanceSession
- AttendanceRecord

These entities should remain conceptually separate.

A User owns classrooms.

A Classroom contains student memberships.

A Student represents a reusable student identity.

A ClassroomStudent represents membership of a student in a classroom.

An AttendanceSession represents one attendance event.

An AttendanceRecord represents one student's result in that session.

## 4. Account Model

A user must authenticate before accessing protected classroom data.

The account is the ownership boundary.

Example:

```text
User
 ├── BSIT-2B
 ├── BSIT-2A
 └── BSIT-1B
```

A user should not automatically see another user's classrooms.

The backend must enforce ownership.

Frontend hiding is not sufficient for authorization.

## 5. Classroom Model

A classroom is a reusable roster.

Example:

```text
BSIT-2B
```

A classroom can contain many students.

The classroom can also have many attendance sessions over time.

Example:

```text
BSIT-2B
 ├── Students
 ├── Attendance Session: October 1
 ├── Attendance Session: October 3
 └── Attendance Session: October 5
```

The classroom remains after an attendance session is completed.

## 6. Student Model

A student is stored independently from a specific attendance event.

Example:

```text
Name: Clarenze Kenshien A. Alao
Student ID: 25-09759
Program: BSIT
```

The Student ID is the primary business identifier.

The database should still use an internal primary key such as UUID or integer ID.

The Student ID should have a unique database constraint.

## 7. Reusable Students

A student can be reused when creating or managing another classroom.

The system should avoid unnecessary duplicate student records.

Example:

```text
Student
25-09759
Clarenze Kenshien A. Alao

        │
        ├── BSIT-2B
        └── another classroom
```

The membership relationship should be represented separately.

## 8. QR Code Model

The QR code should identify the student.

Recommended payload:

```text
25-09759
```

or a stable application-specific identifier containing the Student ID.

The QR should not need to contain:

- Passwords
- Attendance status
- Session information
- Teacher credentials
- Private account data

The backend resolves the scanned identifier.

## 9. Attendance Session

Attendance is recorded through a session.

Example:

```text
Classroom: BSIT-2B
Date: October 3, 2026
Status: ACTIVE
```

The session has a lifecycle:

```text
ACTIVE
  ↓
FINALIZED
```

While active, attendance records can move from pending to present.

When finalized, remaining pending records become absent.

## 10. Attendance States

Every student in the session begins as:

`PENDING`

A successful scan or manual Student ID entry changes the record to:

`PRESENT`

When the session is finalized:

`PENDING -> ABSENT`

The final state must not remain pending.

## 11. Attendance Input

QR and manual entry are two input mechanisms.

They should converge into one application service.

```text
QR Scanner
     │
     ├── Student ID
     │
Manual Input
     │
     └── Student ID
            ↓
    Attendance Service
            ↓
       Validation
            ↓
      Attendance Record
```

This prevents duplicate business logic.

## 12. Duplicate Prevention

A student can only have one attendance record per session.

The database should enforce:

```text
UNIQUE(session_id, student_id)
```

The service should also check for an existing record before inserting.

This gives both application-level and database-level protection.

## 13. Classroom Membership Validation

A scanned student must belong to the classroom associated with the current session.

Example:

```text
Session: BSIT-2B
Scanned student: 25-09759
Membership: BSIT-2B
Result: accepted
```

If the student is not a member:

```text
Session: BSIT-2B
Scanned student: student from another class
Result: rejected
```

The attendance record should not be created.

## 14. Manual Entry

Manual entry is a fallback and a valid attendance method.

Example:

```text
Student ID:
[ 25-09759 ]

[ Mark Present ]
```

The same service validates the Student ID.

Manual entry must not bypass:

- Classroom membership
- Session status
- Duplicate checks
- Student existence
- Authorization

## 15. Session Finalization

The user explicitly finalizes the session.

Recommended flow:

```text
Check Attendance
      ↓
Review
      ↓
End Attendance
      ↓
Confirm
      ↓
Finalize Session
      ↓
Pending -> Absent
```

Export should happen after finalization.

## 16. Excel Export

Excel is a reporting output.

Export should not change database state.

Recommended flow:

```text
Finalize
   ↓
Database contains final statuses
   ↓
Export reads records
   ↓
XLSX generated
```

The export may contain:

- Student ID
- Student name
- Program
- Classroom
- Attendance date
- Status
- Scan time
- Input method

## 17. Attendance History

The classroom should expose previous sessions.

Example:

```text
BSIT-2B

October 5
32 Present
3 Absent

October 3
31 Present
4 Absent

October 1
30 Present
5 Absent
```

History should remain accessible after export.

## 18. Student Attendance History

A student can have attendance records across sessions.

Example:

```text
Clarenze Kenshien A. Alao
25-09759

October 5    Present
October 3    Present
October 1    Absent
```

This enables future attendance statistics.

## 19. Main Screens

The initial interface should contain:

- Login
- Register
- Dashboard
- Classroom list
- Classroom detail
- Student management
- Attendance session
- QR scanner
- Attendance review
- Attendance history
- Student attendance history

## 20. Dashboard

The dashboard summarizes owned classrooms and recent activity.

Potential information:

- Number of classrooms
- Total students across classrooms
- Recent sessions
- Recent attendance activity

Avoid making the dashboard responsible for core business operations.

## 21. Classroom Detail

The classroom page is the central workspace.

It should provide:

- Classroom name
- Student count
- Student checklist
- Add student
- Existing student selection
- Check Attendance
- Attendance history

## 22. Student Management

Student management should support:

- Create student
- Search student
- Add student to classroom
- View student
- Edit student
- Generate QR
- View attendance history

Deleting a student should be handled carefully because historical attendance depends on student identity.

## 23. Authentication

Protected operations include:

- Classroom creation
- Student management
- Attendance creation
- Attendance finalization
- Attendance history
- Export

Authentication identifies the account.

Authorization verifies that the account owns or can access the requested classroom.

## 24. Architectural Principle

The application should follow:

```text
UI
 ↓
API Router
 ↓
Application Service
 ↓
Repository
 ↓
Database
```

The UI should not contain business rules.

The router should not contain complex database workflows.

The repository should not decide attendance policy.

The service layer should coordinate business rules.

## 25. Project Success Criteria

The application is successful when a user can:

1. Create an account.
2. Log in.
3. Create a classroom.
4. Add students.
5. Generate QR codes.
6. Start attendance.
7. Scan QR codes.
8. Enter Student IDs manually.
9. Prevent duplicate attendance.
10. Finalize attendance.
11. Convert pending students to absent.
12. Review attendance history.
13. Export final records to Excel.

## 26. Non-Goals for the Initial Version

The first version does not need:

- Facial recognition
- GPS tracking
- Complex analytics
- Biometric authentication
- Student self-service accounts
- Public QR endpoints
- Automatic attendance without an active session

Keeping these out of the initial scope reduces unnecessary complexity.

## 27. Final Concept

The application is a classroom-centered attendance system.

The central relationship is:

```text
Account
  ↓
Classroom
  ↓
Students
  ↓
Attendance Sessions
  ↓
Attendance Records
```

QR scanning and manual Student ID entry are simply two ways to create a present attendance record.

The database remains the source of truth.

Excel is a generated report, not the primary storage system.

This distinction should guide the rest of the architecture.
