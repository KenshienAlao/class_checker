# Development Rules

## 1. One Task at a Time

* Work on only one clearly defined task at a time.
* Do not combine multiple independent tasks into one implementation.
* Break large features into smaller, manageable tasks.
* Complete the current task before starting another.

## 2. Inspect Before Making Changes

* Inspect the relevant files, existing code, project structure, and configuration before editing.
* Understand the existing implementation and follow the project's established conventions.
* Preserve existing functionality and working code unless the current task requires changes.
* Avoid unnecessary refactoring, dependencies, or unrelated modifications.

## 3. Implement and Verify

* Implement only what is required for the current task.
* Follow the project's architecture, coding standards, and documented requirements.
* Run relevant tests, linting, type checks, builds, or other appropriate verification.
* Fix issues introduced by the current task before reporting completion.
* Do not claim that something works unless it has been verified.
* If verification cannot be completed, clearly explain why.

## 4. Report After Every Task

After completing the task, provide a concise report containing:

* **Task:** What was assigned.
* **Changes:** What was implemented.
* **Files changed:** Which files were added, modified, or removed.
* **Verification:** Commands executed and their actual results.
* **Issues:** Remaining errors, limitations, or concerns.
* **Next task:** A brief description of the proposed next step.

Be honest about incomplete work and failed checks. Never report success without evidence.

## 5. Stop and Wait for Approval

* After reporting, stop working immediately.
* Do not start the next task until the user explicitly approves it.
* Do not automatically continue to the next task, even if it is already listed in a plan or appears straightforward.
* Treat approval for one task as permission for that task only, not for the entire project or phase.
* If the user requests changes to the current task, address those changes and report again before proceeding.

## 6. Handle Unexpected Issues

* If a blocker prevents completion, explain the problem and report what has been completed.
* If an unexpected issue requires changes outside the current task, explain the impact and ask for approval before making unrelated changes.
* Ask questions when essential requirements are unclear. Do not invent requirements or make consequential assumptions without confirmation.

## 7. Follow the Project Plan

* Use the approved plan, specifications, and existing documentation as the source of truth.
* Maintain a clear distinction between completed, in-progress, and pending tasks.
* Update relevant documentation when required by the current task.
* Do not skip tasks or change the approved implementation order without permission.

## 8. Definition of Done

A task is complete only when:

1. The requested implementation is finished.
2. Relevant verification has been performed, or its limitations have been reported.
3. Existing functionality has been preserved as far as reasonably possible.
4. The task report has been provided.
5. Work has stopped pending the user's approval.

**Core rule: Implement one task, verify it, report the results, and stop. Wait for explicit approval before starting the next task.**
