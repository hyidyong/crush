import time
import pygame
from unsent.client.theme import THEME as T

def render(c,ui):
    w,h=c.width,c.height;t=ui.t
    c.text('my.archive',30,59,23,bold=True,width=w-60,align='center');c.icon('down',273,69,15)
    c.icon('compose',374,63);c.hit((357,48,57,50),'compose')
    c.rect((14,106,w-28,44),T.surface,24);c.icon('search',29,119,19,color=T.muted)
    c.text(ui.query if ui.searching else t('검색'),62,117,16,color=T.text if ui.query else T.muted)
    c.hit((14,106,w-28,44),'search')
    prior=c.surface.get_clip();c.surface.set_clip(pygame.Rect(0,158*c.scale,w*c.scale,154*c.scale))
    for i,cid in enumerate(['self',*ui.catalog.characters]):
        x=20+113*i;char=ui.catalog.characters.get(cid);avatar=char.avatar if char else ui.catalog.self_avatar
        c.image(avatar,(x,211,78,78),True);c.rect((x-6,169,99,48),T.elevated,17)
        c.text(ui.notes.get(cid,t('메모가 없어요')),x+1,178,12,width=85,align='center',max_lines=2)
        c.text(t('내 메모') if cid=='self' else ui.name(cid),x-7,293,13,width=92,align='center',max_lines=1)
        c.hit((x-6,169,100,140),'note',character_id=cid)
    c.surface.set_clip(prior)
    c.text(t('메시지'),16,329,17,bold=True);c.text(t('요청'),w-71,331,14,color=T.muted);c.hit((w-90,320,90,39),'requests')
    viewport=pygame.Rect(0,365,w,h-443);prior=c.surface.get_clip();c.surface.set_clip(pygame.Rect(0,365*c.scale,w*c.scale,viewport.h*c.scale))
    contacts=[cid for cid in ui.catalog.characters if ui.query.lower() in (ui.name(cid)+' '+ui.catalog.characters[cid].handle).lower()]
    contacts.sort(key=lambda cid:max((m.created_at for m in ui.state.conversations[cid].messages),default=0),reverse=True)
    ui.state.route.scroll=max(0,min(ui.state.route.scroll,max(0,len(contacts)*76-viewport.h)))
    for i,cid in enumerate(contacts):
        y=365+i*76-ui.state.route.scroll;conv=ui.state.conversations[cid];char=ui.catalog.characters[cid]
        c.image(char.avatar,(16,y+7,56,56),True);c.text(ui.name(cid),84,y+12,15,bold=bool(conv.unread),width=w-125,max_lines=1)
        last=conv.messages[-1] if conv.messages else None
        preview=(t('새 메시지 {count}개',count=conv.unread) if conv.unread>1 else last.text if last else t('메시지 보내기'))
        if last and last.sender=='user':preview=t('보냄')+' · '+preview
        c.text(preview,84,y+36,14,color=T.text if conv.unread else T.muted,width=w-125,max_lines=1)
        if conv.unread:c.rect((w-24,y+31,8,8),T.accent,4)
        hit=pygame.Rect(0,y,w,76).clip(viewport)
        if hit.h:c.hit(hit,'open_thread',character_id=cid)
    if not contacts:c.text(t('검색 결과가 없어요'),20,405,14,color=T.muted)
    c.surface.set_clip(prior);c.tabbar(ui.catalog)
    return (62,114,w-85,28) if ui.searching else None
