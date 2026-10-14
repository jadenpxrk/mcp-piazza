# Example workflows

These prompts show how an assistant uses the tools together.

## Catch up after some days away

> What happened on Piazza since Friday? Give me the instructor announcements first.

1. `recent_activity(since="2026-10-09")` finds the posts with activity in each active course.
2. `get_posts` reads every post in the result, 20 posts in each call.
3. The assistant puts instructor notes, instructor answers, and posts with many likes or stars first.

The `catch_up` prompt does these steps for you.

## Before you ask a question

> I get a segfault in HW3 part 2 when the list is empty. Did someone already ask about this in CSE 12?

1. `search_posts(query="hw3 segfault empty", course="CSE 12")` finds possible duplicates.
2. `get_post` reads the best match, including the instructor answer and followups.

The `before_asking` prompt does these steps for you.

## Find open questions

> Which HW3 questions in CSE 12 have no answer yet?

1. `list_posts(course="CSE 12", filter="unresolved", folder="hw3")` lists unanswered questions and unresolved followups.

## Exam preparation

> Collect everything the instructors said about the midterm.

1. `list_instructor_notes(course="CSE 12")` lists the instructor posts.
2. `search_posts` finds posts about the midterm, with related words such as "room" and "formula sheet".
3. `get_posts` reads every match. The assistant marks facts that only students stated as unconfirmed.

The `exam_prep` prompt does these steps for you.

## Office hours and staff

> When are the TA office hours for CSE 12, and what is the head TA's email?

1. `get_course_info(course="CSE 12")` returns the office hours and the staff list with emails.

## What changed in an announcement

> The instructor edited @88. What changed?

1. `get_post_history(course="CSE 12", number=88)` shows each version with a diff.

## A screenshot in a post

> Look at the error screenshot in @131 and tell me what is wrong.

1. `get_post` reads the thread. The screenshot shows as `[image: https://piazza.com/...]`.
2. `get_attachment(url=...)` returns the image, and the model reads it.
