"""Only explicit ignored local configuration enables an upstream model."""
import os
import re
import tomllib
from pathlib import Path
from urllib.parse import urlsplit
from unsent.backend.providers import BackendSettings

def bind_host(lan=False):return '0.0.0.0' if lan else '127.0.0.1'

def load_local_settings(config_path=None):
    if config_path is None or not Path(config_path).exists():return BackendSettings()
    data=tomllib.loads(Path(config_path).read_text());model=data.get('model',{});provider=model.get('provider')
    if provider not in (None,'openai_compatible','ollama'):raise ValueError('Unsupported model provider')
    url=model.get('base_url')
    if url:
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Use an HTTP(S) model URL without embedded credentials')
    key=model.get('api_key')
    if model.get('api_key_env'):key=os.getenv(model['api_key_env'])
    mode=model.get('response_mode','json')
    if mode not in ('json','text'):raise ValueError('Unsupported response mode')
    hosts=data.get('server',{}).get('allowed_hosts',[])
    if not isinstance(hosts,list) or any(not isinstance(host,str) or not re.fullmatch(r'[A-Za-z0-9.-]+|::1',host) for host in hosts):raise ValueError('Use explicit application hostnames without wildcards or ports')
    return BackendSettings(provider=provider,base_url=url,model=model.get('name'),api_key=key,response_mode=mode,
        timeout_s=float(model.get('timeout_s',120)),allowed_hosts=tuple(dict.fromkeys(('localhost','127.0.0.1','::1',*map(str.lower,hosts)))))
