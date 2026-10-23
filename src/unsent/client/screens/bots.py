"""Private bot authoring screens; source material stays in the local UI state."""

import pygame

from unsent.client.screens.common import back
from unsent.client.theme import THEME as T
from unsent.shared.bots import FIELDS


InputRect = tuple[float, float, float, float]
LABELS = {
    'name': '이름',
    'bio': '소개',
    'personality': '성격·말투',
    'examples': '대화 예시',
}
FIELD_RECTS = {
    'name': (288, 48),
    'bio': (379, 64),
    'personality': (488, 148),
    'examples': (682, 126),
}


def clipped(c, rect, top=102, bottom=None):
    """Clip logical hit/input bounds to the scrolling body, not the footer."""
    x, y, width, height = rect
    bottom = c.height - 92 if bottom is None else bottom
    start, end = max(y, top), min(y + height, bottom)
    return (x, start, width, end - start) if end > start else None


def body_button(c, label, rect, action, **payload):
    hit = clipped(c, rect)
    if hit:
        c.button(label, rect, action, **payload)
        _, kind, values = c.hits[-1]
        c.hits[-1] = (pygame.Rect(hit), kind, values)


def begin(c):
    previous = c.surface.get_clip()
    c.surface.set_clip((0, 102 * c.scale, c.width * c.scale,
                        (c.height - 194) * c.scale))
    return previous


def _scroll(ui, maximum):
    ui.state.route.scroll = max(0, min(ui.state.route.scroll, maximum))
    return ui.state.route.scroll


def library(c, ui):
    sy = _scroll(ui, max(0, 250 + len(ui.bots) * 94 - (c.height - 92)))
    previous = begin(c)
    c.text(ui.t('나만의 대화 상대'), 20, 118 - sy, 20, bold=True)
    c.text(ui.t('원본 자료와 설정은 내 기기에만 보관해요.'), 20, 154 - sy,
           12, T.muted, width=c.width - 40, line_height=19)
    body_button(c, ui.t('초안 계속하기' if ui.bot_draft else '새 봇 만들기'),
                (20, 193 - sy, c.width - 40, 40), 'new_bot', accent=True)
    if not ui.bots:
        c.text(ui.t('이름과 성격을 정해 첫 봇을 만들어 보세요.'),
               20, 280 - sy, 15, T.muted, width=c.width - 40)
    for index, (cid, profile) in enumerate(ui.bots.items()):
        y = 254 + index * 94 - sy
        if not clipped(c, (0, y, c.width, 90)):
            continue
        c.image(ui.catalog.characters[cid].avatar, (20, y + 9, 48, 48), True)
        c.text(profile['name'], 80, y + 9, 16, bold=True,
               width=c.width - 180, max_lines=1)
        c.text(ui.t('개인 봇 · 수정 {count}회', count=profile['revision']),
               80, y + 37, 11, T.muted)
        hit = clipped(c, (10, y, c.width - 20, 80))
        if hit:
            c.hit(hit, 'profile', character_id=cid)
        body_button(c, ui.t('설정 편집'), (c.width - 107, y + 15, 87, 35),
                    'edit_bot', character_id=cid)
    c.surface.set_clip(previous)
    back(c, ui.t('내 봇'))
    c.tabbar(ui.catalog)
    return None


