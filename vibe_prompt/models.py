from typing import List, Optional
from pydantic import BaseModel, computed_field
import hashlib


class Quote(BaseModel):
    text: str
    author: str
    book_title: Optional[str] = None
    tags: List[str] = []
    likes: int = 0
    link: Optional[str] = None

    @computed_field
    @property
    def hash_id(self) -> str:
        # Create a unique hash for the quote based on text and author
        data = f"{self.text}|{self.author}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()


class CrawlState(BaseModel):
    tag_url: str
    last_page_processed: int
