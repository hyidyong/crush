import json,os
from dataclasses import asdict
from pathlib import Path
from unsent.shared.contracts import Message

def mapping(value):return value if isinstance(value,dict) else {}
class DeviceStorage:
    def __init__(self,web=False,path=None):self.web=web;self.path=Path(path) if path else None;self.previous=''
    def read(self):
        try:
            if self.web:
                import platform
                raw=str(platform.window.unsentBridge.load())
            else:raw=self.path.read_text() if self.path and self.path.exists() else ''
            return mapping(json.loads(raw)) if raw else {}
        except (ValueError,OSError,TypeError):return {}
    def restore(self,ui):
        data=self.read()
        from unsent.client.bot_builder import restore_private
        restore_private(ui,data);ui.set_language(data.get('language','ko'))
        ui.state.aliases={cid:str(name)[:32] for cid,name in mapping(data.get('aliases')).items() if cid in ui.catalog.characters}
        ui.tones={cid:tone for cid,tone in mapping(data.get('tones')).items() if cid in ui.catalog.characters and tone in ('balanced','warm','playful','dry')}
        ui.sound=bool(data.get('sound',False));ui.save_history=bool(data.get('save_history',False))
        if not ui.save_history:return
        if isinstance(data.get('session_id'),str) and len(data['session_id'])==32:ui.state.session_id=data['session_id'];ui.transport.session_id=ui.state.session_id
        for cid,saved in mapping(data.get('conversations')).items():
            if cid not in ui.state.conversations or not isinstance(saved,dict):continue
            conv=ui.state.conversations[cid]
            try:
                messages=[Message(**m) for m in saved.get('messages',[])[-200:]]
                if any(m.conversation_id!=cid or m.shared_post_id and m.shared_post_id not in ui.catalog.posts for m in messages):continue
                conv.messages=messages;unfinished=set(saved.get('inflight',[]))
                if 'inflight' not in saved:
                    last_agent=max((i for i,m in enumerate(messages) if m.sender=='agent'),default=-1)
                    unfinished.update(m.id for m in messages[last_agent+1:] if m.sender=='user' and m.status in ('pending','sent','seen'))
                for m in messages:
                    if m.status=='pending' or m.id in unfinished:m.status='failed'
                conv.epoch=max(0,int(saved.get('epoch',0)));conv.draft=str(saved.get('draft',''))[:2000];conv.unread=max(0,int(saved.get('unread',0)))
                from unsent.client.controller import UIAction
                for m in messages:
                    if m.id in unfinished:ui.handle(UIAction('retry',{'character_id':cid,'message_id':m.id}))
            except (TypeError,ValueError,KeyError):continue
    def save(self,ui):
        data={'language':ui.language,'aliases':ui.state.aliases,'tones':ui.tones,'sound':ui.sound,'save_history':ui.save_history,'bots':ui.bots,'bot_draft':ui.bot_draft}
        if ui.save_history:data.update(session_id=ui.state.session_id,conversations={cid:{'messages':[asdict(m) for m in conv.messages[-200:]],'epoch':conv.epoch,'draft':conv.draft,'unread':conv.unread,'inflight':sorted(conv.inflight)} for cid,conv in ui.state.conversations.items()})
        raw=json.dumps(data,ensure_ascii=True,allow_nan=False)
        if raw==self.previous:return True
        try:
            if self.web:
                import platform
                if str(platform.window.unsentBridge.store(raw))!='1':raise OSError('Private storage unavailable')
            elif self.path:
                self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);self.path.parent.chmod(0o700);temporary=self.path.with_suffix('.tmp')
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(fd,'w') as target:os.fchmod(target.fileno(),0o600);target.write(raw)
                temporary.replace(self.path)
            self.previous=raw;return True
        except OSError:ui.say('기기에 저장하지 못했어요.');return False
