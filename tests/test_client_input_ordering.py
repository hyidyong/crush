"""A queued browser edit must be applied before a canvas field change."""
import json
from types import SimpleNamespace
import pygame
from unsent.client.app import Runtime
from unsent.client.input import TextEntry
from unsent.client.controller import UIAction
from test_client_privacy import controller

def test_browser_edit_is_committed_before_switching_fields(monkeypatch):
    runtime=Runtime.__new__(Runtime);runtime.ui=controller();runtime.ui.handle(UIAction('new_bot'))
    runtime.config=SimpleNamespace(web=True);runtime.input_key='';runtime.entry=TextEntry()
    runtime.storage=SimpleNamespace(save=lambda ui:True);runtime.running=True;runtime.pressed=None;runtime.dragged=False
    runtime.window=SimpleNamespace(get_width=lambda:414,get_height=lambda:896)
    runtime.bridge=SimpleNamespace(drainInput=lambda:json.dumps([{'kind':'replace','text':'My private demo'}]))
    runtime.click=lambda pos,held:runtime.ui.handle(UIAction('bot_field',{'field':'personality'}))
    monkeypatch.setattr(pygame.event,'get',lambda:[pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(100,520)),pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=(100,520))])
    runtime.events()
    assert runtime.ui.bot_draft['name']=='My private demo'
    assert runtime.ui.bot_draft['personality']==''
    assert runtime.ui.bot_field=='personality'
