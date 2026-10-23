"""Private server-authenticated identities; caller session IDs are only labels."""
import hashlib
import hmac
import os
import secrets
import stat
from pathlib import Path


def private_directory(path):
    path=Path(path);path.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.is_symlink() or not path.is_dir():raise ValueError('Use a private real data directory')
    path.chmod(0o700);return path


class Identities:
    def __init__(self,data_dir=None):
        self.key=secrets.token_bytes(32)
        if data_dir:
            path=private_directory(data_dir)/'identity.key';flags=getattr(os,'O_NOFOLLOW',0)
            try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|flags,0o600)
            except FileExistsError:
                fd=os.open(path,os.O_RDONLY|flags)
                with os.fdopen(fd,'rb') as source:
                    info=os.fstat(source.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077:raise ValueError('Identity key must be private (0600)')
                    self.key=source.read(33)
                if len(self.key)!=32:raise ValueError('Invalid identity key')
            else:
                with os.fdopen(fd,'wb') as target:target.write(self.key)
        self.instance=self.digest('instance')[:16]
        self.cookie_name='unsent_identity_'+self.instance
        self.revoked=set()

    def digest(self,value):return hmac.new(self.key,value.encode(),hashlib.sha256).hexdigest()
    def issue(self):
        owner=secrets.token_hex(24);return owner,owner+'.'+self.digest('identity:'+owner)
    def verify(self,token):
        if not token or len(token)!=113 or not token.isascii():return None
        owner,_,signature=token.partition('.')
        if len(owner)!=48 or owner in self.revoked:return None
        if not hmac.compare_digest(signature,self.digest('identity:'+owner)):return None
        return owner
    def public(self,owner):return {'storage_scope':self.instance+':'+self.digest('storage:'+owner)[:32],'csrf_token':self.digest('csrf:'+owner)}
    def session(self,owner,client_session):return owner+':'+client_session
