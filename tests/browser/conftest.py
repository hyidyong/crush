"""Browser plugin unavailable; use the installed Chromium through Playwright."""
import os
import shutil
from pathlib import Path

import pytest_asyncio
from playwright.async_api import async_playwright

BASE_URL=os.getenv('UNSENT_TEST_URL','http://127.0.0.1:8765').rstrip('/')
EVIDENCE=Path(os.getenv('UNSENT_QA_DIR','/tmp/unsent-browser-qa'))


class Screen:
    def __init__(self,page):
        self.page=page
        self.errors=[]
        self.console=[]
        page.on('pageerror',lambda error:self.errors.append(str(error)))
        page.on('console',lambda message:self.console.append(message.text) if message.type=='error' else None)
        page.on('console',lambda message:self.errors.append('Python runtime traceback') if 'Traceback (most recent call last)' in message.text else None)

    async def load(self):
        await self.page.goto(BASE_URL)
        await self.wait('window.unsentState?.screen === "inbox"',timeout=60000)
        assert (await self.page.title()).startswith('Unsent')
        canvas=await self.page.locator('#canvas').bounding_box()
        assert canvas and canvas['width']>300 and canvas['height']>500
        assert len((await self.state())['conversations'])>=3

    async def wait(self,expression,*,timeout=15000,arg=None):
        return await self.page.wait_for_function(expression,arg=arg,timeout=timeout)

    async def state(self):return await self.page.evaluate('window.unsentState')

    async def tap(self,x,y):
        canvas=await self.page.locator('#canvas').bounding_box()
        assert canvas
        await self.page.mouse.click(canvas['x']+x*canvas['width']/414,canvas['y']+y*canvas['height']/896)

    async def screenshot(self,name):
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        path=EVIDENCE/name
        await self.page.screenshot(path=str(path))
        assert path.stat().st_size>4000
        return path

    async def inbox(self):
        for _ in range(8):
            state=await self.state()
            if state['screen']=='inbox' and not state.get('modal'):return
            previous={'screen':state['screen'],'modal':state.get('modal')}
            await self.tap(22,72)
            await self.wait('previous => {const state=window.unsentState;return state && JSON.stringify({screen:state.screen,modal:state.modal ?? null}) !== JSON.stringify(previous)}',arg=previous)
        assert (await self.state())['screen']=='inbox'

    async def library(self):
        await self.inbox()
        await self.tap(385,72)
        await self.wait('window.unsentState.modal?.kind === "contacts"')
        await self.tap(180,850)
        await self.wait('window.unsentState.screen === "bots"')

    async def new_bot(self,name):
        await self.library()
        await self.tap(150,213)
        await self.wait('window.unsentState.screen === "bot_editor"')
        await self.page.get_by_role('textbox',name='이름',exact=True).fill(name)

    async def personality(self,text):
        await self.tap(100,520)
        field=self.page.get_by_role('textbox',name='성격·말투',exact=True)
        await field.wait_for(state='visible')
        await field.fill(text)
        return field

    async def save_bot(self):
        await self.tap(170,850)
        await self.wait('window.unsentState.screen === "profile"')
        return (await self.state())['private_bots'][-1]['id']

    async def settings(self):
        await self.tap(375,841)
        await self.wait('window.unsentState.screen === "settings"')


@pytest_asyncio.fixture
async def browser():
    async with async_playwright() as p:
        binary=os.getenv('UNSENT_CHROMIUM') or shutil.which('chromium') or shutil.which('chromium-browser')
        instance=await p.chromium.launch(executable_path=binary,headless=True,args=['--no-sandbox'])
        yield instance
        await instance.close()


@pytest_asyncio.fixture
async def screen(browser):
    context=await browser.new_context(viewport={'width':414,'height':896})
    value=Screen(await context.new_page())
    await value.load()
    yield value
    await context.close()
