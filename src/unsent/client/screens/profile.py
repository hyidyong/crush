import pygame
from unsent.client.theme import THEME as T

def render(c,ui):
    w,h=c.width,c.height;t=ui.t;route=ui.state.route;cid=route.character_id;char=ui.catalog.characters[cid];custom=cid in ui.bots
    route.scroll=max(0,min(route.scroll,0 if custom else 550));s=route.scroll
    previous=c.surface.get_clip();c.surface.set_clip(pygame.Rect(0,100*c.scale,w*c.scale,(h-178)*c.scale))
    c.image(char.avatar,(16,131-s,88,88),True)
    values=(len(char.post_ids),max(0,char.followers+(1 if cid in ui.following and custom else -1 if cid not in ui.following and not custom else 0)),char.following)
    for i,(value,label) in enumerate(zip(values,('게시물','팔로워','팔로잉'))):
        c.text(value,120+i*94,147-s,18,bold=True,width=94,align='center');c.text(t(label),120+i*94,175-s,12,width=94,align='center')
    c.text(ui.name(cid),16,232-s,15,bold=True);c.text(char.bio,16,256-s,13,width=w-32,max_lines=2)
    c.text(t('내가 만든 개인 AI 봇' if custom else '가상 인물 · 사진은 AI로 생성'),16,304-s,10,color=T.muted)
    c.button(t('설정 편집' if custom else '팔로잉' if cid in ui.following else '팔로우'),(16,336-s,184,33),'edit_bot' if custom else 'follow',character_id=cid)
    c.button(t('메시지'),(206,336-s,w-222,33),'open_thread',character_id=cid)
    if not custom:
        for i,pid in enumerate(char.post_ids[:3]):
            x=20+i*88;c.image(ui.catalog.posts[pid].images[0],(x,390-s,66,66),True);c.text(t(('기록','일상','좋은 날')[i]),x-3,464-s,11,width=72,align='center');c.hit((x,386-s,70,99),'post',post_id=pid)
    c.icon('grid',w/2-12,512-s,24);c.rect((0,551-s,w,1),T.border)
    for i,pid in enumerate(char.post_ids):
        tw=(w-2)/3;th=tw*4/3;x=(i%3)*(tw+1);y=553+(i//3)*(th+1)-s
        c.image(ui.catalog.posts[pid].images[0],(x,y,tw,th));hit=pygame.Rect(x,y,tw,th).clip(pygame.Rect(0,100,w,h-178))
        if hit.h:c.hit(hit,'post',post_id=pid)
    if custom:c.text(t('공개 피드 없이 나만 대화하는 프로필이에요.'),24,602,13,color=T.muted,width=w-48,align='center')
    c.surface.set_clip(previous);c.rect((0,45,w,55),T.background);c.icon('back',12,59);c.hit((0,45,46,55),'back');c.text(char.handle,53,60,19,bold=True,width=w-110,max_lines=1);c.icon('more',374,64);c.hit((355,45,59,55),'menu',character_id=cid);c.tabbar(ui.catalog)
