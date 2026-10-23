"""Behavioral recovery tests for isolated conversation state and private bot data."""
import json
from pathlib import Path
import unittest
import tempfile
from unsent.domain.state import AppState, Conversation, apply_event, open_thread, queue_message, reset_thread
from unsent.shared.contracts import ChatEvent
from unsent.shared import bots
from unsent.shared.catalog import load_catalog, asset_reference


def state():
    return AppState(conversations={'rio':Conversation('rio'),'jiwoo':Conversation('jiwoo')})


def test_pending_message_acknowledgement_seen_and_inflight():
    s=state();open_thread(s,'rio');request=queue_message(s,'rio','  hello  ')
    assert request.text=='hello'
    conv=s.conversations['rio']
    assert conv.messages[0].status=='pending' and request.client_message_id in conv.inflight
    apply_event(s,ChatEvent('accepted','rio',0,'r',request.client_message_id))
    apply_event(s,ChatEvent('seen','rio',0,'r',request.client_message_id))
    apply_event(s,ChatEvent('accepted','rio',0,'r',request.client_message_id))
    assert conv.messages[0].status=='seen'
    apply_event(s,ChatEvent('done','rio',0,'r',request.client_message_id))
    assert not conv.inflight


def test_room_visibility_drives_unread_and_duplicate_events_do_not_count_twice():
    s=state();open_thread(s,'jiwoo')
    event=ChatEvent('bubble','rio',0,'r','r.0',{'text':'Hey there'})
    apply_event(s,event);apply_event(s,event)
    assert len(s.conversations['rio'].messages)==1
    assert s.conversations['rio'].unread==1
    open_thread(s,'rio');assert s.conversations['rio'].unread==0
    s.focused=False
    apply_event(s,ChatEvent('bubble','rio',0,'r2','r2.0',{'text':'Still there?'}))
    assert s.conversations['rio'].unread==1


def test_reset_epoch_rejects_late_model_response_and_removes_private_draft():
    s=state();queue_message(s,'rio','old');s.conversations['rio'].draft='private draft'
    assert reset_thread(s,'rio')==1
    apply_event(s,ChatEvent('bubble','rio',0,'r','late',{'text':'late'}))
    assert s.conversations['rio'].messages==[] and s.conversations['rio'].draft==''


def test_private_import_revision_budget_and_active_card_boundary():
    draft=bots.new_draft();draft.update(name='Demo',personality='Quiet and observant')
    document=bots.read_document('/private/notes.md','성격을 설명하는 개인 자료'.encode('utf-8'))
    draft['documents']=[document]
    first=bots.save_profile(draft)
    assert document['name']=='notes.md'
    draft.update(name='Demo revised')
    second=bots.save_profile(draft,first)
    assert len(second['history'])==1 and second['revision']==2
    active=bots.active_card(second)
    assert set(active)=={'name','bio','personality','examples'}
    assert 'documents' not in active and 'history' not in active
    assert bots.restore_bot(second)['documents'][0]['text']==document['text']


def test_private_import_rejects_invalid_sources():
    for name,value in [('bad.exe',b'x'),('bad.txt',b'\xff'),('bad.txt',b'a\x00b'),('big.md',b'x'*65537),('long.txt',b'x'*12001)]:
        try:bots.read_document(name,value)
        except ValueError:pass
        else:raise AssertionError('Invalid file was accepted: '+name)


def test_reference_card_cannot_import_unknown_execution_fields():
    draft=bots.new_draft();draft.update(name='Demo',personality='Friendly',documents=[])
    restored=bots.restore_bot({**bots.save_profile(draft),'server_path':'/private','tools':['network']})
    assert 'server_path' not in restored and 'tools' not in restored


def test_nonfinite_saved_timestamps_are_not_allowed():
    draft=bots.new_draft();draft.update(name='Demo',personality='Friendly')
    saved=bots.save_profile(draft);saved['updated_at']=float('nan')
    try:bots.restore_bot(saved)
    except ValueError:pass
    else:raise AssertionError('NaN entered private JSON state')


def test_atlas_reference_is_bounded_and_catalog_paths_cannot_escape_assets():
    assert asset_reference('media/atlas.png#1,2,30,40')==('media/atlas.png',(1,2,30,40))
    for value in ['atlas.png#-1,2,3,4','atlas.png#0,0,0,4','atlas.png#0,0,3']:
        try:asset_reference(value)
        except ValueError:pass
        else:raise AssertionError('Invalid atlas region accepted')
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);asset=root/'assets';asset.mkdir()
        (root/'outside.png').write_bytes(b'not-an-image')
        (asset/'characters.json').write_text(json.dumps({'self_avatar':'../outside.png','characters':[],'posts':[]}))
        try:load_catalog(asset)
        except ValueError:pass
        else:raise AssertionError('Asset path escaped containment')


if __name__=='__main__':
    suite=unittest.TestSuite(unittest.FunctionTestCase(value) for name,value in list(globals().items()) if name.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
