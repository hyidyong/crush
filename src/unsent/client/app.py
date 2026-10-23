"""Pygame mobile UI shared by the native and browser entry points."""
import asyncio,json,time,os,hashlib
from dataclasses import dataclass,asdict
from pathlib import Path
import pygame
from unsent.client.controller import Controller,UIAction,create_state
from unsent.client.input import TextEntry,InputEvent
from unsent.client.widgets import Canvas
from unsent.client.persistence import DeviceStorage
from unsent.client.transport import BrowserTransport,DesktopTransport
from unsent.shared.catalog import load_catalog
from unsent.shared import bots
from unsent.client.screens import inbox,thread,profile,posts,settings,common
from unsent.client.screens import bots as bot_screen

class OfflineTransport:
    health={'app':'ready','model':'unconfigured'}
    def __init__(self):self.pending=[]
    def start_chat(self,request):
        from unsent.shared.contracts import ChatEvent
        self.pending.append(ChatEvent('error',request.conversation_id,request.epoch,'',request.client_message_id,{'message':'AI 연결이 필요해요. 설정에서 연결 상태를 확인해 주세요.'}))
    def reset(self,*args):pass
    def drain_events(self):pending,self.pending=self.pending,[];return pending
    def close(self):pass

@dataclass
class ClientConfig:
    asset_root:Path
    backend_url:str|None=None
    token:str|None=None
    width:int=414
    height:int=896
    web:bool=False
    frames:int=0
    screenshot:Path|None=None
    initial_screen:str='inbox'
    data_dir:Path|None=None

