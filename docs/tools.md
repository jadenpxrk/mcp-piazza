# Tool reference

All tools are read-only. Tools that take `course` accept one of these values:

- A course ID, for example `abc123xyz` from `https://piazza.com/class/abc123xyz`.
- A course number, for example `CSE 12` or `cse12`.
- Part of the course name, for example `micro` for "Microeconomics".

If the value matches the same course in more than one term, the tool uses the active term.
If the value still matches more than one course, the tool returns an error that lists the matching IDs.

All tools except `get_attachment` and `get_course_stats` publish a typed MCP output schema.
The server leaves out empty fields.

## Post summaries

`list_posts`, `search_posts`, `recent_activity`, and `list_instructor_notes` return post summaries.

| Field | Meaning |
|---|---|
| `number` | The post number. Piazza shows it as `@123`. |
| `subject` | The post title. |
| `snippet` | The start of the post text. |
| `type` | `question`, `note`, or `poll`. |
| `folders` | The folders of the post. |
| `updated` | The time of the last activity, in ISO 8601 format. |
| `pinned` | `true` if the post is pinned. |
| `unread` | `true` if the post has content that you did not read. |
| `instructor_note` | `true` if an instructor wrote the post. |
| `has_instructor_answer`, `has_student_answer` | `true` if the question has that answer, when Piazza sends this data. |
| `unanswered` | `true` if the question has no answer. |
| `unresolved_followups` | The number of unresolved followups. |
| `instructor_endorsed` | `true` if an instructor endorsed the post or marked it as a good question. |
| `likes` | The number of "good question" or "good note" votes. |
| `stars` | The number of users who starred the post. |
| `starred` | `true` if you starred the post. |
| `views` | The number of unique views. |
| `url` | The link to the post on Piazza. |

## Courses

### list_courses

| Parameter | Default | Meaning |
|---|---|---|
| `refresh` | `false` | Load the course list from Piazza again, and clear the cache. |

Returns `id`, `number`, `name`, `term`, `role` (`student` or `instructor`), `active`, and `folders` for each course.

### get_course_info

| Parameter | Meaning |
|---|---|
| `course` | The course. |

Returns the data from the course page:

| Field | Meaning |
|---|---|
| `number`, `name`, `term`, `school`, `department` | Course identity. |
| `start_date`, `end_date`, `active` | Course dates and status. |
| `students` | The number of enrolled users. |
| `description`, `syllabus`, `office_hours`, `general_information` | Course page text, as plain text. |
| `folders` | The post folders. |
| `resource_sections` | The names of the sections on the Resources tab. |
| `staff` | Instructors and TAs, with `name`, `role`, and `email`. |
| `url` | The link to the course. |

### get_unread_counts

| Parameter | Default | Meaning |
|---|---|---|
| `include_inactive` | `false` | Also count courses from past terms. |

Returns `total` and one row for each course with unread posts.
The tool sends one request for each course.

### get_course_stats

| Parameter | Meaning |
|---|---|
| `course` | The course. |

Returns the data from the Statistics page without changes.
Some instructors hide this page from students. For those courses, the tool returns an error.

## Finding posts

### recent_activity

| Parameter | Default | Meaning |
|---|---|---|
| `since` | `7d` | A relative age (`24h`, `7d`, `2w`) or an ISO date or time (`2026-10-01`). A value without a time zone uses local time. |
| `course` | all active courses | Limit the result to one course. |
| `limit` | `50` | The maximum number of posts for each course. The maximum value is 200. |
| `include_inactive` | `false` | Also read courses from past terms. |

The tool reads the feed in pages of 100 posts, newest first.
It stops at the first post that is older than `since` and is not pinned.
It reads a maximum of 1000 posts for each course, and it leaves out courses with no new activity.

### list_posts

| Parameter | Default | Meaning |
|---|---|---|
| `course` | required | The course. |
| `filter` | `all` | `all`, `unread`, `following`, `unresolved`, `unanswered`, `mine`, or `starred`. |
| `folder` | none | Show only posts in this folder. |
| `limit` | `20` | The number of posts. The maximum value is 200. |
| `offset` | `0` | The number of posts to skip, for paging. |

