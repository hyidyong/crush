"""Model connections and credentials remain on the application backend."""
import ssl
from dataclasses import dataclass,field
from urllib.parse import urlsplit
import httpx

@dataclass
class BackendSettings:
    provider:str|None=None
    base_url:str|None=None
    model:str|None=None
    api_key:str|None=field(default=None,repr=False)
    response_mode:str='json'
    timeout_s:float=120
    access_token:str|None=field(default=None,repr=False)
    catalog_path:str|None=None
    data_dir:str|None=None
    allowed_hosts:tuple[str,...]=('localhost','127.0.0.1','::1')

class OpenAIProvider:
    def __init__(self,settings,transport=None):self.settings=settings;self.transport=transport
    def client(self,timeout):
        host=urlsplit(self.settings.base_url or '').hostname
        return httpx.AsyncClient(transport=self.transport,timeout=timeout,verify=ssl.create_default_context(),trust_env=host not in ('localhost','127.0.0.1','::1'))
    @property
    def headers(self):return {'Authorization':'Bearer '+self.settings.api_key} if self.settings.api_key else {}
    async def reply(self,messages,*,max_tokens=1024,timeout=120):
        body={'model':self.settings.model,'messages':messages,'max_tokens':max_tokens,'temperature':.7,'top_p':.8,'stream':False}
        if self.settings.response_mode=='json':body['response_format']={'type':'json_object'}
        async with self.client(timeout) as client:
            response=await client.post(self.settings.base_url.rstrip('/')+'/chat/completions',headers=self.headers,json=body)
            response.raise_for_status();return response.json()['choices'][0]['message']['content']
    async def health(self):
        async with self.client(4) as client:
            response=await client.get(self.settings.base_url.rstrip('/')+'/models',headers=self.headers);response.raise_for_status()
            return any(m.get('id')==self.settings.model for m in response.json().get('data',[]))

class OllamaProvider(OpenAIProvider):
    @property
    def root(self):
        root=self.settings.base_url.rstrip('/');return root[:-3] if root.endswith('/v1') else root
    async def reply(self,messages,*,max_tokens=1024,timeout=120):
        body={'model':self.settings.model,'messages':messages,'stream':False,'think':False,'keep_alive':'10m',
              'options':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0,'num_predict':max_tokens,'num_ctx':8192}}
        if self.settings.response_mode=='json':body['format']={'type':'object','properties':{'bubbles':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':3}},'required':['bubbles'],'additionalProperties':False}
        async with self.client(timeout) as client:
            response=await client.post(self.root+'/api/chat',headers=self.headers,json=body);response.raise_for_status();return response.json()['message']['content']
    async def health(self):
        async with self.client(4) as client:
            response=await client.get(self.root+'/api/tags',headers=self.headers);response.raise_for_status()
            return any(m.get('name')==self.settings.model for m in response.json().get('models',[]))

def make_provider(settings):
    if not settings.base_url or not settings.model:return None
    if settings.provider=='ollama':return OllamaProvider(settings)
    if settings.provider=='openai_compatible':return OpenAIProvider(settings)
    return None
