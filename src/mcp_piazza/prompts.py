"""MCP prompts. Many clients show them as slash commands."""

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt
    def catch_up(since: str = "7d") -> str:
        """Summarize what happened on Piazza since a time, across all active courses."""
        return (
            f"Call recent_activity with since={since!r}. "
            "Read every post in the result with get_posts, 20 posts in each call. Do not skip a post because of its "
            "title or snippet: a simple student question can have an instructor answer with new information. "
            "Write a short summary for each course with the post number and link for each item. "
            "Put items first when they are pinned, instructor notes, instructor answers, instructor-endorsed, "
            "or have many likes or stars. "
            "End with a list of actions for me, such as deadlines and changes to assignments."
        )

    @mcp.prompt
    def before_asking(course: str, question: str) -> str:
        """Check whether a question was already asked and answered in a course."""
        return (
            f"I want to ask this question in {course}: {question!r}. "
            "Use search_posts with two or three different keyword sets. Read the best matches with get_posts. "
            "If an answer exists, quote it with the post link. If no answer exists, say so and suggest a clear title "
            "and folder for a new post."
        )

    @mcp.prompt
    def exam_prep(course: str, topic: str = "exam") -> str:
        """Collect what instructors and students said about an exam or topic."""
        return (
            f"In {course}, call list_instructor_notes, and read every instructor post with get_posts. "
            f"Call search_posts with {topic!r} and with related words, such as midterm, final, quiz, test, room, "
            "coverage, and formula sheet. Also call list_posts with a matching folder if one exists. "
            "Read every match with get_posts. Do not skip a post because of its title. "
            "Collect the logistics (date, time, room, allowed materials), the covered topics, and clarifications. "
            "Put facts from instructors or instructor-endorsed answers first. Mark facts that only students "
            "stated as unconfirmed. Give the post link for each fact."
        )
