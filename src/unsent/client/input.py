from dataclasses import dataclass
@dataclass
class InputEvent:
    kind:str
    text:str=''
    key:str=''
    shift:bool=False
@dataclass
class InputResult:
    kind:str='none'
    text:str=''
class TextEntry:
    def __init__(self,text=''):self.text=text;self.composing=False;self.preedit=''
    def handle(self,event):
        before=self.text
        if event.kind=='composition_start':self.composing=True
        elif event.kind=='composition_end':self.text=event.text[:2000];self.composing=False;self.preedit=''
        elif event.kind=='replace':self.text=event.text[:2000]
        elif event.kind=='text':self.text=(self.text+event.text)[:2000];self.composing=False;self.preedit=''
        elif event.kind=='key' and not self.composing:
            if event.key=='Enter':
                if event.shift:self.text=(self.text+'\n')[:2000]
                elif self.text.strip():
                    value,self.text=self.text,'';return InputResult('submit',value)
            elif event.key=='Backspace':self.text=self.text[:-1]
        return InputResult('changed' if before!=self.text else 'none',self.text)
