"""Wire types shared with the browser: standard library only."""
from dataclasses import dataclass, field


@dataclass
class Message:
    id: str
    conversation_id: str
    epoch: int
    sender: str
    text: str
    status: str
    created_at: float
    reply_to: str | None = None
    shared_post_id: str | None = None
    reaction: str | None = None


@dataclass
class ChatRequest:
    session_id: str
    conversation_id: str
    epoch: int
    client_message_id: str
    text: str
    reply_to: str | None = None
    shared_post_id: str | None = None
    display_name: str | None = None
    tone: str = 'balanced'
    language: str = 'ko'
    custom_persona: dict | None = None


@dataclass
class ChatEvent:
    kind: str
    conversation_id: str
    epoch: int
    request_id: str
    message_id: str
    payload: dict = field(default_factory=dict)


@dataclass
class Route:
    screen: str
    character_id: str | None = None
    post_id: str | None = None
    scroll: float = 0.0
    page: int = 0


@dataclass
class Character:
    id: str
    display_name: str
    handle: str
    avatar: str
    bio: str
    post_ids: list[str]
    note: str
    followers: int = 128
    following: int = 173
    greeting: str = '안녕, 뭐 하고 있었어?'
    translations: dict = field(default_factory=dict)


@dataclass
class Post:
    id: str
    character_id: str
    images: list[str]
    caption: str
    like_count: int
    created_at: str
    description: str = ''
    translations: dict = field(default_factory=dict)


@dataclass
class Catalog:
    characters: dict[str, Character]
    posts: dict[str, Post]
    self_avatar: str
