"""Convert Piazza post HTML to compact markdown-style text."""

import html
import re
from html.parser import HTMLParser

_BLOCK = {"p", "div", "section", "article", "header", "footer", "table", "ul", "ol", "blockquote", "hr"}
_SKIP = {"script", "style", "head"}


def abs_url(url: str) -> str:
    return "https://piazza.com" + url if url.startswith("/") else url


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.pre = 0
        self.skip = 0
        self.lists: list[list[int]] = []  # one entry per open list: [next number] for <ol>, [] for <ul>
        self.quotes: list[int] = []  # start index in out of each open blockquote
        self.link: str | None = None
        self.link_text: list[str] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.rows_in_table = 0

    def _emit(self, s: str) -> None:
        if self.cell is not None:
            self.cell.append(s)
        elif self.link is not None:
            self.link_text.append(s)
        else:
            self.out.append(s)

    def _newline(self, blank: bool = False) -> None:
        self.out.append("\n\n" if blank else "\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag in _SKIP:
            self.skip += 1
        elif tag == "br":
            self._emit("\n") if self.pre or self.cell is not None else self._newline()
        elif tag == "pre":
            self.pre += 1
            self._newline(blank=True)
            self.out.append("```\n")
        elif tag == "code" and not self.pre:
            self._emit("`")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline(blank=True)
            self.out.append("#" * int(tag[1]) + " ")
        elif tag in ("ul", "ol"):
            self.lists.append([1] if tag == "ol" else [])
        elif tag == "li":
            depth = max(len(self.lists) - 1, 0)
            marker = "- "
            if self.lists and self.lists[-1]:
                marker = f"{self.lists[-1][0]}. "
                self.lists[-1][0] += 1
            self._newline()
            self.out.append("  " * depth + marker)
        elif tag == "blockquote":
            self._newline(blank=True)
            self.quotes.append(len(self.out))
        elif tag == "a":
            self.link, self.link_text = a.get("href", ""), []
        elif tag == "img":
            self._emit(f"[image: {abs_url(a.get('src', ''))}]")
        elif tag == "table":
            self.rows_in_table = 0
            self._newline(blank=True)
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag in _BLOCK:
            self._newline(blank=True)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skip = max(self.skip - 1, 0)
        elif tag == "pre" and self.pre:
            self.pre -= 1
            if not "".join(self.out).endswith("\n"):
                self.out.append("\n")
            self.out.append("```")
            self._newline(blank=True)
        elif tag == "code" and not self.pre:
            self._emit("`")
        elif tag in ("ul", "ol") and self.lists:
            self.lists.pop()
            if not self.lists:
                self._newline(blank=True)
        elif tag == "blockquote" and self.quotes:
            start = self.quotes.pop()
            body = re.sub(r"\n{3,}", "\n\n", "".join(self.out[start:]).strip())
            self.out[start:] = ["\n".join(("> " + line).rstrip() for line in body.split("\n"))]
            self._newline(blank=True)
        elif tag == "a" and self.link is not None:
            text, href = "".join(self.link_text).strip(), abs_url(self.link)
            self.link = None
            self._emit(text if text == href or not href else f"{text} ({href})" if text else href)
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()).replace("|", "\\|"))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.out.append("| " + " | ".join(self.row) + " |\n")
            if self.rows_in_table == 0:
                self.out.append("|" + "---|" * len(self.row) + "\n")
            self.rows_in_table += 1
            self.row = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") or tag in _BLOCK:
            self._newline(blank=True)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.pre:
            self.out.append(data)
        else:
            self._emit(re.sub(r"\s+", " ", data))


def to_text(s: str | None, editor: str | None = None) -> str:
    """Convert Piazza HTML to text. Content from the markdown editor ('md' or 'me') stays as markdown."""
    if not s:
        return ""
    if editor in ("md", "me"):
        return html.unescape(s).strip()
    conv = _Converter()
    conv.feed(s)
    conv.close()
    text = "".join(conv.out)
    text = re.sub(r"[ \t]+\n", "\n", text)  # trailing spaces
    return re.sub(r"\n{3,}", "\n\n", text).strip()
