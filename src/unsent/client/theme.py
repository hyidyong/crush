from dataclasses import dataclass
@dataclass(frozen=True)
class Theme:
    background:tuple=(0,0,0)
    surface:tuple=(38,38,38)
    elevated:tuple=(28,28,28)
    border:tuple=(48,48,48)
    text:tuple=(245,245,245)
    muted:tuple=(160,160,168)
    accent:tuple=(88,81,255)
    outgoing:tuple=(85,55,217)
    red:tuple=(255,55,82)
THEME=Theme()
