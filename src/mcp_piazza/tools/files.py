from urllib.parse import urlsplit

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.utilities.types import File, Image

from ..client import PiazzaClient
from ..safety import fence
from ..text import abs_url
from . import FULL_CONTENT, READ_ONLY

MAX_BYTES = 10_000_000
MAX_IMAGE_BYTES = 5_000_000  # many clients reject larger images
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpeg", "image/gif": "gif", "image/webp": "webp"}
TEXT_TYPES = {"application/json", "application/xml", "application/javascript", "application/x-python"}


def check_url(url: str) -> str:
    """Allow only https URLs on piazza.com, so the session cookies never go to another site."""
    full = abs_url(url.strip())
    parts = urlsplit(full)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "piazza.com" or host.endswith(".piazza.com")):
        raise ToolError("get_attachment only reads https links on piazza.com, as shown in [image: ...] or post links.")
    return full


def register(mcp: FastMCP, client: PiazzaClient) -> None:
    @mcp.tool(annotations=READ_ONLY, meta=FULL_CONTENT, output_schema=None)
    def get_attachment(url: str) -> Image | File | str:
        """Open a file or image that a post links to, such as an [image: ...] link or a piazza.com upload link.

        Images come back as images that the model can see. Text files come back as text.
        Other files, such as PDFs, come back as an embedded file if the client supports it. The maximum size is 10 MB.
        """
        data, mime = client.download(check_url(url), MAX_BYTES)
        if mime in IMAGE_TYPES:
            if len(data) > MAX_IMAGE_BYTES:
                raise ToolError(f"The image is larger than {MAX_IMAGE_BYTES // 1_000_000} MB.")
            return Image(data=data, format=IMAGE_TYPES[mime])
        if mime.startswith("text/") or mime in TEXT_TYPES:
            text = data.decode("utf-8", errors="replace")
            return fence(text) if client.settings.fence_content else text
        name = urlsplit(url).path.rsplit("/", 1)[-1] or "attachment"
        return File(data=data, format=mime.split("/")[-1], name=name)
