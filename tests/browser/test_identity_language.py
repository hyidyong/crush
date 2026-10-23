import asyncio
import json
import re
import pytest
from .conftest import Screen,BASE_URL
from .test_mobile_recovery import sse

pytestmark=pytest.mark.browser


async def test_english_setting_persists_and_drives_custom_reply_request(screen):
    sent=[];submitted=asyncio.Event()
    async def chat(route):
        data=route.request.post_data_json;sent.append(data);submitted.set()
        await route.fulfill(status=200,content_type='text/event-stream',body=sse(data,'Hey, how was your day?'))
    await screen.page.route('**/api/chat',chat)
    await screen.new_bot('My private demo');await screen.personality('관찰력이 좋고 다정한 친구')
    cid=await screen.save_bot()
    await screen.settings();await screen.tap(300,585)
    await screen.wait('window.unsentState.language === "en"')
    assert await screen.page.locator('html').get_attribute('lang')=='en'
    assert any(bot['id']==cid for bot in (await screen.state())['private_bots'])
    await screen.tap(22,72);await screen.wait('window.unsentState.screen === "profile"')
    await screen.screenshot('english-private-profile.png')
    await screen.tap(300,352);await screen.wait('window.unsentState.screen === "thread"')
    field=screen.page.get_by_role('textbox',name='Message',exact=True)
    await field.fill('안녕, 오늘 뭐 했어?');await field.press('Enter')
    await asyncio.wait_for(submitted.wait(),5)
    await screen.wait('window.unsentState.conversations[window.unsentState.character_id].messages.some(m=>m.sender === "agent")')
    assert sent[0]['language']=='en'
    assert sent[0]['custom_persona']['personality']=='관찰력이 좋고 다정한 친구'
    assert sent[0]['conversation_id']==cid
    assert not re.search('[가-힣]',(await screen.state())['conversations'][cid]['messages'][-1]['text'])
    await screen.page.reload();await screen.wait('window.unsentState?.screen === "inbox"',timeout=60000)
    assert (await screen.state())['language']=='en'
    assert any(bot['id']==cid for bot in (await screen.state())['private_bots'])
    assert not screen.errors


async def test_bootstrap_failure_never_overwrites_saved_settings(screen):
    await screen.settings();await screen.tap(300,585);await screen.tap(350,418)
    await screen.wait('window.unsentState.language === "en"')
    await screen.wait('JSON.parse(window.unsentBridge.load()).save_history === true')
    before=await screen.page.evaluate('window.unsentBridge.load()')
    async def offline(route):await route.fulfill(status=503,body='intentional bootstrap failure')
    await screen.page.route('**/api/identity',offline)
    await screen.page.reload()
    retry=screen.page.get_by_role('button',name=re.compile('Retry|다시 시도')).first
    await retry.wait_for(state='visible',timeout=15000)
    assert await screen.page.evaluate('window.unsentState === undefined')
    assert before in await screen.page.evaluate('Object.values(localStorage)')
    await screen.page.unroute('**/api/identity',offline)
    await retry.click();await screen.wait('window.unsentState?.screen === "inbox"',timeout=60000)
    assert (await screen.state())['language']=='en'
    assert await screen.page.evaluate('JSON.parse(window.unsentBridge.load()).save_history') is True


@pytest.mark.parametrize('fallback',[False,True])
async def test_first_tabs_share_identity_and_fresh_session_clears_them(browser,fallback):
    context=await browser.new_context(viewport={'width':414,'height':896})
    if fallback:
        await context.add_init_script("Object.defineProperty(navigator,'locks',{value:undefined});Object.defineProperty(crypto,'randomUUID',{value:undefined})")
    active=0;maximum=0;scopes=[];first=asyncio.Event();release=asyncio.Event();count=0
    async def identity(route):
        nonlocal active,maximum,count
        active+=1;maximum=max(maximum,active);count+=1
        if count==1:
            first.set();await release.wait()
        response=await route.fetch()
        scopes.append((await response.json())['storage_scope'])
        await route.fulfill(response=response)
        active-=1
    await context.route('**/api/identity',identity)
    one=Screen(await context.new_page());two=Screen(await context.new_page())
    try:
        await asyncio.gather(one.page.goto(BASE_URL,wait_until='domcontentloaded'),two.page.goto(BASE_URL,wait_until='domcontentloaded'))
        await asyncio.wait_for(first.wait(),10)
        await asyncio.gather(one.page.wait_for_function('!!window.unsentBridge'),two.page.wait_for_function('!!window.unsentBridge'))
        release.set()
        await asyncio.gather(one.wait('window.unsentState?.screen === "inbox"',timeout=60000),two.wait('window.unsentState?.screen === "inbox"',timeout=60000))
        assert maximum==1 and len(scopes)>=2 and len(set(scopes))==1
        cookies=await context.cookies()
        identity_cookies=[cookie for cookie in cookies if cookie['name'].startswith('unsent_identity_')]
        assert identity_cookies and all(cookie['httpOnly'] for cookie in identity_cookies)
        assert 'unsent_identity_' not in await one.page.evaluate('document.cookie')
        await two.tap(150,397);await two.wait('window.unsentState.screen === "thread"')
        await one.settings();await one.tap(180,686)
        await one.wait('window.unsentState.modal?.kind === "private_session"')
        await one.tap(180,751)
        await asyncio.gather(one.wait('window.unsentState?.screen === "inbox"',timeout=60000),two.wait('window.unsentState?.screen === "inbox"',timeout=60000))
        assert not one.errors and not two.errors
    finally:release.set();await context.close()
