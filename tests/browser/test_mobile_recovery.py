import asyncio
import json
import uuid

import pytest
from .conftest import Screen

pytestmark=pytest.mark.browser


def sse(request,text='짧은 테스트 답장이야.'):
    rid=uuid.uuid4().hex
    base=dict(conversation_id=request['conversation_id'],epoch=request['epoch'],request_id=rid,message_id=request['client_message_id'])
    events=[dict(base,kind='accepted',payload={}),dict(base,kind='seen',payload={}),
            dict(base,kind='typing',payload={'active':True}),
            dict(base,kind='bubble',message_id=rid+'.0',payload={'text':text}),
            dict(base,kind='typing',payload={'active':False}),dict(base,kind='done',payload={})]
    return ''.join('data: '+json.dumps(event,ensure_ascii=False)+'\n\n' for event in events)


async def test_ime_enter_multiline_and_room_drafts(screen):
    page=screen.page;requests=[];submitted=asyncio.Event()
    async def chat(route):
        requests.append(route.request.post_data_json);submitted.set()
        await route.fulfill(status=503,body='intentional offline fixture')
    await page.route('**/api/chat',chat)
    await screen.tap(150,397)
    await screen.wait('window.unsentState.screen === "thread"')
    field=page.get_by_role('textbox',name='메시지',exact=True)
    await field.focus()
    await field.dispatch_event('compositionstart')
    await field.fill('안녕')
    await field.dispatch_event('keydown',{'key':'Enter','isComposing':True,'keyCode':229})
    assert requests==[]
    await field.dispatch_event('compositionend',{'data':'안녕'})
    await screen.wait('window.unsentState.conversations.rio.draft === "안녕"')
    # A key event after composition is a new user action rather than IME confirmation.
    await field.press('Shift+Enter')
    await field.type('둘째 줄')
    assert await field.input_value()=='안녕\n둘째 줄'
    await field.press('Enter')
    await asyncio.wait_for(submitted.wait(),5)
    assert len(requests)==1 and requests[0]['text']=='안녕\n둘째 줄'
    await screen.wait('window.unsentState.conversations.rio.messages.some(m=>m.sender === "user" && m.status === "failed")')
    await field.press('Enter')
    await field.fill('남겨 둔 초안')
    await screen.wait('window.unsentState.conversations.rio.draft === "남겨 둔 초안"')
    await screen.tap(22,72)
    await screen.tap(150,473)
    await screen.wait('window.unsentState.character_id === "jiwoo"')
    assert await field.input_value()==''
    assert (await screen.state())['conversations']['rio']['draft']=='남겨 둔 초안'
    assert len(requests)==1
    assert not screen.errors


async def test_pending_room_reply_updates_unread_then_profile_and_post(screen):
    page=screen.page;started=asyncio.Event();release=asyncio.Event();requests=[]
    async def chat(route):
        data=route.request.post_data_json;requests.append(data);started.set()
        await release.wait()
        await route.fulfill(status=200,content_type='text/event-stream',body=sse(data))
    await page.route('**/api/chat',chat)
    try:
        await screen.tap(150,397)
        field=page.get_by_role('textbox',name='메시지',exact=True)
        await field.fill('대화 동작을 확인해 보자')
        await field.press('Enter');await asyncio.wait_for(started.wait(),5)
        await screen.tap(22,72);await screen.tap(150,473)
        await screen.wait('window.unsentState.character_id === "jiwoo"')
        release.set()
        await screen.wait('window.unsentState.conversations.rio.unread > 0')
        assert (await screen.state())['character_id']=='jiwoo'
        await screen.inbox();await screen.tap(150,397)
        await screen.wait('window.unsentState.character_id === "rio"')
        state=await screen.state()
        assert state['conversations']['rio']['unread']==0
        assert next(m for m in state['conversations']['rio']['messages'] if m['sender']=='user')['status']=='seen'
        await screen.screenshot('mobile-thread.png')
        await screen.tap(150,70);await screen.wait('window.unsentState.screen === "profile"')
        await screen.screenshot('mobile-profile.png')
        await screen.tap(60,610);await screen.wait('window.unsentState.screen === "post"')
        await screen.screenshot('mobile-post.png')
        canvas=await page.locator('#canvas').bounding_box()
        await page.mouse.move(canvas['x']+330*canvas['width']/414,canvas['y']+260*canvas['height']/896)
        await page.mouse.down();await page.mouse.move(canvas['x']+70*canvas['width']/414,canvas['y']+260*canvas['height']/896,steps=8);await page.mouse.up()
        await screen.wait('window.unsentState.page === 1')
        assert len(requests)==1 and not screen.errors
    finally:release.set()


@pytest.mark.parametrize('width,height',[(390,844),(430,932)])
async def test_mobile_first_viewport_is_rendered_without_runtime_error(browser,width,height):
    context=await browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
    screen=Screen(await context.new_page())
    try:
        await screen.load();await screen.screenshot(f'inbox-{width}.png')
        await screen.tap(150,397);await screen.wait('window.unsentState.screen === "thread"')
        assert await screen.page.get_by_role('textbox',name='메시지',exact=True).is_visible()
        assert not screen.errors
    finally:await context.close()