def editor(c, ui) -> InputRect | None:
    if not ui.bot_draft:
        return library(c, ui)
    draft = ui.bot_draft
    sy = _scroll(ui, max(0, 1135 - (c.height - 92)))
    previous = begin(c)
    input_rect = None
    c.text(ui.t('내 기기에 저장되는 개인 AI 프로필'), 20, 117 - sy,
           16, bold=True, width=c.width - 40)
    c.text(ui.t('직접 쓴 설명과 예시를 매 대화에 참고해요.'),
           20, 147 - sy, 12, T.muted, width=c.width - 40)
    avatars = [character.avatar for character in ui.original_catalog.characters.values()]
    for index, avatar in enumerate(avatars[:3]):
        x, y = 20 + index * 80, 188 - sy
        c.rect((x - 3, y - 3, 62, 62),
               T.accent if index == draft['avatar'] else T.border, 31, 2)
        c.image(avatar, (x, y, 56, 56), True)
        hit = clipped(c, (x - 4, y - 4, 64, 64))
        if hit:
            c.hit(hit, 'bot_avatar', avatar=index)
    for field, (y, height) in FIELD_RECTS.items():
        y -= sy
        value = draft[field]
        c.text(ui.t(LABELS[field]) + f'  {len(value)}/{FIELDS[field]}',
               20, y - 24, 12, T.muted)
        c.rect((20, y, c.width - 40, height), T.elevated, 10)
        hit = clipped(c, (20, y, c.width - 40, height))
        if hit:
            c.hit(hit, 'bot_field', field=field)
            active = field == ui.bot_field
            if not (active and getattr(ui, 'web', False)):
                c.text(value or ui.t('눌러서 입력'), 32, y + 12, 14,
                       T.text if value else T.muted, width=c.width - 64,
                       line_height=21, max_lines=max(1, (height - 20) // 21))
            if active:
                input_rect = clipped(c, (32, y + 10, c.width - 64, height - 20))
    body_button(c, ui.t('텍스트 파일 가져오기'),
                (20, 833 - sy, c.width - 40, 42), 'bot_import_file')
    c.text(ui.t('TXT·MD / UTF-8 / 64KB·12,000자 / 원본 3개'),
           20, 889 - sy, 11, T.muted, width=c.width - 40, line_height=18)
    c.text(ui.t('대화에는 편집한 성격 1,400자와 예시 600자만 사용해요.'),
           20, 929 - sy, 11, T.muted, width=c.width - 40, line_height=18)
    c.text(ui.t('개인 자료 {count}개', count=len(draft['documents'])),
           20, 979 - sy, 13)
    if draft['documents']:
        body_button(c, ui.t('초안의 원본 자료 지우기'),
                    (20, 1007 - sy, c.width - 40, 36), 'clear_draft_docs')
    c.text(ui.t('실제 당사자가 아닌 AI예요. 선택한 AI 서버가 대화 설정을 처리해요. 외부 전송을 피하려면 로컬 모델을 사용하세요.'),
           20, 1060 - sy, 11, T.muted, width=c.width - 40, line_height=18)
    c.surface.set_clip(previous)
    back(c, ui.t('봇 프로필 만들기'))
    c.rect((0, c.height - 87, c.width, 87), T.background)
    c.button(ui.t('프로필 저장'), (20, c.height - 69, c.width - 40, 42),
             'save_bot', accent=True)
    return input_rect


def history(c, ui):
    route = ui.state.route
    profile = ui.bots[route.character_id]
    total_height = 280 + len(profile['documents']) * 78 + len(profile['history']) * 94
    sy = _scroll(ui, max(0, total_height - (c.height - 92)))
    previous = begin(c)
    c.text(ui.t('이 기기에만 남는 작성 기록'), 20, 122 - sy, 18, bold=True)
    c.text(ui.t('원본 파일과 수정 기록은 AI 서버에 보내지 않아요.'),
           20, 158 - sy, 12, T.muted, width=c.width - 40)
    body_button(c, ui.t('원본·수정 기록 지우기'),
                (20, 199 - sy, c.width - 40, 38), 'clear_bot_records',
                character_id=route.character_id)
    y = 265 - sy
    for index, document in enumerate(profile['documents']):
        c.text(document['name'], 20, y, 15, bold=True,
               width=c.width - 40, max_lines=1)
        c.text(ui.t('원본 {count}자 · 눌러서 보기', count=len(document['text'])),
               20, y + 29, 12, T.muted)
        hit = clipped(c, (12, y - 6, c.width - 24, 69))
        if hit:
            c.hit(hit, 'bot_source', character_id=route.character_id, index=index)
        y += 78
    for index, revision in enumerate(profile['history']):
        c.text(ui.t('수정 기록 {count}', count=revision['revision']) + ' · ' + revision['name'],
               20, y, 14, bold=True, width=c.width - 40, max_lines=1)
        c.text(revision['personality'], 20, y + 27, 12, T.muted,
               width=c.width - 40, max_lines=1)
        c.text(ui.t('눌러서 편집 초안으로 복원'), 20, y + 51, 11, T.accent)
        hit = clipped(c, (12, y - 5, c.width - 24, 85))
        if hit:
            c.hit(hit, 'restore_bot_revision', character_id=route.character_id, index=index)
        y += 94
    c.surface.set_clip(previous)
    back(c, ui.t('개인 자료·수정 기록'))
    c.tabbar(ui.catalog)
    return None


def source(c, ui):
    route = ui.state.route
    document = ui.bots[route.character_id]['documents'][route.page]
    lines = c.type.lines(document['text'], c.width - 40, 14)
    sy = _scroll(ui, max(0, len(lines) * 22 + 135 - (c.height - 92)))
    previous = begin(c)
    first = max(0, int((sy - 30) / 22))
    for index in range(first, min(len(lines), first + int(c.height / 22) + 2)):
        c.text(lines[index], 20, 125 + index * 22 - sy, 14,
               width=c.width - 40, max_lines=1)
    c.surface.set_clip(previous)
    back(c, document['name'])
    c.tabbar(ui.catalog)
    return None


def render(canvas, controller) -> InputRect | None:
    """Return the active editor's clipped logical textarea bounds, or None."""
    return {
        'bots': library,
        'bot_editor': editor,
        'bot_history': history,
        'bot_source': source,
    }[controller.state.route.screen](canvas, controller)
