import asyncio
import json
import secrets
from contextlib import asynccontextmanager,suppress
from dataclasses import asdict,replace
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,StreamingResponse
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from unsent.backend.persona import PERSONAS
from unsent.backend.providers import BackendSettings,make_provider
from unsent.backend.service import ChatService
from unsent.backend.identity import Identities
from unsent.shared.contracts import ChatRequest
from unsent.shared.bots import is_bot_id


class CustomPersonaInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=32)
    bio:str=Field(default='',max_length=160)
    personality:str=Field(min_length=1,max_length=1400)
    examples:str=Field(default='',max_length=600)
    @field_validator('name','personality')
    @classmethod
    def required_text(cls,value):
        if not value.strip() or '\x00' in value:raise ValueError('Nonblank text required')
        return value.strip()

class ChatInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    conversation_id:str=Field(min_length=1,max_length=64)
    epoch:int=Field(ge=0)
    client_message_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_.-]+$')
    text:str=Field(min_length=1,max_length=2000)
    reply_to:str|None=Field(default=None,max_length=80)
    shared_post_id:str|None=Field(default=None,max_length=80)
    display_name:str|None=Field(default=None,max_length=32)
    tone:str=Field(default='balanced',pattern=r'^(balanced|warm|playful|dry)$')
    language:str=Field(default='ko',pattern=r'^(ko|en)$')
    custom_persona:CustomPersonaInput|None=None
    @field_validator('text')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Enter a message')
        return value.strip()
    @model_validator(mode='after')
    def card_contract(self):
        if is_bot_id(self.conversation_id):
            if self.custom_persona is None:raise ValueError('Active private bot settings required')
        elif self.custom_persona is not None:raise ValueError('Private settings require a private bot ID')
        return self

class ResetInput(BaseModel):
    session_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    epoch:int=Field(ge=0)


def create_app(settings=None,provider=None):
    settings=settings or BackendSettings()
    provider=provider if provider is not None else make_provider(settings)
    service=ChatService(settings,provider);identities=Identities(settings.data_dir)
    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:await asyncio.sleep(30);service.store.expire()
        worker=asyncio.create_task(cleanup())
        try:yield
        finally:
            worker.cancel();service.close()
            with suppress(asyncio.CancelledError):await worker
    app=FastAPI(title='Unsent',lifespan=lifespan)
    app.state.service=service;app.state.settings=settings
    @app.middleware('http')
    async def private_access(request:Request,call_next):
        host=urlsplit('//'+request.headers.get('host','')).hostname
        if host not in settings.allowed_hosts:return JSONResponse({'detail':'Unrecognized application host'},status_code=400)
        if request.url.path.startswith('/api/'):
            origin=request.headers.get('origin')
            if request.headers.get('sec-fetch-site')=='cross-site' or origin and origin!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Same-origin access required'},status_code=403)
            if settings.access_token:
                supplied=request.headers.get('authorization','')
                if not supplied.isascii() or not secrets.compare_digest(supplied,'Bearer '+settings.access_token):
                    return JSONResponse({'detail':'Connection authentication required'},status_code=401)
        owner=identities.verify(request.cookies.get(identities.cookie_name));request.state.owner=owner
        if request.url.path.startswith('/api/') and request.method!='GET':
            if not owner:return JSONResponse({'detail':'Private identity required'},status_code=401)
            csrf=request.headers.get('x-unsent-csrf','')
            if not csrf.isascii() or not secrets.compare_digest(csrf,identities.public(owner)['csrf_token']):
                return JSONResponse({'detail':'Private request verification required'},status_code=403)
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self' blob: data:; connect-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
        return response
    def identity_response(request,fresh=False):
        owner=request.state.owner;token=None
        if fresh and owner:
            identities.revoked.add(owner)
            for key in list(service.store.sessions):
                if key.startswith(owner+':'):service.store.drop(key)
            owner=None
        if not owner:owner,token=identities.issue()
        response=JSONResponse(identities.public(owner))
        if token:response.set_cookie(identities.cookie_name,token,httponly=True,secure=request.url.scheme=='https',samesite='strict',max_age=31536000,path='/api/')
        return response
    @app.get('/api/identity')
    async def identity(request:Request):
        if request.headers.get('x-unsent-client')!='1':raise HTTPException(403,'Private client bootstrap required')
        return identity_response(request)
    @app.post('/api/identity/new')
    async def new_identity(request:Request):return identity_response(request,True)
    @app.get('/api/health')
    async def health():
        model='unconfigured'
        if provider is not None:
            try:model='reachable' if not hasattr(provider,'health') or await provider.health() else 'unavailable'
            except Exception:model='unavailable'
        return {'app':'ready','model':model}
    @app.get('/api/catalog')
    async def catalog():
        if settings.catalog_path and Path(settings.catalog_path).is_file():return json.loads(Path(settings.catalog_path).read_text())
        return {'characters':[{'id':key,'display_name':value['name']} for key,value in PERSONAS.items()],'posts':[]}
    @app.post('/api/chat')
    async def chat(body:ChatInput,http_request:Request):
        if body.conversation_id not in PERSONAS and not is_bot_id(body.conversation_id):raise HTTPException(404,'Conversation partner not found')
        request=replace(ChatRequest(**body.model_dump()),session_id=identities.session(http_request.state.owner,body.session_id))
        async def stream():
            async for event in service.stream(request):yield 'data: '+json.dumps(asdict(event),ensure_ascii=False)+'\n\n'
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    @app.post('/api/conversations/{character_id}/reset')
    async def reset(character_id:str,body:ResetInput,request:Request):
        if character_id not in PERSONAS and not is_bot_id(character_id):raise HTTPException(404,'Conversation partner not found')
        service.reset(identities.session(request.state.owner,body.session_id),character_id,body.epoch)
        return {'ok':True,'epoch':body.epoch}
    return app
