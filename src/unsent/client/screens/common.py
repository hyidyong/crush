"""Shared mobile chrome and local interaction sheets."""
import time
import pygame

from unsent.client.theme import THEME


def statusbar(canvas):
    """Draw the compact iOS-style status area in logical screen coordinates."""
    canvas.text('9:41', 33, 11, 15, bold=True)
    for index, height in enumerate((4, 6, 9, 12)):
        canvas.rect((326 + index * 4, 27 - height, 3, height), THEME.text, 1)
    scale = canvas.scale
    for radius in (7, 11):
        pygame.draw.arc(canvas.surface, THEME.text,
                        pygame.Rect(round((355 - radius) * scale),
                                    round((21 - radius) * scale),
                                    round(radius * 2 * scale), round(radius * 2 * scale)),
                        .65, 2.5, max(1, round(1.7 * scale)))
    canvas.rect((354, 23, 3, 3), THEME.text, 2)
    canvas.rect((371, 12, 24, 13), THEME.muted, 3, 1)
    canvas.rect((373, 14, 18, 9), THEME.text, 2)
    canvas.rect((396, 16, 2, 5), THEME.muted, 1)


def header(canvas, title, subtitle=None, *, right='more', right_action='menu', back=True):
    canvas.rect((0, 43, canvas.width, 57), THEME.background)
    if back:
        canvas.icon('back', 12, 60, 25)
        canvas.hit((0, 45, 47, 54), 'back')
    canvas.text(title, 49, 53 if subtitle else 58, 18, bold=True,
                width=canvas.width - 98, align='center', max_lines=1)
    if subtitle:
        canvas.text(subtitle, 49, 78, 11, THEME.muted,
                    width=canvas.width - 98, align='center', max_lines=1)
    if right:
        canvas.icon(right, canvas.width - 42, 60, 23)
        canvas.hit((canvas.width - 55, 45, 55, 54), right_action)
    canvas.rect((0, 99, canvas.width, .5), THEME.border)


def home_indicator(canvas):
    canvas.rect((canvas.width / 2 - 73, canvas.height - 12, 146, 5), THEME.text, 3)


def back(canvas, title):
    header(canvas, title, right=None)


def notices(canvas, controller):
    """Show a temporary local toast or an incoming-room notification."""
    if controller.modal:
        return
    now = time.time()
    if controller.toast and controller.toast_until > now:
        canvas.rect((15, 748, canvas.width - 30, 61), THEME.elevated, 14)
        canvas.text(controller.toast, 29, 763, 13, width=canvas.width - 58, max_lines=2)
        return
    notifications = controller.state.notifications
    if not notifications:
        return
    notification = notifications[-1]
    cid = notification['conversation_id']
    if now - notification['at'] > 4 or cid not in controller.catalog.characters:
        return
    if controller.state.route.screen == 'thread' and controller.state.active_conversation_id == cid:
        return
    canvas.rect((10, 103, canvas.width - 20, 76), THEME.elevated, 15)
    canvas.image(controller.catalog.characters[cid].avatar, (23, 116, 46, 46), True)
    canvas.text(controller.name(cid), 82, 115, 13, bold=True, width=canvas.width - 105, max_lines=1)
    canvas.text(notification['text'], 82, 139, 12, THEME.muted, width=canvas.width - 105, max_lines=1)
    canvas.hit((10, 103, canvas.width - 20, 76), 'open_thread', character_id=cid)


def _row(canvas, controller, label, y, action, *, red=False, **payload):
    canvas.text(controller.t(label), 25, y + 8, 14,
                THEME.red if red else THEME.text, width=canvas.width - 50, max_lines=1)
    canvas.hit((12, y, canvas.width - 24, 35), action, **payload)


def _contacts(canvas, controller, modal, top, *, sharing=False):
    start, bottom = top + 68, 820
    maximum = max(0, len(controller.catalog.characters) * 70 - (bottom - start))
    scroll = max(0, min(float(modal.get('scroll', 0)), maximum))
    modal['scroll'] = scroll
    viewport = pygame.Rect(0, round(start * canvas.scale),
                           round(canvas.width * canvas.scale), round((bottom - start) * canvas.scale))
    previous = canvas.surface.get_clip()
    canvas.surface.set_clip(viewport)
    ordered = sorted(controller.catalog.characters,
                     key=lambda cid: max((message.created_at for message in controller.state.conversations[cid].messages), default=0),
                     reverse=True)
    for index, cid in enumerate(ordered):
        y = start + index * 70 - scroll
        if y + 70 <= start or y >= bottom:
            continue
        character = controller.catalog.characters[cid]
        canvas.image(character.avatar, (24, y + 10, 48, 48), True)
        canvas.text(controller.name(cid), 87, y + 12, 14, bold=True,
                    width=canvas.width - 110, max_lines=1)
        canvas.text(character.handle, 87, y + 37, 12, THEME.muted,
                    width=canvas.width - 110, max_lines=1)
        hit_top, hit_bottom = max(y, start), min(y + 70, bottom)
        payload = {'character_id': cid}
        if sharing:
            payload['post_id'] = modal['post_id']
        canvas.hit((12, hit_top, canvas.width - 24, hit_bottom - hit_top),
                   'share_post' if sharing else 'open_thread', **payload)
    canvas.surface.set_clip(previous)
    if not sharing:
        canvas.button(controller.t('내 봇 만들기·관리'), (20, 829, canvas.width - 40, 42), 'bot_library')


