import pygame
from unsent.client.theme import THEME as T

def render(c,ui):
    w,h=c.width,c.height;t=ui.t;r=ui.state.route;p=ui.catalog.posts[r.post_id];ch=ui.catalog.characters[p.character_id]
    # Texture-atlas crops have an explicit source ratio.
    from unsent.shared.catalog import asset_reference
    _,region=asset_reference(p.images[r.page]);ratio=region[3]/region[2] if region else 1
    media_h=w*ratio;total=58+media_h+208;r.scroll=max(0,min(r.scroll,max(0,total-(h-101))))
    y=101-r.scroll;previous=c.surface.get_clip();c.surface.set_clip(pygame.Rect(0,101*c.scale,w*c.scale,(h-101)*c.scale))
    c.image(ch.avatar,(12,y+11,33,33),True);c.text(ui.name(ch.id),54,y+10,14,bold=True);c.text(t('일상의 기록'),54,y+32,10,color=T.muted);c.hit((0,y,w,57),'profile',character_id=ch.id)
    my=y+58;c.image(p.images[r.page],(0,my,w,media_h))
    if len(p.images)>1:
        c.rect((w-54,my+14,42,26),T.surface,15);c.text(f'{r.page+1}/{len(p.images)}',w-54,my+18,11,width=42,align='center')
    c.hit((0,my,w/2,media_h),'page',delta=-1);c.hit((w/2,my,w/2,media_h),'page',delta=1)
    ay=my+media_h+29
    for icon,x,action,active in [('heart',14,'like',p.id in ui.liked_posts),('comment',78,'comments',False),('repost',120,'repost',p.id in ui.reposted),('plane',162,'share',False),('bookmark',w-38,'save',p.id in ui.saved_posts)]:
        c.icon(icon,x,ay,25,color=T.red if icon=='heart' and active else T.accent if active else T.text,filled=active);c.hit((x-4,ay-8,38,42),action,post_id=p.id)
    c.text(p.like_count+(p.id in ui.liked_posts),44,ay+3,14,bold=True);c.text(t('여러 명이 좋아합니다'),14,ay+43,13)
    c.text(ch.handle+'  '+p.caption,14,ay+69,13,width=w-28,max_lines=3);c.text(p.created_at,14,ay+145,10,color=T.muted)
    c.surface.set_clip(previous);c.rect((0,45,w,56),T.background);c.rect((0,100,w,.5),T.border);c.icon('back',12,59);c.hit((0,45,48,55),'back');c.text(t('게시물'),50,52,16,bold=True,width=w-100,align='center');c.text(ch.handle,50,77,11,color=T.muted,width=w-100,align='center')
