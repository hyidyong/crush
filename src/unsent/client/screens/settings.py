from unsent.client.theme import THEME as T

def render(c,ui):
    w,h=c.width,c.height;t=ui.t;c.icon('back',12,59);c.hit((0,45,48,55),'back');c.text(t('설정'),55,59,20,bold=True)
    c.text(t('대화 설정'),20,133,24,bold=True);c.text(t('AI 연결'),20,190,14,bold=True)
    health=getattr(ui.transport,'health',{});connected=health.get('configured') or health.get('connected') or health.get('model_ready') or health.get('model')=='reachable'
    c.text(t('모델 서버에 연결됨' if connected else 'AI 서버 설정 필요'),20,218,13,color=T.accent if connected else T.muted)
    c.text(t('서버·모델 설정은 실행 폴더의 개인 설정에서\n바꿀 수 있어요. API 키는 서버에만 보관해요.'),20,252,12,color=T.muted,width=w-40)
    c.rect((20,318,w-40,.5),T.border)
    for label,enabled,y,action in [('알림 소리',ui.sound,345,'sound'),('대화 저장',ui.save_history,410,'history')]:
        c.text(t(label),20,y,15);c.rect((w-88,y-10,68,36),T.accent if enabled else T.surface,20);c.rect((w-88+(35 if enabled else 4),y-6,28,28),T.text,14);c.hit((w-98,y-16,88,48),action)
    c.text(t('기기 저장은 기본으로 꺼져 있어요. 켜면 기기에\n저장해요. 서버 재시작 시 AI 기억은 초기화돼요.'),20,451,11,color=T.muted,width=w-40)
    c.text(t('언어'),20,531,15,bold=True);c.button('한국어',(20,565,178,38),'language',accent=ui.language=='ko',language='ko');c.button('English',(210,565,w-230,38),'language',accent=ui.language=='en',language='en')
    c.text(t('언어 안내'),20,616,11,color=T.muted,width=w-40,max_lines=2)
    if getattr(ui,'web',False):c.button(t('새 비공개 세션'),(20,666,w-40,40),'privacy_menu')
    c.text(t('개인정보 안내'),20,729,11,color=T.muted,width=w-40);c.tabbar(ui.catalog,selected='settings')