def render_modal(canvas, controller):
    """Draw the active bottom sheet and return its optional text-input rectangle."""
    modal = controller.modal
    if not modal:
        return None
    # A sheet is a complete interaction layer: clicks never reach content below it.
    canvas.hits.clear()
    shade = pygame.Surface(canvas.surface.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 155))
    canvas.surface.blit(shade, (0, 0))
    top = canvas.height - 370
    canvas.hit((0, 0, canvas.width, top), 'close_modal')
    canvas.rect((0, top, canvas.width, 370), THEME.elevated, 21)
    canvas.rect((canvas.width / 2 - 18, top + 9, 36, 4), THEME.muted, 2)
    canvas.icon('close', canvas.width - 40, top + 23, 20)
    canvas.hit((canvas.width - 52, top + 15, 46, 42), 'close_modal')
    kind = modal['kind']
    cid = modal.get('character_id') or controller.state.active_conversation_id or controller.state.route.character_id
    titles = {
        'contacts': '새 메시지', 'requests': '메시지 요청', 'thread_menu': '대화 설정',
        'rename': '별명 바꾸기', 'edit_note': '메모 수정', 'tone_menu': '대화 말투',
        'message_menu': '메시지', 'share': '메시지로 공유', 'note': '내 메모',
        'private_session': '새 비공개 세션', 'delete_bot': '봇 삭제',
        'import_path': '텍스트 파일 경로',
    }
    canvas.text(controller.t(titles.get(kind, '메시지')), 20, top + 30, 17,
                bold=True, width=canvas.width - 70, max_lines=1)
    if kind in ('contacts', 'share'):
        _contacts(canvas, controller, modal, top, sharing=kind == 'share')
    elif kind == 'requests':
        canvas.text(controller.t('새로운 요청이 없어요'), 24, top + 115, 14,
                    THEME.muted, width=canvas.width - 48, align='center')
    elif kind == 'thread_menu' and cid:
        for label, y, action in (
            ('프로필 보기', top + 64, 'profile'), ('별명 바꾸기', top + 99, 'rename'),
            ('대화 말투', top + 134, 'tone_menu'), ('대화 비우기', top + 169, 'reset'),
        ):
            _row(canvas, controller, label, y, action, character_id=cid)
        if cid in controller.bots:
            _row(canvas, controller, '봇 설정 편집', top + 204, 'edit_bot', character_id=cid)
            _row(canvas, controller, '개인 자료·수정 기록', top + 239, 'bot_history', character_id=cid)
            canvas.rect((20, top + 288, canvas.width - 40, .5), THEME.border)
            _row(canvas, controller, '봇 삭제', top + 298, 'confirm_bot_delete', red=True, character_id=cid)
    elif kind in ('rename', 'edit_note', 'import_path'):
        rect = (24, top + 95, canvas.width - 48, 58)
        canvas.rect(rect, THEME.surface, 10)
        if not getattr(controller, 'web', False):
            canvas.text(controller.edit_value, rect[0] + 12, rect[1] + 14, 14,
                        width=rect[2] - 24, max_lines=2)
        canvas.hit(rect, 'focus_edit')
        canvas.button(controller.t('가져오기' if kind == 'import_path' else '저장'),
                      (24, top + 183, canvas.width - 48, 42),
                      'bot_import_path' if kind == 'import_path' else 'save_edit', accent=True)
        return rect
    elif kind == 'tone_menu':
        for index, (label, tone) in enumerate((('편안하게', 'balanced'), ('장난스럽게', 'playful'), ('다정하게', 'warm'))):
            _row(canvas, controller, label, top + 85 + index * 55, 'set_tone', character_id=cid, tone=tone)
    elif kind == 'message_menu':
        for index, (label, action) in enumerate((('좋아요 ♡', 'react'), ('답장', 'quote'), ('텍스트 복사', 'copy'))):
            _row(canvas, controller, label, top + 85 + index * 55, action,
                 character_id=cid, message_id=modal['message_id'])
    elif kind == 'note':
        note_cid = modal.get('character_id', 'self')
        text = controller.notes.get(note_cid) or controller.t('메모가 없어요')
        canvas.text(text, 27, top + 100, 20, width=canvas.width - 54, align='center', max_lines=3)
        canvas.button(controller.t('메모 수정' if note_cid == 'self' else '메모에 답장'),
                      (24, top + 205, canvas.width - 48, 42),
                      'edit_note' if note_cid == 'self' else 'reply_note',
                      accent=True, character_id=note_cid)
    elif kind in ('private_session', 'delete_bot'):
        prompt = '새 세션 안내' if kind == 'private_session' else '봇과 원본 자료·수정 기록·대화를 이 기기에서 지울까요?'
        canvas.text(controller.t(prompt), 25, top + 93, 15,
                    width=canvas.width - 50, max_lines=4, align='center')
        canvas.button(controller.t('새로 시작' if kind == 'private_session' else '삭제'),
                      (24, top + 205, canvas.width - 48, 42),
                      'fresh_session' if kind == 'private_session' else 'delete_bot',
                      accent=True, character_id=cid)
        canvas.button(controller.t('취소'), (24, top + 263, canvas.width - 48, 42), 'close_modal')
    return None


render_statusbar = statusbar
render_header = header
render_notices = notices
