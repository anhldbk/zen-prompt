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


class Profile(BaseModel):
    tag: Optional[List[str]] = None
    author: Optional[List[str]] = None
    min_likes: int = 0
    quote_max_words: Optional[int] = None
    quote_max_chars: Optional[int] = None
    quote_width: int = 80
    photo: str = "topic@minimalist"
    no_photo: bool = False
    photo_layout: str = "table"
    image_max_height: int = 10
    image_max_width: Optional[int] = None
    verbose: bool = False


class ProfileConfig(BaseModel):
    profiles: dict[str, Profile] = {}
    default_profile: Optional[str] = None
