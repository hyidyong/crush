"""Conversation state independent of rendering and network transports."""
import time
import uuid
from dataclasses import dataclass, field
from unsent.shared.contracts import ChatEvent, ChatRequest, Message, Route


@dataclass
class Conversation:
    character_id: str
    epoch: int = 0
    messages: list[Message] = field(default_factory=list)
    draft: str = ''
    unread: int = 0
    scroll: float = 0.0
    typing: bool = False
    error: str = ''
    reply_to: str | None = None
    inflight: set[str] = field(default_factory=set)


@dataclass
class AppState:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    active_conversation_id: str | None = None
    routes: list[Route] = field(default_factory=lambda: [Route('inbox')])
    focused: bool = True
    screen_visible: bool = True
    aliases: dict[str, str] = field(default_factory=dict)
    notifications: list[dict] = field(default_factory=list)

    @property
    def route(self):
        return self.routes[-1]


def is_thread_visible(state, conversation_id):
    return (state.focused and state.screen_visible and state.route.screen == 'thread'
            and state.active_conversation_id == conversation_id)


def open_thread(state, conversation_id, visible=True):
    if conversation_id not in state.conversations:
        raise KeyError(conversation_id)
    state.active_conversation_id = conversation_id
    state.screen_visible = visible
    if state.route.screen != 'thread' or state.route.character_id != conversation_id:
        state.routes.append(Route('thread', conversation_id))
    if is_thread_visible(state, conversation_id):
        state.conversations[conversation_id].unread = 0


def queue_message(state, conversation_id, text):
    text = text.strip()
    if not text:
        return None
    if len(text) > 2000:
        raise ValueError('메시지는 2,000자까지 보낼 수 있어요.')
    conversation = state.conversations[conversation_id]
    message = Message(uuid.uuid4().hex, conversation_id, conversation.epoch,
                      'user', text, 'pending', time.time(), conversation.reply_to)
    conversation.messages.append(message)
    conversation.inflight.add(message.id)
    conversation.draft = ''
    conversation.error = ''
    conversation.reply_to = None
    return ChatRequest(state.session_id, conversation_id, conversation.epoch,
                       message.id, text, reply_to=message.reply_to,
                       display_name=state.aliases.get(conversation_id))


def apply_event(state, event):
    conversation = state.conversations.get(event.conversation_id)
    if conversation is None or event.epoch != conversation.epoch:
        return
    message = next((m for m in conversation.messages if m.id == event.message_id), None)
    if event.kind in ('accepted', 'seen'):
        if message is not None and message.sender == 'user':
            if event.kind == 'seen' or message.status != 'seen':
                message.status = 'seen' if event.kind == 'seen' else 'sent'
    elif event.kind == 'typing':
        conversation.typing = bool(event.payload.get('active', False))
    elif event.kind == 'bubble':
        if message is not None:
            return
        text = event.payload.get('text', '')
        if not isinstance(text, str) or not text:
            return
        conversation.messages.append(Message(event.message_id, event.conversation_id,
            event.epoch, 'agent', text, 'received', time.time()))
        conversation.error = ''
        if not is_thread_visible(state, event.conversation_id):
            conversation.unread += 1
            state.notifications.append({'conversation_id':event.conversation_id, 'text':text, 'at':time.time()})
            state.notifications[:] = state.notifications[-20:]
    elif event.kind == 'done':
        conversation.typing = False
        conversation.inflight.discard(event.message_id)
    elif event.kind == 'error':
        conversation.typing = False
        conversation.inflight.discard(event.message_id)
        conversation.error = str(event.payload.get('message', '답장을 불러오지 못했어요.'))
        if message is not None and message.sender == 'user':
            message.status = 'failed'


def reset_thread(state, conversation_id):
    conversation = state.conversations[conversation_id]
    conversation.epoch += 1
    conversation.messages.clear()
    conversation.inflight.clear()
    conversation.draft = ''
    conversation.unread = 0
    conversation.scroll = 0.0
    conversation.typing = False
    conversation.error = ''
    conversation.reply_to = None
    state.notifications[:] = [n for n in state.notifications if n['conversation_id'] != conversation_id]
    return conversation.epoch
