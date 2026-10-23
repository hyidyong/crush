"""Device-owned bot data. Only active_card() crosses the chat boundary."""
import json
import math
import re
import time
import uuid
from copy import deepcopy
from pathlib import PurePosixPath

MAX_BOTS = 8
FIELDS = {'name':32, 'bio':160, 'personality':1400, 'examples':600}


def is_bot_id(value):
    return isinstance(value, str) and re.fullmatch(r'custom_[0-9a-f]{32}', value) is not None


def timestamp(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid timestamp')
    return value


def read_document(name, raw):
    name = PurePosixPath(str(name).replace('\\', '/')).name[:120]
    if not name.lower().endswith(('.txt', '.md')) or len(raw) > 65536:
        raise ValueError('TXT·MD 파일은 64KB까지 가져올 수 있어요.')
    try:
        # The minimal browser Python runtime provides UTF-8 but not utf-8-sig.
        text = raw.decode('utf-8').removeprefix('\ufeff').strip()
    except UnicodeDecodeError as exc:
        raise ValueError('UTF-8 텍스트 파일을 골라 주세요.') from exc
    if not text or '\x00' in text or len(text) > 12000:
        raise ValueError('비어 있지 않은 텍스트를 12,000자 이내로 넣어 주세요.')
    return {'name':name, 'text':text, 'at':time.time()}


def new_draft():
    return {'id':'custom_'+uuid.uuid4().hex, 'name':'', 'bio':'', 'personality':'', 'examples':'', 'avatar':0, 'documents':[]}


def validate_card(data, complete=True):
    result = {}
    for key, maximum in FIELDS.items():
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > maximum or '\x00' in value:
            raise ValueError('입력 길이를 확인해 주세요.')
        result[key] = value.strip()
    if complete and (not result['name'] or not result['personality']):
        raise ValueError('이름과 성격 설명을 입력해 주세요.')
    avatar = data.get('avatar', 0)
    if type(avatar) is not int or not 0 <= avatar <= 2:
        raise ValueError('프로필 이미지를 다시 골라 주세요.')
    result['avatar'] = avatar
    return result


def restore_bot(data, complete=True):
    if not isinstance(data, dict) or not is_bot_id(data.get('id')):
        raise ValueError('Invalid private bot')
    result = {'id':data['id'], **validate_card(data, complete)}
    docs = data.get('documents', [])
    if not isinstance(docs, list) or len(docs) > 3:
        raise ValueError('자료는 봇마다 3개까지 보관해요.')
    result['documents'] = [read_document(doc['name'], doc['text'].encode('utf-8')) for doc in docs]
    for target, source in zip(result['documents'], docs):
        target['at'] = timestamp(source.get('at', 0))
    if complete:
        history = data.get('history', [])
        if not isinstance(history, list) or len(history) > 5:
            raise ValueError('Invalid private history')
        result['history'] = [{**validate_card(item), 'at':timestamp(item.get('at', 0)),
                              'revision':max(1, int(item.get('revision', 1)))} for item in history]
        result.update(created_at=timestamp(data.get('created_at', time.time())),
                      updated_at=timestamp(data.get('updated_at', time.time())),
                      revision=max(1, int(data.get('revision', 1))))
    return result


def save_profile(draft, previous=None):
    result = restore_bot(draft, complete=False)
    result.update(validate_card(draft))
    now = time.time()
    history = deepcopy(previous.get('history', [])) if previous else []
    if previous:
        history.append({**validate_card(previous), 'at':previous['updated_at'], 'revision':previous['revision']})
    result.update(history=history[-5:], created_at=previous['created_at'] if previous else now,
                  updated_at=now, revision=previous['revision']+1 if previous else 1)
    return result


def active_card(profile):
    return {key:profile[key] for key in FIELDS}


def check_budget(profiles, draft=None):
    if len(profiles) > MAX_BOTS or len(json.dumps({'bots':profiles, 'draft':draft}, ensure_ascii=True)) > 3000000:
        raise ValueError('개인 봇은 8개까지 만들 수 있어요. 자료나 기록을 정리해 주세요.')
