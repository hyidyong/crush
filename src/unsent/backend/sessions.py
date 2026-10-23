import asyncio
import time
from dataclasses import dataclass,field
from unsent.shared.contracts import ChatEvent,ChatRequest

@dataclass
class RequestRecord:
    request:ChatRequest
    request_id:str
    events:list[ChatEvent]=field(default_factory=list)
    changed:asyncio.Event=field(default_factory=asyncio.Event)
    finished:bool=False
    failed:bool=False
    task:asyncio.Task|None=None

@dataclass
class ConversationSession:
    epoch:int=0
    history:list[dict]=field(default_factory=list)
    records:dict[str,RequestRecord]=field(default_factory=dict)
    lock:asyncio.Lock=field(default_factory=asyncio.Lock)

@dataclass
class Session:
    conversations:dict[str,ConversationSession]=field(default_factory=dict)
    last_seen:float=field(default_factory=time.monotonic)

class SessionStore:
    def __init__(self):self.sessions={}
    def get(self,session_id):
        session=self.sessions.setdefault(session_id,Session());session.last_seen=time.monotonic();return session
    def expire(self,now=None):
        now=time.monotonic() if now is None else now
        for key,session in list(self.sessions.items()):
            if now-session.last_seen>=1800:self.drop(key)
    def drop(self,key):
        session=self.sessions.pop(key,None)
        if session:
            for conv in session.conversations.values():
                for record in conv.records.values():
                    if record.task and not record.task.done():record.task.cancel()
                conv.history.clear()
    def close(self):
        for key in list(self.sessions):self.drop(key)
