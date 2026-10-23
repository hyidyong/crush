from collections import OrderedDict
from pathlib import Path
import pygame
from unsent.client.icons import icon_surface
from unsent.client.text import TextRenderer
from unsent.client.theme import THEME

def load_media(root,name):
    path,_,region=name.partition('#');image=pygame.image.load(str(Path(root)/path)).convert_alpha()
    if region:image=image.subsurface(pygame.Rect(*map(int,region.split(',')))).copy()
    return image

class Canvas:
    def __init__(self,asset_root,width=414,height=896,scale=2):
        self.root=Path(asset_root);self.width=width;self.height=height;self.scale=scale
        self.surface=pygame.Surface((round(width*scale),round(height*scale)))
        self.type=TextRenderer(self.root/'fonts',scale);self.cache=OrderedDict();self.hits=[]
    def rect(self,xywh,color,radius=0,width=0):
        pygame.draw.rect(self.surface,color,pygame.Rect(*(round(v*self.scale) for v in xywh)),round(width*self.scale),border_radius=round(radius*self.scale))
    def text(self,text,x,y,size=14,color=None,bold=False,width=None,**style):
        return self.type.draw(self.surface,str(text),(x,y,width or self.width-x,0),dict(size=size,color=color or THEME.text,bold=bold,**style))
    def icon(self,name,x,y,size=24,color=None,filled=False):
        self.surface.blit(icon_surface(name,round(size*self.scale),tuple(color or THEME.text),filled),(round(x*self.scale),round(y*self.scale)))
    def image(self,name,rect,circle=False):
        x,y,w,h=rect;target=round(w*self.scale),round(h*self.scale);key=name,target,circle
        if key not in self.cache:
            image=load_media(self.root,name);factor=max(target[0]/image.get_width(),target[1]/image.get_height())
            image=pygame.transform.smoothscale(image,(max(1,round(image.get_width()*factor)),max(1,round(image.get_height()*factor))))
            out=pygame.Surface(target,pygame.SRCALPHA);out.blit(image,((target[0]-image.get_width())//2,(target[1]-image.get_height())//2))
            if circle:
                mask=pygame.Surface(target,pygame.SRCALPHA);pygame.draw.ellipse(mask,(255,255,255,255),mask.get_rect());out.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
            self.cache[key]=out
            while len(self.cache)>64:self.cache.popitem(last=False)
        else:self.cache.move_to_end(key)
        self.surface.blit(self.cache[key],(round(x*self.scale),round(y*self.scale)))
    def hit(self,rect,action,**payload):self.hits.append((pygame.Rect(rect),action,payload))
    def button(self,label,rect,action,*,accent=False,**payload):
        self.rect(rect,THEME.accent if accent else THEME.surface,8);self.text(label,rect[0],rect[1]+9,14,bold=True,width=rect[2],align='center',max_lines=1);self.hit(rect,action,**payload)
    def start(self):self.surface.fill(THEME.background);self.hits.clear()
    def tabbar(self,catalog,selected='inbox'):
        y=self.height-78;self.rect((0,y,self.width,78),THEME.background);self.rect((0,y,self.width,.5),THEME.border);step=self.width/5
        for index,name in enumerate(('home','reels','plane','search','self')):
            x=step*(index+.5)-12
            if name=='self':self.image(catalog.self_avatar,(x,y+18,24,24),True)
            else:self.icon(name,x,y+18,24,filled=name=='plane' and selected=='inbox')
            self.hit((step*index,y,step,60),{2:'inbox',3:'search',4:'settings'}.get(index,'out_of_scope'))
