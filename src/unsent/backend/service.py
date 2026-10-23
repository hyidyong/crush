import asyncio
import json
import re
import uuid
from pathlib import Path
from unsent.backend.persona import build_messages
from unsent.backend.sessions import ConversationSession,RequestRecord,SessionStore
from unsent.shared.contracts import ChatEvent


def message(language,ko,en):return en if language=='en' else ko

def parse_bubbles(raw):
    if not isinstance(raw,str):raise ValueError('Invalid model response')
    raw=re.sub(r'<think>.*?</think>','',raw,flags=re.S).strip()
    if raw.startswith('```'):raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw).strip()
    try:data=json.loads(raw)
    except (ValueError,TypeError) as exc:raise ValueError('Invalid model JSON') from exc
    if not isinstance(data,dict) or set(data)!={'bubbles'}:raise ValueError('Invalid model schema')
    bubbles=data['bubbles']
    if not isinstance(bubbles,list) or not 1<=len(bubbles)<=3 or any(not isinstance(b,str) or not b.strip() or len(b)>280 for b in bubbles) or sum(map(len,bubbles))>600:raise ValueError('Invalid model bubbles')
    return [b.strip() for b in bubbles]


class ChatService:
    def __init__(self,settings,provider):self.settings=settings;self.provider=provider;self.store=SessionStore()
    def conversation(self,session_id,conversation_id,epoch=0):
        return self.store.get(session_id).conversations.setdefault(conversation_id,ConversationSession(epoch=epoch))
    def emit(self,record,kind,payload=None,message_id=None):
        r=record.request;record.events.append(ChatEvent(kind,r.conversation_id,r.epoch,record.request_id,message_id or r.client_message_id,payload or {}));record.changed.set()
    async def stream(self,request):
        self.store.expire();conv=self.conversation(request.session_id,request.conversation_id,request.epoch)
        if request.epoch>conv.epoch:self.reset(request.session_id,request.conversation_id,request.epoch)
        record=conv.records.get(request.client_message_id)
        if record is None or record.finished and record.failed:
            record=RequestRecord(request,uuid.uuid4().hex);conv.records[request.client_message_id]=record
            self.emit(record,'accepted');record.task=asyncio.create_task(self.produce(conv,record))
        index=0
        while True:
            while index<len(record.events):yield record.events[index];index+=1
            if record.finished:return
            record.changed.clear()
            if index<len(record.events):continue
            await record.changed.wait()
    def post_context(self,post_id,language='ko'):
        if not post_id or not self.settings.catalog_path:return ''
        try:
            data=json.loads(Path(self.settings.catalog_path).read_text());post=next(p for p in data['posts'] if p['id']==post_id)
            if language=='en':post={**post,**post.get('translations',{}).get('en',{})}
            return json.dumps({'caption':post['caption'],'description':post.get('description','')},ensure_ascii=False)
        except (OSError,ValueError,KeyError,StopIteration):return ''
    async def produce(self,conv,record):
        r=record.request
        try:
            async with asyncio.timeout(self.settings.timeout_s):
                async with conv.lock:
                    if r.epoch!=conv.epoch:raise ValueError('Stale conversation')
                    if self.provider is None:
                        record.failed=True;self.emit(record,'error',{'message':message(r.language,'AI 연결이 필요해요. 설정에서 연결 상태를 확인해 주세요.','An AI connection is needed. Check Settings.'),'code':'unconfigured'});return
                    self.emit(record,'seen');self.emit(record,'typing',{'active':True})
                    quote=''
                    for turn in reversed(conv.history):
                        if r.reply_to in turn.get('bubble_texts',{}):quote=turn['bubble_texts'][r.reply_to];break
                        if turn.get('id')==r.reply_to:quote=turn['content'];break
                    messages=build_messages(r,conv.history,self.post_context(r.shared_post_id,r.language),quote,self.settings.response_mode)
                    for attempt in range(2):
                        raw=await self.provider.reply(messages,max_tokens=1024,timeout=self.settings.timeout_s)
                        try:
                            if self.settings.response_mode=='text':
                                text=raw.strip()
                                if not text or len(text)>280 or '<think>' in text:raise ValueError('Invalid text reply')
                                bubbles=parse_bubbles(text) if text.startswith('{') else [text]
                            else:bubbles=parse_bubbles(raw)
                            if r.language=='en':
                                reply=' '.join(bubbles)
                                if len(re.findall('[가-힣]',reply))>len(re.findall('[A-Za-z]',reply))/3:raise ValueError('Reply language mismatch')
                            break
                        except ValueError:
                            if attempt:raise
                            repair=message(r.language,'짧은 답장 본문만 한국어로280자 이하로 다시 보내세요.' if self.settings.response_mode=='text' else '다른 설명 없이 {"bubbles":["짧은 답장"]} JSON 형식과 길이 제한만 지켜 다시 답하세요.',
                                           'Reply in English. Send only the short reply text, at most280 characters.' if self.settings.response_mode=='text' else 'Reply in English. Output only {"bubbles":["short reply"]} within stated length limits.')
                            messages.append({'role':'user','content':repair})
                    if r.epoch!=conv.epoch:return
                    conv.history.append({'role':'user','content':r.text,'id':r.client_message_id})
                    for i,bubble in enumerate(bubbles):self.emit(record,'bubble',{'text':bubble},f'{record.request_id}.{i}')
                    conv.history.append({'role':'assistant','content':'\n'.join(bubbles) if self.settings.response_mode=='text' else json.dumps({'bubbles':bubbles},ensure_ascii=False),'id':record.request_id+'.0',
                                         'bubble_texts':{f'{record.request_id}.{i}':text for i,text in enumerate(bubbles)}})
                    conv.history[:]=conv.history[-40:]
        except asyncio.CancelledError:pass
        except TimeoutError:
            record.failed=True;self.emit(record,'error',{'message':message(r.language,'답장이 오래 걸리고 있어요. 잠시 후 다시 보내 주세요.','The reply is taking a while. Please try again.'),'code':'timeout'})
        except Exception:
            record.failed=True;self.emit(record,'error',{'message':message(r.language,'답장을 불러오지 못했어요. 연결을 확인하고 다시 시도해 주세요.','Could not load the reply. Check your connection and try again.'),'code':'upstream'})
        finally:
            self.emit(record,'typing',{'active':False});self.emit(record,'done');record.finished=True;record.changed.set()
    def reset(self,session_id,conversation_id,epoch):
        conv=self.conversation(session_id,conversation_id)
        if epoch<=conv.epoch:return
        conv.epoch=epoch;conv.history.clear()
        for record in conv.records.values():
            if record.task and not record.task.done():record.task.cancel()
        conv.records.clear()
    def close(self):self.store.close()
