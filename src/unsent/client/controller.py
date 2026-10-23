import time
from copy import deepcopy
from dataclasses import dataclass,field
from unsent.domain.state import AppState,Conversation,apply_event,open_thread,queue_message,reset_thread
from unsent.shared.contracts import ChatRequest,Message,Route
from unsent.domain.actions import rename_character,share_post,navigate_back,carousel_page
from unsent.shared.i18n import translate
from unsent.shared import bots
from unsent.client import bot_builder

@dataclass
class UIAction:
    kind:str
    payload:dict=field(default_factory=dict)

def create_state(catalog):
    state=AppState(conversations={cid:Conversation(cid) for cid in catalog.characters})
    for index,char in enumerate(catalog.characters.values()):
        conv=state.conversations[char.id]
        conv.messages.append(Message('greeting-'+char.id,char.id,0,'agent',char.greeting,'received',time.time()-(index+1)*840))
        conv.unread=1 if index<2 else 0
    return state

class Controller:
    def __init__(self,state,catalog,transport):
        self.state,self.catalog,self.transport=state,catalog,transport;self.original_catalog=deepcopy(catalog)
        self.language='ko';self.query='';self.searching=False;self.modal=None;self.edit_value='';self.toast='';self.toast_until=0
        self.tones={};self.notes={'self':'잠깐 쉬어가기',**{cid:c.note for cid,c in catalog.characters.items()}}
        self.following=set(catalog.characters);self.liked_posts=set();self.saved_posts=set();self.reposted=set();self.requests=set()
        self.sound=False;self.save_history=False;self.on_change=None
        self.bots={};self.bot_draft=None;self.bot_field=None;self.on_import=None
    def t(self,text,**values):return translate(text,self.language,**values)
    def name(self,cid):return self.state.aliases.get(cid,self.catalog.characters[cid].display_name)
    def say(self,text):self.toast,self.toast_until=self.t(text),time.time()+4
    def set_language(self,language):
        if language not in ('ko','en'):return
        old=self.catalog;old_self=self.t('잠깐 쉬어가기');self.language=language;self.catalog=deepcopy(self.original_catalog)
        for char in self.catalog.characters.values():
            for key,value in char.translations.get(language,{}).items():setattr(char,key,value)
            if self.notes.get(char.id)==old.characters[char.id].note:self.notes[char.id]=char.note
            for message in self.state.conversations[char.id].messages:
                if message.id=='greeting-'+char.id:message.text=char.greeting
        for post in self.catalog.posts.values():
            for key,value in post.translations.get(language,{}).items():setattr(post,key,value)
        if self.notes.get('self')==old_self:self.notes['self']=self.t('잠깐 쉬어가기')
        bot_builder.install_catalog(self)
    def prepare_request(self,request):
        request.language=self.language
        if request.conversation_id in self.bots:request.custom_persona=bots.active_card(self.bots[request.conversation_id])
    def handle(self,action):
        kind,p=action.kind,action.payload;state=self.state;cid=p.get('character_id') or state.active_conversation_id
        if bot_builder.handle(self,kind,p,cid):pass
        elif kind=='language':self.set_language(p['language'])
        elif kind=='privacy_menu':self.modal={'kind':'private_session'}
        elif kind=='fresh_session' and getattr(self,'web',False):self.transport.bridge.freshSession()
        elif kind=='open_thread':self.modal=None;self.searching=False;open_thread(state,cid,True)
        elif kind=='inbox':state.routes=[Route('inbox')];state.active_conversation_id=None;self.modal=None;self.searching=False
        elif kind=='back':
            if self.modal:self.modal=None
            elif self.searching:self.searching=False;self.query=''
            elif len(state.routes)>1:navigate_back(state)
        elif kind=='search':self.searching=True;self.query='';self.edit_value=''
        elif kind=='send' and cid:
            try:request=queue_message(state,cid,p.get('text',state.conversations[cid].draft))
            except ValueError as exc:self.say(str(exc));return
            if request:
                request.tone=self.tones.get(cid,'balanced');self.prepare_request(request);self.transport.start_chat(request);state.conversations[cid].scroll=0
        elif kind=='retry' and cid:
            conv=state.conversations[cid];message=next((m for m in conv.messages if m.id==p['message_id']),None)
            if message and message.status=='failed':
                message.status='pending';conv.inflight.add(message.id);conv.error=''
                request=ChatRequest(state.session_id,cid,conv.epoch,message.id,message.text,message.reply_to,message.shared_post_id,state.aliases.get(cid),self.tones.get(cid,'balanced'),self.language)
                self.prepare_request(request);self.transport.start_chat(request)
        elif kind=='reset' and cid:
            self.transport.reset(cid,reset_thread(state,cid));self.modal=None;self.say('대화를 비웠어요.')
        elif kind=='focus':
            state.focused=bool(p['focused'])
            if state.focused and state.route.screen=='thread':open_thread(state,state.route.character_id,True)
        elif kind=='settings':state.routes.append(Route('settings',cid))
        elif kind=='menu':self.modal={'kind':'thread_menu','character_id':cid or state.route.character_id}
        elif kind=='compose':self.modal={'kind':'contacts'}
        elif kind=='requests':self.modal={'kind':'requests'}
        elif kind=='close_modal':self.modal=None
        elif kind=='note':self.modal={'kind':'note','character_id':p.get('character_id','self')}
        elif kind=='reply_note':open_thread(state,cid,True);state.conversations[cid].draft=f'“{self.notes[cid]}” ';self.modal=None
        elif kind=='profile' and cid:self.modal=None;state.routes.append(Route('profile',cid))
        elif kind=='post':
            post=self.catalog.posts[p['post_id']];self.modal=None;state.routes.append(Route('post',post.character_id,post.id))
        elif kind=='page':
            route=state.route;post=self.catalog.posts[route.post_id];route.page=carousel_page(route.page,p['delta'],len(post.images))
        elif kind=='follow' and cid:
            if cid in self.following:self.following.remove(cid)
            else:self.following.add(cid)
        elif kind in ('like','save','repost'):
            collection={'like':self.liked_posts,'save':self.saved_posts,'repost':self.reposted}[kind];pid=p['post_id']
            if pid in collection:collection.remove(pid)
            else:collection.add(pid)
        elif kind=='share':self.modal={'kind':'share','post_id':p['post_id']}
        elif kind=='share_post':
            request=share_post(state,cid,p['post_id'],self.t('이 게시물 봤어?'));request.tone=self.tones.get(cid,'balanced');self.prepare_request(request)
            self.transport.start_chat(request);self.modal=None;open_thread(state,cid,True);state.conversations[cid].scroll=0
        elif kind in ('rename','edit_note'):
            self.modal={'kind':kind,'character_id':cid if kind=='rename' else 'self'};self.edit_value=self.name(cid) if kind=='rename' else self.notes['self']
        elif kind=='save_edit' and self.modal:
            if self.modal['kind']=='rename':
                try:rename_character(state,self.modal['character_id'],self.edit_value)
                except ValueError as exc:self.say(str(exc));return
            else:self.notes['self']=self.edit_value.strip()[:60]
            self.modal=None
        elif kind=='tone_menu':self.modal={'kind':'tone_menu','character_id':cid}
        elif kind=='set_tone':self.tones[cid]=p['tone'];self.modal=None;self.say('대화 말투를 바꿨어요.')
        elif kind=='message_menu':self.modal={'kind':'message_menu','character_id':cid,'message_id':p['message_id']}
        elif kind in ('react','quote','copy'):
            message=next((m for m in state.conversations[cid].messages if m.id==p['message_id']),None)
            if message:
                if kind=='react':message.reaction=None if message.reaction else 'heart'
                elif kind=='quote':state.conversations[cid].reply_to=message.id
                else:
                    try:
                        if getattr(self,'web',False):self.transport.bridge.copy(message.text)
                        else:
                            import pygame
                            pygame.scrap.put_text(message.text)
                        self.say('텍스트를 복사했어요.')
                    except Exception:self.say('이 환경에서는 복사할 수 없어요.')
            self.modal=None
        elif kind=='cancel_reply' and cid:state.conversations[cid].reply_to=None
        elif kind=='attachment_info':self.say('사진은 프로필의 게시물에서 공유할 수 있어요.')
        elif kind=='comments':self.say('댓글 대신 메시지로 이야기를 나눠 보세요.')
        elif kind=='history':self.save_history=not self.save_history
        elif kind=='sound':self.sound=not self.sound
        elif kind=='out_of_scope':self.say('여기서는 메시지와 프로필을 이용할 수 있어요.')
        if self.on_change:self.on_change()
    def tick(self,now):
        previous=self.state.notifications[-1] if self.state.notifications else None
        for event in self.transport.drain_events():
            if event.kind=='error':event.payload['message']=self.t(event.payload.get('message','답장을 불러오지 못했어요.'))
            apply_event(self.state,event)
        latest=self.state.notifications[-1] if self.state.notifications else None
        if self.sound and latest is not None and latest is not previous:
            from unsent.client.audio import notify
            notify()
        if self.on_change:self.on_change()
