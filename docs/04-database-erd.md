# Classroom Attendance Web App

## Database Design and ERD

## 1. Database Goal

The database must preserve:

- User accounts
- Reusable students
- Classroom ownership
- Classroom membership
- Attendance sessions
- Attendance records
- Historical attendance results

The database is the source of truth for attendance.

## 2. Core Tables

The initial schema contains:

```text
users
classrooms
students
classroom_students
attendance_sessions
attendance_records
```

Additional tables can be added for refresh tokens, audit logs, or settings if required.

## 3. Users

Table:

`users`

Purpose:

Stores authenticated application accounts.

Suggested columns:

```text
id
name
email
password_hash
created_at
updated_at
```

Rules:

- `id` is the primary key.
- `email` must be unique.
- `password_hash` stores a password hash, never plaintext.
- `created_at` records account creation.

## 4. Classrooms

Table:

`classrooms`

Suggested columns:

```text
id
owner_id
name
created_at
updated_at
```

Relationships:

```text
users.id
    ↓
classrooms.owner_id
```

One user can own many classrooms.

Each classroom has exactly one owner in the initial model.

## 5. Students

Table:

`students`

Suggested columns:

```text
id
student_id
full_name
program
created_at
updated_at
```

Rules:

- `id` is the internal primary key.
- `student_id` is the business identifier.
- `student_id` must be unique.
- `full_name` is required.
- `program` can be required or optional based on final requirements.

## 6. Why Student ID Is Separate from Primary Key

A database primary key should remain stable.

Student ID is a business identifier that may have institutional meaning.

Example:

```text
Internal ID:
7c9f...

Student ID:
25-09759
```

The application can display `25-09759` while relationships use the internal primary key.

## 7. Classroom Students

Table:

`classroom_students`

Suggested columns:

```text
id
classroom_id
student_id
created_at
```

This is a junction table.

It represents:

```text
Student belongs to Classroom
```

The recommended unique constraint is:

```text
UNIQUE(classroom_id, student_id)
```

## 8. Many-to-Many Model

The relationship can be represented as:

```text
Classroom
   │
   │ 1
   ▼
ClassroomStudent
   ▲
   │ 1
   │
Student
```

Conceptually:

```text
Classroom N ↔ N Student
```

The junction table makes the relationship explicit.

## 9. Attendance Sessions

Table:

`attendance_sessions`

Suggested columns:

```text
id
classroom_id
status
started_at
finalized_at
created_at
```

Possible statuses:

```text
ACTIVE
FINALIZED
```

The session belongs to one classroom.

A classroom can have many sessions.

## 10. Attendance Records

Table:

`attendance_records`

Suggested columns:

```text
id
session_id
student_id
status
marked_at
method
created_at
updated_at
```

Possible status values:

```text
PENDING
PRESENT
ABSENT
```

Possible methods:

```text
QR
MANUAL
```

For absent records, `method` can be null because no attendance input occurred.

## 11. Attendance Record Relationship

```text
AttendanceSession
        │
        │ 1
        ▼
AttendanceRecord
        ▲
        │ N
        │
     Student
```

One session has many attendance records.

A student has many attendance records across different sessions.

## 12. Unique Attendance Rule

The most important constraint is:

```text
UNIQUE(session_id, student_id)
```

This guarantees one record per student per session.

Without this constraint, duplicate scans could create multiple rows.

## 13. Foreign Keys

Recommended foreign keys:

```text
classrooms.owner_id
    → users.id

classroom_students.classroom_id
    → classrooms.id

classroom_students.student_id
    → students.id

attendance_sessions.classroom_id
    → classrooms.id

attendance_records.session_id
    → attendance_sessions.id

attendance_records.student_id
    → students.id
```

## 14. ERD

```text
┌─────────────┐
│    users    │
├─────────────┤
│ PK id       │
│    name     │
│ UK email    │
│    password │
└──────┬──────┘
       │ 1
       │
       │ N
┌──────▼──────────────┐
│     classrooms      │
├─────────────────────┤
│ PK id               │
│ FK owner_id         │
│    name             │
└──────┬──────────────┘
       │
       │ 1
       │
       ├───────────────┐
       │               │
       │ N             │ 1
┌──────▼──────────┐    │
│classroom_students│    │
├─────────────────┤    │
│ PK id           │    │
│ FK classroom_id │    │
│ FK student_id   │    │
└────────┬────────┘    │
         │ N           │
         │             │
         ▼ 1           │
┌─────────────────┐    │
│    students     │    │
├─────────────────┤    │
│ PK id           │    │
│ UK student_id   │    │
│    full_name    │    │
│    program      │    │
└────────┬────────┘    │
         │             │
         │ 1           │
         │             │
         │ N           │
┌────────▼─────────────┴──┐
│    attendance_records    │
├──────────────────────────┤
│ PK id                    │
│ FK session_id            │
│ FK student_id            │
│ status                   │
│ marked_at                │
│ method                   │
└──────────▲───────────────┘
           │ N
           │
           │ 1
┌──────────┴──────────────┐
│   attendance_sessions    │
├──────────────────────────┤
│ PK id                    │
│ FK classroom_id          │
│ status                   │
│ started_at               │
│ finalized_at             │
└──────────────────────────┘
```