class Runtime:
    def __init__(self,config):
        self.config=config;pygame.init();pygame.display.set_caption('Unsent')
        self.window=pygame.display.set_mode((config.width,config.height),pygame.RESIZABLE)
        self.canvas=Canvas(config.asset_root,414,896);catalog=load_catalog(Path(config.asset_root))
        self.bridge=None
        if config.web:
            import platform
            self.bridge=platform.window.unsentBridge;transport=BrowserTransport(self.bridge)
        else:
            private=config.data_dir or Path('.local')/'users'/str(getattr(os,'getuid',lambda:0)())/'default'
            transport=DesktopTransport(config.backend_url,config.token,identity_path=Path(private)/'identity.json') if config.backend_url else OfflineTransport()
        self.ui=Controller(create_state(catalog),catalog,transport);self.ui.web=config.web
        self.private=None if config.web else Path(private);self.storage=None
        if config.web:self.activate_storage(DeviceStorage(True))
        elif not config.backend_url:self.activate_storage(DeviceStorage(path=self.private/'device-offline.json'))
        self.ui.on_change=self.save;self.ui.on_import=self.import_file
        if config.initial_screen=='thread':self.ui.handle(UIAction('open_thread',{'character_id':next(iter(catalog.characters))}))
        elif config.initial_screen=='profile':self.ui.handle(UIAction('profile',{'character_id':next(iter(catalog.characters))}))
        elif config.initial_screen=='settings':self.ui.handle(UIAction('settings'))
        self.entry=TextEntry();self.input_key='';self.input_rect=None;self.running=True;self.pressed=None;self.last_tap=None;self.snapshot_previous='';self.dragged=False
        pygame.key.start_text_input()

    def activate_storage(self,storage):
        self.storage=storage;storage.restore(self.ui);self.ui.transport.session_id=self.ui.state.session_id

    def save(self):return self.storage.save(self.ui) if self.storage else False

    def target(self):
        ui=self.ui
        if self.storage is None:return ('','',2000,False)
        if ui.modal:
            return ('edit',ui.edit_value,1024 if ui.modal['kind']=='import_path' else 60,False) if ui.modal['kind'] in ('rename','edit_note','import_path') else ('','',2000,False)
        if ui.searching:return ('search',ui.query,100,False)
        if ui.state.route.screen=='bot_editor' and ui.bot_draft and ui.bot_field:
            key=ui.bot_field;return ('bot:'+key,ui.bot_draft[key],bots.FIELDS[key],key!='name')
        if ui.state.route.screen=='thread':
            cid=ui.state.route.character_id;return ('chat:'+cid,ui.state.conversations[cid].draft,2000,False)
        return ('','',2000,False)

    def input(self,event):
        key,value,limit,multiline=self.target()
        if not key:return
        if self.input_key!=key:self.entry=TextEntry(value);self.input_key=key
        if multiline and event.kind=='key' and event.key=='Enter':event.shift=True
        result=self.entry.handle(event);self.entry.text=self.entry.text[:limit]
        ui=self.ui
        if key=='edit':ui.edit_value=self.entry.text
        elif key=='search':ui.query=self.entry.text
        elif key.startswith('bot:'):ui.bot_draft[key[4:]]=self.entry.text
        else:ui.state.conversations[key[5:]].draft=self.entry.text
        if result.kind=='submit':
            if key.startswith('chat:'):ui.handle(UIAction('send',{'character_id':key[5:],'text':result.text}))
            elif key=='edit':
                ui.edit_value=result.text;ui.handle(UIAction('bot_import_path' if ui.modal['kind']=='import_path' else 'save_edit'))
            elif key=='bot:name':ui.bot_draft['name']=result.text;ui.bot_field='personality';ui.state.route.scroll=370
        self.save()

    def import_file(self,path=None):
        if self.config.web:self.bridge.pickBotFile();return
        if not path:self.ui.modal={'kind':'import_path'};self.ui.edit_value='';return
        try:
            target=Path(path).expanduser()
            with target.open('rb') as source:data=source.read(65537)
            doc=bots.read_document(target.name,data)
            self.ui.handle(UIAction('bot_import',{'name':doc['name'],'text':doc['text']}))
        except (OSError,ValueError,UnicodeError):self.ui.say('파일을 읽지 못했어요. 경로와 권한을 확인해 주세요.')

    def scroll(self,amount):
        ui=self.ui
        if ui.modal:
            if ui.modal['kind'] in ('contacts','share'):ui.modal['scroll']=min(max(0,len(ui.catalog.characters)*70-226),max(0,ui.modal.get('scroll',0)+amount))
        elif ui.state.route.screen=='thread':ui.state.conversations[ui.state.route.character_id].scroll=max(0,ui.state.conversations[ui.state.route.character_id].scroll+amount)
        else:ui.state.route.scroll=max(0,ui.state.route.scroll+amount)

    def point(self,xy):
        return xy[0]*414/self.window.get_width(),xy[1]*896/self.window.get_height()

    def click(self,pos,held=0):
        for rect,action,payload in reversed(self.canvas.hits):
            if rect.collidepoint(pos):
                if self.storage is None:
                    if action=='native_retry':self.ui.transport.close();self.__init__(self.config)
                    return
                if action=='message':
                    stamp=time.monotonic();same=self.last_tap and self.last_tap[0]==payload['message_id'] and stamp-self.last_tap[1]<.33
                    self.last_tap=(payload['message_id'],stamp)
                    if held>=.45:action='message_menu'
                    elif same:action='react'
                    else:return
                if action in ('focus_edit','noop'):return
                self.ui.handle(UIAction(action,payload));self.input_key='';self.render();return

    def events(self):
        # DOM edits precede the canvas click that changes their input target.
        if self.config.web:self.browser_events()
        for event in pygame.event.get():
            if event.type==pygame.QUIT:self.running=False
            elif event.type==pygame.WINDOWFOCUSLOST:self.ui.handle(UIAction('focus',{'focused':False}))
            elif event.type==pygame.WINDOWFOCUSGAINED:self.ui.handle(UIAction('focus',{'focused':True}))
            elif event.type==pygame.MOUSEWHEEL:self.scroll(-event.y*42)
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:self.pressed=(self.point(event.pos),time.monotonic());self.dragged=False
            elif event.type==pygame.MOUSEMOTION and self.pressed and event.buttons[0]:
                dx,dy=self.point(event.rel)
                if abs(dy)>2:self.dragged=True;self.scroll(-dy)
            elif event.type==pygame.MOUSEBUTTONUP and event.button==1 and self.pressed:
                start,at=self.pressed;end=self.point(event.pos);self.pressed=None
                if self.ui.state.route.screen=='post' and abs(end[0]-start[0])>32 and abs(end[0]-start[0])>abs(end[1]-start[1]):self.ui.handle(UIAction('page',{'delta':1 if end[0]<start[0] else -1}))
                elif not self.dragged:self.click(end,time.monotonic()-at)
            elif event.type==pygame.DROPFILE and self.ui.state.route.screen=='bot_editor':self.import_file(event.file)
            elif not self.config.web and event.type==pygame.TEXTINPUT:self.input(InputEvent('text',event.text))
            elif not self.config.web and event.type==pygame.TEXTEDITING:self.entry.composing=bool(event.text)
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:self.ui.handle(UIAction('back'))
                elif not self.config.web and event.key in (pygame.K_RETURN,pygame.K_BACKSPACE):self.input(InputEvent('key',key='Enter' if event.key==pygame.K_RETURN else 'Backspace',shift=bool(event.mod&pygame.KMOD_SHIFT)))
                elif not self.config.web and event.key==pygame.K_v and event.mod&pygame.KMOD_CTRL:
                    try:self.input(InputEvent('text',pygame.scrap.get_text()))
                    except Exception:pass

    def browser_events(self):
        try:items=json.loads(str(self.bridge.drainInput()))
        except (ValueError,TypeError):items=[]
        for value in items:
            kind=value.get('kind')
            if kind=='visibility':self.ui.handle(UIAction('focus',{'focused':value['focused']}))
            elif kind=='scroll':self.scroll(value['amount'])
            elif kind=='bot_file':self.ui.handle(UIAction('bot_import',{'name':value['name'],'text':value['text']}));self.input_key=''
            elif kind=='bot_file_error':self.ui.say('UTF-8 텍스트 파일을 골라 주세요.')
            elif kind=='private_error':self.ui.say('기기에 저장하지 못했어요.')
            else:self.input(InputEvent(kind,value.get('text',''),value.get('key',''),value.get('shift',False)))

    def snapshot(self):
        ui=self.ui;s=ui.state
        return dict(screen=s.route.screen,character_id=s.route.character_id,page=s.route.page,scroll=s.route.scroll,language=ui.language,modal=ui.modal,
            has_bot_draft=ui.bot_draft is not None,private_bots=[{'id':p['id'],'name':p['name'],'revision':p['revision']} for p in ui.bots.values()],
            conversations={cid:{'draft':c.draft,'unread':c.unread,'typing':c.typing,'error':c.error,'messages':[asdict(m) for m in c.messages]} for cid,c in s.conversations.items()})

    def render(self):
        c=self.canvas;ui=self.ui;c.start();screen=ui.state.route.screen
        if self.storage is None:
            unavailable=getattr(ui.transport,'identity_status','')=='unavailable'
            c.text(ui.t('서버에 연결할 수 없음' if unavailable else 'AI 연결 확인 중…'),20,380,15,width=374,align='center');common.statusbar(c)
            if unavailable:c.button('Retry / 다시 시도',(80,432,254,43),'native_retry',accent=True)
            pygame.transform.smoothscale(c.surface,self.window.get_size(),self.window);pygame.display.flip();return
        renderer={'inbox':inbox,'thread':thread,'profile':profile,'post':posts,'settings':settings}.get(screen,bot_screen)
        self.input_rect=renderer.render(c,ui)
        if ui.modal:self.input_rect=common.render_modal(c,ui)
        common.statusbar(c);common.notices(c,ui);common.home_indicator(c)
        pygame.transform.smoothscale(c.surface,self.window.get_size(),self.window);pygame.display.flip()
        if self.config.web:
            key,value,limit,multi=self.target();label=ui.t('검색' if key=='search' else bot_screen.LABELS.get(key[4:],'이름') if key.startswith('bot:') else '메시지')
            if key.startswith('chat:') and ui.language=='en':label='Message'
            raw=lambda v:json.dumps(v,ensure_ascii=True)
            self.bridge.setInput(raw(self.input_rect if key else None),raw(value),raw(label),414,896,raw(ui.t('메시지…') if key.startswith('chat:') else ui.t('눌러서 입력')),'multiline' if multi else 'chat',limit,key)
            file_rect=next((tuple(rect) for rect,kind,_ in c.hits if kind=='bot_import_file'),None)
            self.bridge.setBotFileButton(raw(file_rect),raw(ui.t('텍스트 파일 가져오기')),raw(ui.bot_draft['id'] if ui.bot_draft else ''))
            snapshot=raw(self.snapshot())
            if snapshot!=self.snapshot_previous:self.bridge.snapshot(snapshot);self.snapshot_previous=snapshot

    async def run(self):
        frames=0
        while self.running:
            if not self.config.web and self.config.backend_url:
                transport=self.ui.transport
                if getattr(transport,'identity_changed',False):
                    transport.close();self.__init__(self.config);continue
                if self.storage is None and transport.storage_scope and transport.identity_ready:
                    scope=hashlib.sha256((self.config.backend_url+'|'+transport.storage_scope).encode()).hexdigest()
                    self.activate_storage(DeviceStorage(path=self.private/('device-'+scope+'.json')))
            self.events();self.ui.tick(time.time());self.render();frames+=1
            if self.config.web and frames==1:self.bridge.ready()
            if self.config.frames and frames>=self.config.frames:break
            await asyncio.sleep(1/30)
        if self.config.screenshot:
            Path(self.config.screenshot).parent.mkdir(parents=True,exist_ok=True);pygame.image.save(self.window,str(self.config.screenshot))
        self.save();self.ui.transport.close();pygame.quit()

async def run(config):await Runtime(config).run()