The result has `has_more`. When it is `true`, call the tool again with a larger `offset`.
`unresolved` includes unanswered questions and posts with unresolved followups.
`mine` includes only your posts that show your name. Piazza does not include your anonymous posts.
Piazza has no server filter for `unresolved` and `starred`, so the tool reads the full course feed in one request.

### search_posts

| Parameter | Default | Meaning |
|---|---|---|
| `query` | required | Keywords, as in the Piazza search box. |
| `course` | all active courses | Limit the search to one course. |
| `limit` | `20` | The number of results for each course. The maximum value is 200. |

Returns the results grouped by course. Courses with no results are left out.

### list_instructor_notes

| Parameter | Default | Meaning |
|---|---|---|
| `course` | required | The course. |
| `limit` | `20` | The number of posts. The maximum value is 200. |

Returns the notes and polls that instructors wrote. The tool uses the Piazza `instructors` filter.

## Reading posts

### get_post

| Parameter | Meaning |
|---|---|
| `course` | The course. |
| `number` | The post number. |

Returns the full thread:

| Field | Meaning |
|---|---|
| `subject`, `content` | The post title and text. |
| `author` | `Name (role)`, `Anonymous`, `you`, or a pseudonym. |
| `created`, `updated`, `edits` | The creation time, the time of the last edit, and the number of edits. |
| `folders`, `tags`, `status`, `views` | Post metadata. |
| `endorsed_by` | The people who endorsed the post. |
| `instructor_answer`, `student_answer` | `author`, `updated`, `content`, `endorsed_by`, and `edits`. |
| `discussion` | Followups. Each followup has `author`, `created`, `content`, `resolved`, and `replies`. |
| `poll` | For a poll, the poll data as Piazza sends it. |

The server converts HTML to markdown-style text:

| HTML | Text |
|---|---|
| Link | `text (url)` |
| Image | `[image: url]`. Use `get_attachment` to see the image. |
| Code block | A fenced block between ```` ``` ```` lines |
| Inline code | `` `code` `` |
| Heading | `## Heading` |
| List | `- item` or `1. item`, with nested lists indented |
| Table | A markdown table |
| Quote | `> text` |

LaTeX such as `$$x^2$$` stays as it is. Text from the Piazza markdown editor stays as markdown.

### get_posts

| Parameter | Meaning |
|---|---|
| `course` | The course. |
| `numbers` | Up to 20 post numbers. The tool removes duplicates. |

Returns `{"posts": [...]}` with one thread for each number, in the same format as `get_post`.
If the tool cannot read a post, that entry has `number` and `error`, and the tool still returns the other posts.

### get_post_history

| Parameter | Default | Meaning |
|---|---|---|
| `course` | required | The course. |
| `number` | required | The post number. |
| `diff` | `true` | Show each later version as a diff. |

Returns `versions`, oldest first. Each version has `version`, `author`, `created`, and `subject`.
With `diff=true`, version 1 has `content` and each later version has `diff`, a unified diff from the version before it.
With `diff=false`, each version has `content`.

### get_attachment

| Parameter | Meaning |
|---|---|
| `url` | A link from a post, such as the URL in `[image: ...]`. |

The tool reads only `https` links on `piazza.com` and its subdomains. It reads a maximum of 10 MB.

| File type | Result |
|---|---|
| PNG, JPEG, GIF, WebP (maximum 5 MB) | An image that the model can see |
| Text, JSON, XML | Text, in an untrusted-text fence |
| Other types, such as PDF | An embedded file. Some clients cannot show embedded files. |

## Prompts

| Prompt | Arguments | Result |
|---|---|---|
| `catch_up` | `since` (default `7d`) | Read all recent posts in all active courses. Summarize them with actions for you. |
| `before_asking` | `course`, `question` | Search for the question and quote an existing answer. |
| `exam_prep` | `course`, `topic` (default `exam`) | Read all instructor posts and all matching posts. Collect logistics, topics, and clarifications with links. |

## Resources

| URI | Content |
|---|---|
| `piazza://courses` | The same data as `list_courses`. |
| `piazza://courses/{course_id}/posts/{number}` | The same data as `get_post`. |