## 15. Session Initialization

When a session starts, the application should create attendance records for classroom members.

Example roster:

```text
25-09759
25-09760
25-09761
```

Initial records:

```text
25-09759 PENDING
25-09760 PENDING
25-09761 PENDING
```

This gives the system a complete checklist.

## 16. Why Precreate Records

Precreating records makes absence calculation straightforward.

The system does not need to guess which students were expected.

The expected list comes directly from classroom membership at session creation.

## 17. Alternative Model

Another design would create only present records and calculate absences later.

That can reduce rows, but it makes the session checklist more complex.

For this classroom application, precreating session records is easier to understand and matches the visible PENDING state.

## 18. Finalization Query Concept

Conceptually:

```text
UPDATE attendance_records
SET status = 'ABSENT'
WHERE session_id = ?
AND status = 'PENDING'
```

Then:

```text
UPDATE attendance_sessions
SET status = 'FINALIZED'
WHERE id = ?
```

Both operations should occur in one transaction.

## 19. Attendance Status Rules

Allowed normal transitions:

```text
PENDING → PRESENT
PENDING → ABSENT
```

The second transition happens during finalization.

A finalized session should not accept new present records.

## 20. Timestamp Rules

Important timestamps:

```text
User.created_at
Classroom.created_at
Student.created_at
Session.started_at
Session.finalized_at
AttendanceRecord.marked_at
```

`marked_at` should be set when a student becomes present.

Absent records may leave `marked_at` null.

## 21. Method Rules

If:

```text
status = PRESENT
```

then method should normally be:

```text
QR
```

or:

```text
MANUAL
```

If:

```text
status = ABSENT
```

method can be null.

This represents that no attendance input was received.

## 22. Classroom Ownership

A classroom must always have an owner.

The database relationship alone is not enough.

The service layer must verify ownership before:

- Viewing
- Editing
- Adding students
- Starting sessions
- Finalizing sessions
- Exporting

## 23. Student Reuse

Student records should not be duplicated simply because a student is added to another classroom.

Example:

```text
Student 25-09759
        │
        ├── Membership: BSIT-2B
        └── Membership: another class
```

The student remains one database record.

## 24. Historical Records

Historical attendance should reference the student record.

Student information changes should be handled carefully.

For reporting, the application may eventually store a snapshot of important display fields.

That decision can be made if historical names or program information need to remain unchanged.

## 25. Deletion Rules

Avoid cascading deletion from a student directly into historical attendance without an explicit design decision.

A safer initial strategy is:

```text
Student active = false
```

rather than physically deleting a student with historical records.

## 26. Classroom Removal

If a classroom is deleted, historical attendance may also be affected.

For that reason, classroom deletion should either:

- Be disabled initially, or
- Use soft deletion

This protects attendance history.

## 27. Index Strategy

Recommended indexes:

```text
users(email)
students(student_id)
classrooms(owner_id)
classroom_students(classroom_id)
classroom_students(student_id)
attendance_sessions(classroom_id)
attendance_sessions(status)
attendance_records(session_id)
attendance_records(student_id)
```

The unique constraints should also be indexed by the database.

## 28. Search Strategy

Student search should primarily use:

```text
student_id
full_name
```

The Student ID lookup must be indexed because QR and manual attendance both depend on it.

## 29. Transaction Boundaries

Starting a session may require:

1. Validate classroom ownership.
2. Validate classroom existence.
3. Retrieve active members.
4. Create session.
5. Create pending records.

This operation should be transactional.

## 30. Finalization Transaction

Finalization should:

1. Validate ownership.
2. Lock or safely update the session.
3. Ensure it is active.
4. Convert pending to absent.
5. Set finalized timestamp.
6. Set session status.
7. Commit.

## 31. Concurrency

Two finalization requests should not produce inconsistent state.

The database transaction and session state must prevent double finalization.

Similarly, duplicate attendance requests must be protected by the unique constraint.

## 32. Data Integrity

The database should enforce what the database can enforce.

Examples:

```text
UNIQUE users.email
UNIQUE students.student_id
UNIQUE classroom_students(classroom_id, student_id)
UNIQUE attendance_records(session_id, student_id)
FOREIGN KEY relationships
NOT NULL required fields
```

Business rules remain in the service layer.

## 33. Example Data

User:

```text
id: 1
name: Teacher
email: teacher@example.com
```

Classroom:

```text
id: 10
owner_id: 1
name: BSIT-2B
```

Student:

```text
id: 100
student_id: 25-09759
full_name: Clarenze Kenshien A. Alao
program: BSIT
```

Membership:

```text
classroom_id: 10
student_id: 100
```

Session:

```text
id: 500
classroom_id: 10
status: ACTIVE
```

Attendance:

```text
session_id: 500
student_id: 100
status: PRESENT
method: QR
```

## 34. Database Source of Truth

The frontend checklist is a representation of database state.

The Excel file is a representation of finalized database state.

Neither should become the primary data store.

## 35. Final Data Flow

```text
User
 ↓
Classroom
 ↓
ClassroomStudent
 ↓
AttendanceSession
 ↓
AttendanceRecord
 ↓
Excel Report
```

This model is normalized enough for the initial project and remains understandable for development and maintenance.
