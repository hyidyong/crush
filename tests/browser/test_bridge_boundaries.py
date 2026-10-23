"""Transport boundaries tested independently from model inference and WASM."""
import asyncio,json
import pytest
from .conftest import BASE_URL

pytestmark=pytest.mark.browser
HARNESS='''<!doctype html><html><head><title>Bridge verification</title></head><body>
<div id="phone"><canvas id="canvas"></canvas><textarea id="composer"></textarea><input id="bot-file-input" type="file"><div id="chatlog"></div><div id="loading"><span id="loading-message"></span><button id="retry" hidden>Retry</button></div></div>
<script src="/bridge.js"></script></body></html>'''

async def harness(context):
    page=await context.new_page()
    await page.route('**/bridge-verification',lambda route:route.fulfill(status=200,content_type='text/html',body=HARNESS))
    await page.goto(BASE_URL+'/bridge-verification')
    await page.wait_for_function('window.unsentBridge?.isReady()')
    return page

async def test_truncated_successful_stream_becomes_retryable_error(browser):
    context=await browser.new_context()
    try:
        page=await harness(context)
        request={'session_id':'bridge-test','conversation_id':'rio','epoch':0,'client_message_id':'truncated','text':'Synthetic transport check'}
        base={'conversation_id':'rio','epoch':0,'request_id':'test','message_id':'truncated'}
        body=''.join('data: '+json.dumps(dict(base,kind=kind,payload=payload))+'\n\n' for kind,payload in [('accepted',{}),('typing',{'active':True})])
        await page.route('**/api/chat',lambda route:route.fulfill(status=200,content_type='text/event-stream',body=body))
        await page.evaluate('raw=>{window.captured=[];setInterval(()=>window.captured.push(...JSON.parse(window.unsentBridge.drainEvents())),10);window.unsentBridge.startChat(raw)}',json.dumps(request))
        await page.wait_for_function('window.captured.some(event=>event.kind === "error")')
        events=await page.evaluate('window.captured')
        assert [event['kind'] for event in events][:2]==['accepted','typing']
        assert next(event for event in events if event['kind']=='error')['message_id']=='truncated'
    finally:await context.close()

@pytest.mark.parametrize('fallback',[False,True])
async def test_fresh_session_blocks_concurrent_old_namespace_writes(browser,fallback):
    context=await browser.new_context()
    if fallback:await context.add_init_script("Object.defineProperty(navigator,'locks',{value:undefined})")
    try:
        one,two=await asyncio.gather(harness(context),harness(context))
        await two.evaluate("window.unsentBridge.store(JSON.stringify({marker:'SYNTHETIC-OLD-PRIVATE'}));window.writer=setInterval(()=>window.unsentBridge.store(JSON.stringify({marker:'SYNTHETIC-OLD-PRIVATE'})),0)")
        await one.evaluate("window.originalRemove=Storage.prototype.removeItem;Storage.prototype.removeItem=function(key){const result=window.originalRemove.call(this,key);if(key.startsWith('unsent-device:')){const until=performance.now()+150;while(performance.now()<until){}}return result};void window.unsentBridge.freshSession()")
        await one.wait_for_function('window.unsentBridge?.isReady() && !JSON.stringify(localStorage).includes("SYNTHETIC-OLD-PRIVATE")')
        await two.wait_for_function('window.unsentBridge?.isReady() && !JSON.stringify(localStorage).includes("SYNTHETIC-OLD-PRIVATE")')
        assert await one.evaluate('window.unsentBridge.load()')==''
        assert await two.evaluate('window.unsentBridge.load()')==''
    finally:await context.close()
