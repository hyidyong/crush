from unsent.domain.state import open_thread, queue_message


def rename_character(state, character_id, display_name):
    name = display_name.strip()
    if not 1 <= len(name) <= 32:
        raise ValueError('별명은 1~32자로 적어 주세요.')
    if character_id not in state.conversations:
        raise KeyError(character_id)
    state.aliases[character_id] = name


def share_post(state, conversation_id, post_id, text='이 게시물 봤어?'):
    request = queue_message(state, conversation_id, text)
    request.shared_post_id = post_id
    state.conversations[conversation_id].messages[-1].shared_post_id = post_id
    return request


def navigate_back(state):
    if len(state.routes) > 1:
        state.routes.pop()
    if state.route.screen == 'thread':
        open_thread(state, state.route.character_id, state.screen_visible)


def carousel_page(current, delta, count):
    return max(0, min(count - 1, current + delta))
