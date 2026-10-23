import asyncio
import json
import uuid
import pytest
from .conftest import Screen,BASE_URL
from .test_mobile_recovery import sse

pytestmark=pytest.mark.browser


async def test_private_file_and_bot_survive_reload_but_not_delete_or_fresh_session(browser):
    a=await browser.new_context(viewport={'width':414,'height':896})
    b=await browser.new_context(viewport={'width':414,'height':896})
    screen=Screen(await a.new_page());other=Screen(await b.new_page())
    requests=[];posted=[];submitted=asyncio.Event()
    async def chat(route):
        data=route.request.post_data_json;requests.append(data);submitted.set()
        await route.fulfill(status=200,content_type='text/event-stream',body=sse(data))
    await screen.page.route('**/api/chat',chat)
    screen.page.on('request',lambda req:posted.append(req.post_data or '') if req.method=='POST' else None)
    try:
        await screen.load();await other.load()
        name='Demo-'+uuid.uuid4().hex[:10];secret='raw-'+uuid.uuid4().hex
        await screen.new_bot(name)
        await screen.page.mouse.wheel(0,500)
        picker=screen.page.locator('#bot-file-input')
        await picker.wait_for(state='visible')
        async with screen.page.expect_file_chooser() as chooser:
            await picker.click()
        await (await chooser.value).set_files({'name':'private-notes.txt','mimeType':'text/plain',
            'buffer':('Calm and observant.\n'+'Private reference. '*150+secret).encode()})
        personality=screen.page.get_by_role('textbox',name='성격·말투',exact=True)
        await personality.wait_for(state='visible')
        await personality.fill('차분하고 짧게 말하는 친구. 가끔 다정한 농담을 해.')
        await personality.press('Enter');await personality.type('내 말을 잘 들어줘.')
        assert '\n' in await personality.input_value()
        assert not requests and not any(secret in body for body in posted)
        await screen.screenshot('private-editor.png')
        cid=await screen.save_bot()
        assert secret not in json.dumps(await screen.state())
        await screen.tap(300,352);await screen.wait('window.unsentState.screen === "thread"')
        await screen.page.get_by_role('textbox',name='메시지',exact=True).fill('오늘 어땠어?')
        await screen.page.get_by_role('textbox',name='메시지',exact=True).press('Enter')
        await asyncio.wait_for(submitted.wait(),5)
        await screen.wait('window.unsentState.conversations[window.unsentState.character_id].messages.some(m=>m.sender === "agent")')
        assert set(requests[0]['custom_persona'])=={'name','bio','personality','examples'}
        assert secret not in json.dumps(requests) and 'private-notes.txt' not in json.dumps(requests)
        assert (await other.state())['private_bots']==[]
        assert secret not in await other.page.evaluate('JSON.stringify(localStorage)')
        assert name not in await other.page.evaluate('JSON.stringify(localStorage)')
        assert secret in await screen.page.evaluate('window.unsentBridge.load()')
        catalog=await a.request.get(BASE_URL+'/api/catalog')
        assert catalog.status==200
        assert name not in await catalog.text()
        await screen.page.reload();await screen.wait('window.unsentState?.screen === "inbox"',timeout=60000)
        assert (await screen.state())['private_bots'][0]['id']==cid
        await screen.library();await screen.tap(100,279)
        await screen.wait('window.unsentState.screen === "profile"')
        await screen.tap(100,351);await screen.wait('window.unsentState.screen === "bot_editor"')
        await screen.page.get_by_role('textbox',name='이름',exact=True).fill(name+' edited')
        await screen.save_bot()
        assert (await screen.state())['private_bots'][0]['revision']==2
        await screen.tap(385,72);await screen.wait('window.unsentState.modal?.kind === "thread_menu"')
        await screen.tap(120,772);await screen.wait('window.unsentState.screen === "bot_history"')
        await screen.tap(100,284);await screen.wait('window.unsentState.screen === "bot_source"')
        assert secret not in json.dumps(await screen.state())
        await screen.tap(22,72);await screen.tap(22,72)
        await screen.wait('window.unsentState.screen === "profile"')
        await screen.tap(385,72);await screen.wait('window.unsentState.modal?.kind === "thread_menu"')
        await screen.tap(100,842);await screen.wait('window.unsentState.modal?.kind === "delete_bot"')
        await screen.tap(180,751);await screen.wait('window.unsentState.private_bots.length === 0')
        assert secret not in await screen.page.evaluate('window.unsentBridge.load()')
        await screen.page.reload();await screen.wait('window.unsentState?.screen === "inbox"',timeout=60000)
        assert (await screen.state())['private_bots']==[]
        await screen.new_bot('Another private demo');await screen.personality('다정하고 간결한 친구')
        await screen.save_bot()
        sibling=Screen(await a.new_page());await sibling.load()
        assert len((await sibling.state())['private_bots'])==1
        await screen.settings();await screen.tap(180,686)
        await screen.wait('window.unsentState.modal?.kind === "private_session"')
        await screen.tap(180,751)
        await screen.wait('window.unsentState?.screen === "inbox" && window.unsentState.private_bots.length === 0',timeout=60000)
        await sibling.wait('window.unsentState?.screen === "inbox" && window.unsentState.private_bots.length === 0',timeout=60000)
        assert 'Another private demo' not in await screen.page.evaluate('JSON.stringify(localStorage)')
        assert (await other.state())['private_bots']==[]
        assert not screen.errors and not other.errors
    finally:await a.close();await b.close()


async def test_quota_failure_keeps_draft_and_reports_no_saved_bot(screen):
    await screen.new_bot('Unsaved demo');await screen.personality('차분하고 간결한 친구')
    await screen.page.evaluate("window.failedBotWrites=0;window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key.startsWith('unsent-device:')){if(Object.keys(JSON.parse(value).bots||{}).length)window.failedBotWrites++;throw new DOMException('Full','QuotaExceededError')}return window.originalSetItem.call(this,key,value)};void 0")
    try:
        await screen.tap(170,850)
        await screen.wait('window.failedBotWrites > 0')
        await screen.wait('window.unsentState.screen === "bot_editor" && window.unsentState.has_bot_draft')
        assert (await screen.state())['private_bots']==[]
        assert await screen.page.get_by_role('textbox',name='성격·말투',exact=True).input_value()=='차분하고 간결한 친구'
    finally:await screen.page.evaluate('Storage.prototype.setItem=window.originalSetItem;void 0')
    await screen.save_bot()
    assert (await screen.state())['private_bots'][0]['name']=='Unsaved demo'
