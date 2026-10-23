from pathlib import Path
import pygame

class TextRenderer:
    def __init__(self,root,scale=2):
        self.root=Path(root);self.scale=scale;self.fonts={}
    def font(self,size,bold=False):
        key=(size,bold)
        if key not in self.fonts:
            name='NotoSansKR-Bold.ttf' if bold else 'NotoSansKR-Regular.ttf'
            self.fonts[key]=pygame.font.Font(str(self.root/name),round(size*self.scale))
        return self.fonts[key]
    def width(self,text,size=14,bold=False):return self.font(size,bold).size(str(text))[0]/self.scale
    def lines(self,text,width,size=14,bold=False):
        result=[]
        for paragraph in str(text).split('\n'):
            line=''
            for char in paragraph:
                candidate=line+char
                if line and self.width(candidate,size,bold)>width:result.append(line);line=char
                else:line=candidate
            result.append(line)
        return result or ['']
    def draw(self,surface,text,rect,style):
        x,y,w,_=rect;size=style.get('size',14);bold=style.get('bold',False)
        lines=self.lines(text,w,size,bold);maximum=style.get('max_lines')
        if maximum and len(lines)>maximum:
            lines=lines[:maximum]
            tail=lines[-1]
            while tail and self.width(tail+'…',size,bold)>w:tail=tail[:-1]
            lines[-1]=tail+'…'
        lineheight=style.get('line_height',size*1.45)
        for i,line in enumerate(lines):
            image=self.font(size,bold).render(line,True,style.get('color',(245,245,245)))
            xx=x
            if style.get('align')=='center':xx+=(w-image.get_width()/self.scale)/2
            elif style.get('align')=='right':xx+=w-image.get_width()/self.scale
            surface.blit(image,(round(xx*self.scale),round((y+i*lineheight)*self.scale)))
        return len(lines)*lineheight
