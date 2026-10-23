from copy import deepcopy
from unsent.shared import bots
from unsent.shared.contracts import Character,Route
from unsent.domain.state import Conversation
ACTIONS={'bot_library','new_bot','edit_bot','save_bot','delete_bot','confirm_bot_delete','bot_field','bot_avatar','bot_import','bot_import_file','bot_import_path','clear_draft_docs','bot_history','bot_source','clear_bot_records','restore_bot_revision'}

def install_catalog(ui):
    avatars=[c.avatar for c in ui.original_catalog.characters.values()]
    for cid,p in ui.bots.items():
        ui.catalog.characters[cid]=Character(cid,p['name'],'bot.'+cid[-8:],avatars[p['avatar']],p['bio'],[],ui.t('개인 봇'),followers=0,following=0,greeting=ui.t('편하게 말을 걸어 주세요.'))
        ui.state.conversations.setdefault(cid,Conversation(cid));ui.notes[cid]=ui.t('개인 봇')

def restore_private(ui,data):
    values=data.get('bots',{})
    if isinstance(values,dict):
        for cid,value in list(values.items())[:bots.MAX_BOTS]:
            try:
                item=bots.restore_bot(value)
                if item['id']==cid:ui.bots[cid]=item
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError):pass
    if data.get('bot_draft'):
        try:ui.bot_draft=bots.restore_bot(data['bot_draft'],complete=False)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):pass
    install_catalog(ui)

def handle(ui,kind,p,cid):
    if kind not in ACTIONS:return False
    if kind!='bot_import_path':ui.modal=None
    if kind=='bot_library':ui.bot_field=None;ui.state.routes.append(Route('bots'))
    elif kind=='new_bot':
        if len(ui.bots)>=bots.MAX_BOTS and not(ui.bot_draft and ui.bot_draft['id'] in ui.bots):ui.say('개인 봇은 8개까지 만들 수 있어요. 자료나 기록을 정리해 주세요.');return True
        if not ui.bot_draft:ui.bot_draft=bots.new_draft()
        ui.bot_field='name';ui.state.routes.append(Route('bot_editor',ui.bot_draft['id']))
    elif kind=='edit_bot' and cid in ui.bots:ui.bot_draft=deepcopy(ui.bots[cid]);ui.bot_field='name';ui.state.routes.append(Route('bot_editor',cid))
    elif kind=='bot_field':ui.bot_field=p['field'] if p['field'] in bots.FIELDS else None
    elif kind=='bot_avatar' and ui.bot_draft:ui.bot_draft['avatar']=int(p['avatar'])%3
    elif kind=='bot_import_file':
        if ui.on_import:ui.on_import()
    elif kind=='bot_import_path':
        if ui.on_import:ui.on_import(ui.edit_value)
    elif kind=='clear_draft_docs' and ui.bot_draft:ui.bot_draft['documents']=[]
    elif kind=='bot_import' and ui.bot_draft:
        try:
            doc=bots.read_document(p['name'],p['text'].encode('utf-8'))
            if len(ui.bot_draft['documents'])>=3:raise ValueError('자료는 봇마다 3개까지 보관해요.')
            candidate=deepcopy(ui.bot_draft);candidate['documents'].append(doc)
            bots.check_budget(ui.bots,candidate);ui.bot_draft=candidate;ui.bot_field='personality';ui.state.route.scroll=370
            ui.say('파일을 가져왔어요. 대화에 사용할 성격 요약을 검토해 주세요.')
        except (ValueError,KeyError,TypeError) as exc:ui.say(str(exc))
    elif kind=='save_bot' and ui.bot_draft:
        try:
            key=ui.bot_draft['id'];old=ui.bots.get(key);profile=bots.save_profile(ui.bot_draft,old);updated={**ui.bots,key:profile};bots.check_budget(updated)
            ui.bots=updated
            if ui.on_change and ui.on_change() is False:
                if old:ui.bots[key]=old
                else:ui.bots.pop(key,None)
                ui.say('저장하지 못했어요. 초안은 유지했어요.');return True
            install_catalog(ui);ui.bot_draft=None;ui.bot_field=None;ui.state.routes=[Route('inbox'),Route('bots'),Route('profile',key)];ui.say('개인 봇을 저장했어요.')
        except (ValueError,KeyError,TypeError) as exc:ui.say(str(exc))
    elif kind=='confirm_bot_delete' and cid in ui.bots:ui.modal={'kind':'delete_bot','character_id':cid}
    elif kind=='delete_bot' and cid in ui.bots:
        profile=ui.bots.pop(cid);character=ui.catalog.characters.pop(cid);conv=ui.state.conversations.pop(cid)
        aliases=ui.state.aliases.copy();tones=ui.tones.copy();notes=ui.notes.copy();draft=ui.bot_draft
        ui.state.aliases.pop(cid,None);ui.tones.pop(cid,None);ui.notes.pop(cid,None)
        if draft and draft['id']==cid:ui.bot_draft=None
        if ui.on_change and ui.on_change() is False:
            ui.bots[cid]=profile;ui.catalog.characters[cid]=character;ui.state.conversations[cid]=conv
            ui.state.aliases=aliases;ui.tones=tones;ui.notes=notes;ui.bot_draft=draft;ui.say('삭제를 저장하지 못했어요. 다시 시도해 주세요.');return True
        ui.transport.reset(cid,conv.epoch+1);ui.following.discard(cid);ui.state.notifications[:]=[n for n in ui.state.notifications if n['conversation_id']!=cid]
        ui.bot_field=None;ui.state.active_conversation_id=None;ui.state.routes=[Route('inbox'),Route('bots')];ui.say('봇과 개인 자료·기록을 삭제했어요.')
    elif kind=='bot_history' and cid in ui.bots:ui.bot_field=None;ui.state.routes.append(Route('bot_history',cid))
    elif kind=='bot_source' and cid in ui.bots:ui.state.routes.append(Route('bot_source',cid,page=int(p['index'])))
    elif kind=='clear_bot_records' and cid in ui.bots:
        old=deepcopy(ui.bots[cid]);draft=deepcopy(ui.bot_draft);ui.bots[cid]['documents']=[];ui.bots[cid]['history']=[]
        if ui.bot_draft and ui.bot_draft['id']==cid:ui.bot_draft['documents']=[]
        if ui.on_change and ui.on_change() is False:ui.bots[cid]=old;ui.bot_draft=draft;ui.say('삭제를 저장하지 못했어요. 다시 시도해 주세요.');return True
        ui.say('원본 자료와 수정 기록을 지웠어요. 현재 성격 설정은 유지돼요.')
    elif kind=='restore_bot_revision' and cid in ui.bots:
        revision=ui.bots[cid]['history'][int(p['index'])];ui.bot_draft=deepcopy(ui.bots[cid]);ui.bot_draft.update({key:revision[key] for key in (*bots.FIELDS,'avatar')})
        ui.bot_field='personality';ui.state.routes.append(Route('bot_editor',cid))
    return True
