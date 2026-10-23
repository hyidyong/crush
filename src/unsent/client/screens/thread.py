import pygame
from unsent.client.theme import THEME as T

def render(c,ui):
    w,h=c.width,c.height;t=ui.t;cid=ui.state.route.character_id;char=ui.catalog.characters[cid];conv=ui.state.conversations[cid]
    c.icon('back',12,59);c.hit((0,45,46,50),'back');c.image(char.avatar,(49,52,35,35),True)
    c.text(ui.name(cid),94,53,15,bold=True,width=w-145,max_lines=1);c.text(char.handle,94,76,10,color=T.muted,width=w-145,max_lines=1)
    c.hit((45,45,w-100,50),'profile',character_id=cid);c.icon('more',374,62);c.hit((355,44,59,55),'menu',character_id=cid)
    c.rect((0,99,w,1),T.border)
    health=getattr(ui.transport,'health',{});connected=bool(health.get('configured') or health.get('connected') or health.get('model_ready') or health.get('model')=='reachable')
    top=104
    if not connected:
        c.rect((0,100,w,30),T.elevated);c.text(t('AI 서버 설정이 필요해요'),14,107,11,color=T.muted);c.hit((0,100,w,30),'settings');top=135
    lines=c.type.lines(conv.draft or t('메시지…'),w-140,14);height=max(48,min(4,len(lines))*22+20);cy=h-height-25;bottom=cy-9
    blocks=[];total=267
    for m in conv.messages:
        line_count=len(c.type.lines(m.text,248,14));mh=line_count*21+22+(24 if m.reply_to else 0)+(128 if m.shared_post_id else 0)
        blocks.append((m,mh));total+=mh+11+(18 if m.reaction else 0)
    total+=48
    conv.scroll=max(0,min(conv.scroll,max(0,total-(bottom-top))))
    y=bottom-total+conv.scroll if total>bottom-top else top
    prior=c.surface.get_clip();viewport=pygame.Rect(0,top,w,max(0,bottom-top));c.surface.set_clip(pygame.Rect(0,top*c.scale,w*c.scale,viewport.h*c.scale))
    c.image(char.avatar,(w/2-45,y+16,90,90),True);c.text(ui.name(cid),20,y+120,22,bold=True,width=w-40,align='center')
    c.text(char.handle,20,y+152,12,color=T.muted,width=w-40,align='center')
    c.text(t('내가 만든 개인 AI 봇' if cid in ui.bots else '가상 인물 · AI 대화'),20,y+174,11,color=T.muted,width=w-40,align='center')
    c.button(t('프로필 보기'),(w/2-57,y+203,114,32),'profile',character_id=cid);y+=267
    last_user=next((m.id for m in reversed(conv.messages) if m.sender=='user'),None)
    for m,mh in blocks:
        widths=[c.type.width(line,14) for line in c.type.lines(m.text,248,14)];bw=min(274,max(70,max(widths,default=60)+26));bw=max(bw,160 if m.shared_post_id else 0)
        x=w-14-bw if m.sender=='user' else 50
        c.rect((x,y,bw,mh),T.outgoing if m.sender=='user' else T.surface,18)
        ty=y+10
        if m.reply_to:c.text('↳ '+t('답장'),x+13,ty,11,color=T.muted,width=bw-26,max_lines=1);ty+=24
        if m.shared_post_id in ui.catalog.posts:
            post=ui.catalog.posts[m.shared_post_id];c.image(post.images[0],(x+7,ty,bw-14,116));hit=pygame.Rect(x+7,ty,bw-14,116).clip(viewport)
            if hit.h:c.hit(hit,'post',post_id=post.id)
            ty+=128
        c.text(m.text,x+13,ty,14,width=bw-26)
        if m.sender=='agent':c.image(char.avatar,(12,y+mh-26,26,26),True)
        hit=pygame.Rect(x,y,bw,mh).clip(viewport)
        if hit.h:c.hit(hit,'message',character_id=cid,message_id=m.id)
        if m.status=='failed':c.text('!',max(5,x-23),y+mh-22,16,color=T.red);c.hit((max(0,x-32),y,32,mh),'retry',character_id=cid,message_id=m.id)
        y+=mh+11
        if m.reaction:c.text('♥',x+8,y-5,14,color=T.red);y+=18
        if m.id==last_user:
            label={'pending':'전송 중…','sent':'보냄','seen':'읽음','failed':'전송 실패 · 다시 시도'}.get(m.status,'보냄')
            c.text(t(label),14,y-2,10,color=T.muted,width=w-28,align='right');y+=20
    if conv.typing:c.text(t('입력 중…'),50,y,12,color=T.muted)
    c.surface.set_clip(prior)
    if conv.reply_to:
        c.rect((10,cy-37,w-20,32),T.elevated,8);c.text(t('답장할 메시지를 선택했어요'),20,cy-30,11,color=T.muted);c.icon('close',w-42,cy-28,16);c.hit((w-55,cy-37,45,32),'cancel_reply',character_id=cid)
    if conv.error:c.text(conv.error,14,cy-57,10,color=T.red,width=w-28,max_lines=2)
    c.rect((10,cy,w-20,height),T.elevated,27);c.rect((17,cy+8,32,32),T.accent,17);c.icon('camera',24,cy+15,18);c.hit((17,cy+8,32,32),'attachment_info')
    if not getattr(ui,'web',False):c.text(conv.draft or t('메시지…'),58,cy+12,14,color=T.text if conv.draft else T.muted,width=w-140,max_lines=4)
    if conv.draft.strip():c.text(t('보내기'),w-66,cy+14,13,color=T.accent,bold=True);c.hit((w-76,cy,65,height),'send',character_id=cid)
    else:c.icon('heart',w-47,cy+14,22);c.hit((w-58,cy,47,height),'send',character_id=cid,text='♡')
    return (58,cy+12,w-137,height-20)
