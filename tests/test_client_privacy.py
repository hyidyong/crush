import copy
from pathlib import Path
from unsent.client.controller import Controller,UIAction,create_state
from unsent.client.persistence import DeviceStorage
from unsent.shared.catalog import load_catalog

class Transport:
    def __init__(self):self.requests=[];self.resets=[]
    def start_chat(self,request):self.requests.append(request)
    def reset(self,*args):self.resets.append(args)
    def drain_events(self):return []

def controller():
    catalog=load_catalog(Path('assets'));return Controller(create_state(catalog),catalog,Transport())

def draft(ui):
    ui.handle(UIAction('new_bot'));ui.bot_draft['name']='Private demo'

def test_imported_source_never_becomes_active_prompt_implicitly():
    ui=controller();draft(ui);raw='PRIVATE-SOURCE-MARKER at the beginning of a short document'
    ui.handle(UIAction('bot_import',{'name':'private-source.txt','text':raw}))
    assert ui.bot_draft['documents'][0]['text']==raw
    assert ui.bot_draft['personality']==''
    ui.handle(UIAction('save_bot'));assert not ui.bots
    ui.bot_draft['personality']='Gentle, thoughtful and concise.'
    ui.handle(UIAction('save_bot'));cid=next(iter(ui.bots))
    ui.handle(UIAction('open_thread',{'character_id':cid}));ui.handle(UIAction('send',{'text':'Hello'}))
    card=ui.transport.requests[-1].custom_persona
    assert set(card)=={'name','bio','personality','examples'}
    assert raw not in repr(card) and 'private-source.txt' not in repr(card)

def test_bom_import_uses_browser_supported_utf8_codec():
    from unsent.shared.bots import read_document
    assert read_document('style.md',b'\xef\xbb\xbf'+ '차분한 말투'.encode())['text']=='차분한 말투'

def test_save_failure_retains_draft_and_delete_failure_restores_bot():
    ui=controller();draft(ui);ui.bot_draft['personality']='Gentle and concise.';original=copy.deepcopy(ui.bot_draft)
    ui.on_change=lambda:False;ui.handle(UIAction('save_bot'))
    assert ui.bot_draft==original and not ui.bots
    ui.on_change=lambda:True;ui.handle(UIAction('save_bot'));cid=next(iter(ui.bots));saved=copy.deepcopy(ui.bots[cid])
    ui.on_change=lambda:False;ui.handle(UIAction('delete_bot',{'character_id':cid}))
    assert ui.bots[cid]==saved and cid in ui.catalog.characters and not ui.transport.resets

def test_bot_profiles_persist_without_chat_history_and_language_does_not_change_source(tmp_path):
    ui=controller();draft(ui);ui.bot_draft['personality']='짧고 다정하게 말한다.';ui.handle(UIAction('save_bot'));cid=next(iter(ui.bots))
    ui.set_language('en');storage=DeviceStorage(path=tmp_path/'device.json');assert storage.save(ui)
    other=controller();storage.restore(other)
    assert other.language=='en' and other.bots[cid]['personality']=='짧고 다정하게 말한다.'
    assert not other.save_history
    other.handle(UIAction('open_thread',{'character_id':cid}));other.handle(UIAction('send',{'text':'Hello'}))
    assert other.transport.requests[-1].language=='en'
    assert (tmp_path/'device.json').stat().st_mode&0o777==0o600
