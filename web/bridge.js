/* Private device bridge. No profile-source upload and no provider credentials. */
(() => {
  'use strict';
  const field=document.getElementById('composer'), picker=document.getElementById('bot-file-input'),phone=document.getElementById('phone');
  const queue=[],events=[],running=new Set(),chains=new Map(),epochs=new Map();
  let identity=null,ready=false,closed=false,suspended=false,generation=null,entryMode='chat',inputKey='',composing=false,compositionEnded=0,inputRect=null,fileRect=null,fileDraft=null;
  let health={app:'loading',model:'unconfigured',configured:false};
  const ascii=value=>JSON.stringify(value).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
  const fragment=new URLSearchParams(location.hash.slice(1));
  if(fragment.has('access_token')){sessionStorage.setItem('unsent-access-token',fragment.get('access_token'));history.replaceState(null,'',location.pathname+location.search)}
  const headers=(mutation=false)=>{
    const value={'X-Unsent-Client':'1'};const token=sessionStorage.getItem('unsent-access-token');
    if(token)value.Authorization='Bearer '+token;
    if(mutation){value['Content-Type']='application/json';value['X-Unsent-CSRF']=identity.csrf_token}
    return value;
  };
  function lockIDB(work){return new Promise((resolve,reject)=>{
    const opening=indexedDB.open('unsent-private-lock',1);opening.onupgradeneeded=()=>opening.result.createObjectStore('lock');opening.onerror=()=>reject(new Error('Private lock unavailable'));
    opening.onsuccess=()=>{const db=opening.result;const tx=db.transaction('lock','readwrite');let finished=false,result,error;
      function keep(){if(finished)return;const request=tx.objectStore('lock').get('identity');request.onsuccess=()=>keep();request.onerror=()=>{error=new Error('Private lock unavailable');finished=true}}
      tx.oncomplete=()=>{db.close();error?reject(error):resolve(result)};tx.onabort=()=>{db.close();reject(error||new Error('Private lock aborted'))};
      const first=tx.objectStore('lock').get('identity');first.onsuccess=()=>{keep();Promise.resolve().then(work).then(value=>{result=value;finished=true},reason=>{error=reason;finished=true})};
    };
  })}
  const locked=work=>navigator.locks?navigator.locks.request('unsent-private-identity',work):lockIDB(work);
  function invalidate(){if(closed)return;closed=true;ready=false;running.forEach(v=>v.abort());queue.length=events.length=0;window.unsentState=undefined;field.value='';field.hidden=true;picker.hidden=true;document.getElementById('chatlog').textContent='';phone.style.visibility='hidden';location.reload()}
  async function identify(){
    if(closed)throw new Error('Session closed');
    const response=await fetch('/api/identity',{headers:headers(),credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(8000)});
    if(!response.ok)throw new Error('Private bootstrap unavailable');const next=await response.json();
    if(identity&&identity.storage_scope!==next.storage_scope){invalidate();throw new Error('Private identity changed')}
    identity=next;return next;
  }
  async function refresh(){return locked(identify)}
  async function bootstrap(){
    try{document.getElementById('retry').hidden=true;await locked(async()=>{await identify();generation=localStorage.getItem('unsent-private-session-reset')});ready=true;
      fetch('/api/health',{headers:headers(),cache:'no-store'}).then(r=>r.json()).then(v=>health={...v,configured:v.model==='reachable',model_ready:v.model==='reachable'}).catch(()=>{});
    }catch(_){document.getElementById('loading-message').textContent='개인 공간에 연결하지 못했어요. / Could not open private storage.';document.getElementById('retry').hidden=false}
  }
  document.getElementById('retry').onclick=bootstrap;
  function layout(){const sx=phone.clientWidth/414,sy=phone.clientHeight/896;
    if(inputRect){const[x,y,w,h]=inputRect;Object.assign(field.style,{left:x*sx+'px',top:y*sy+'px',width:w*sx+'px',height:h*sy+'px',fontSize:14*sx+'px'})}
    if(fileRect){const[x,y,w,h]=fileRect;Object.assign(picker.style,{left:x*sx+'px',top:y*sy+'px',width:w*sx+'px',height:h*sy+'px'})}
  }
  field.addEventListener('compositionstart',()=>{composing=true;queue.push({kind:'composition_start'})});
  field.addEventListener('compositionend',()=>{composing=false;compositionEnded=performance.now();queue.push({kind:'composition_end',text:field.value})});
  field.addEventListener('input',()=>{if(!composing)queue.push({kind:'replace',text:field.value})});
  for(const type of ['keydown','keyup','keypress'])field.addEventListener(type,event=>{
    event.stopImmediatePropagation();
    if(type!=='keydown'||event.key!=='Enter'||entryMode==='multiline'||event.shiftKey)return;
    if(composing||event.isComposing||event.keyCode===229||performance.now()-compositionEnded<30){event.preventDefault();return}
    event.preventDefault();if(field.value.trim()){queue.push({kind:'replace',text:field.value});queue.push({kind:'key',key:'Enter'});field.value=''}
  },true);
  picker.addEventListener('change',async()=>{const file=picker.files[0],draft=fileDraft;picker.value='';if(!file||closed)return;
    try{if(file.size>65536||!(/\.(txt|md)$/i.test(file.name)))throw new Error('size');const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(closed||draft!==fileDraft)return;queue.push({kind:'bot_file',name:file.name,text})}
    catch(_){queue.push({kind:'bot_file_error'})}
  });
  window.addEventListener('resize',layout);window.addEventListener('storage',event=>{if(event.key==='unsent-private-session-reset')invalidate()});
  document.addEventListener('visibilitychange',()=>{queue.push({kind:'visibility',focused:!document.hidden});if(!document.hidden)refresh().catch(()=>{})});
  // Touch drag stays in canvas coordinates, without page scrolling.
  let touchY=null;
  const canvas=document.getElementById('canvas');canvas.addEventListener('touchstart',e=>{touchY=e.touches[0]?.clientY},{passive:true});
  canvas.addEventListener('touchmove',e=>{if(touchY!==null){const y=e.touches[0].clientY;queue.push({kind:'scroll',amount:(touchY-y)*896/phone.clientHeight});touchY=y}e.preventDefault()},{passive:false});
  canvas.addEventListener('touchend',()=>touchY=null);
  const fail=request=>events.push({kind:'error',conversation_id:request.conversation_id,epoch:request.epoch,request_id:request.client_message_id,message_id:request.client_message_id,payload:{message:'답장을 불러오지 못했어요. 연결을 확인하고 다시 시도해 주세요.'}});
  async function chat(request){
    if(closed||request.epoch<(epochs.get(request.conversation_id)||0))return;
    const aborter=new AbortController();running.add(aborter);
    try{await refresh();if(closed||request.epoch<(epochs.get(request.conversation_id)||0))return;
      const response=await fetch('/api/chat',{method:'POST',credentials:'same-origin',headers:headers(true),body:JSON.stringify(request),signal:aborter.signal});
      if(!response.ok)throw new Error('Chat unavailable');const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='',complete=false;
      for(;;){const{done,value}=await reader.read();buffer+=decoder.decode(value,{stream:!done});let index;
        while((index=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,index);buffer=buffer.slice(index+2);for(const line of block.split('\n'))if(line.startsWith('data: ')){const event=JSON.parse(line.slice(6));if(event.conversation_id===request.conversation_id&&event.epoch===request.epoch&&event.kind==='done')complete=true;if(!closed&&event.epoch>=(epochs.get(event.conversation_id)||0))events.push(event)}}
        if(done)break;
      }if(!complete)throw new Error('Incomplete reply stream');
    }catch(error){if(!closed&&error.name!=='AbortError'&&request.epoch>=(epochs.get(request.conversation_id)||0))fail(request)}finally{running.delete(aborter)}
  }
  window.unsentBridge={
    isReady:()=>ready&&!closed,health:()=>ascii(health),getHealth:()=>ascii(health),
    drainInput:()=>ascii(queue.splice(0)),drainEvents:()=>ascii(events.splice(0)),
    startChat:raw=>{const request=JSON.parse(raw);window.unsentSession=request.session_id;const prev=chains.get(request.conversation_id)||Promise.resolve();const next=prev.catch(()=>{}).then(()=>chat(request));chains.set(request.conversation_id,next)},
    reset:(cid,epoch,sessionID)=>{epochs.set(cid,epoch);const session=sessionID||window.unsentSession;if(!session)return;refresh().then(()=>fetch('/api/conversations/'+encodeURIComponent(cid)+'/reset',{method:'POST',headers:headers(true),credentials:'same-origin',body:JSON.stringify({session_id:session,epoch})})).catch(()=>{})},
    load:()=>{if(!ready||closed)return '';try{return localStorage.getItem('unsent-device:'+identity.storage_scope)||''}catch(_){return ''}},
    store:raw=>{if(!ready||closed||suspended)return 0;try{const key='unsent-device:'+identity.storage_scope;if(localStorage.getItem('unsent-private-session-reset')!==generation){invalidate();return 0}localStorage.setItem(key,raw);if(localStorage.getItem('unsent-private-session-reset')!==generation){localStorage.removeItem(key);invalidate();return 0}return 1}catch(_){return 0}},
    setInput:(raw,value,label,w,h,placeholder,mode='chat',limit=2000,key='')=>{
      const rect=JSON.parse(raw);inputRect=rect;field.hidden=!rect||closed;entryMode=mode;
      if(!field.hidden){const next=JSON.parse(value);if(field.value!==next&&(!composing||inputKey!==key))field.value=next;field.setAttribute('aria-label',JSON.parse(label));field.placeholder=JSON.parse(placeholder);field.maxLength=limit;inputKey=key;layout()}
    },
    setBotFileButton:(raw,label,draft='""')=>{fileRect=JSON.parse(raw);fileDraft=JSON.parse(draft);picker.hidden=!fileRect||closed;picker.setAttribute('aria-label',JSON.parse(label));layout()},pickBotFile:()=>picker.click(),
    snapshot:raw=>{if(closed||suspended)return;const state=JSON.parse(raw);window.unsentState=state;document.documentElement.lang=state.language;document.title='Unsent · '+(state.language==='en'?'Messages':'메시지');canvas.setAttribute('aria-label',state.language==='en'?'Unsent messages':'Unsent 메시지');document.getElementById('chatlog').textContent=Object.values(state.conversations).flatMap(c=>c.messages.map(m=>m.text)).join('\n')},
    ready:()=>{document.getElementById('loading').hidden=true;document.getElementById('loading').style.display='none'},
    freshSession:async()=>{try{await locked(async()=>{await identify();suspended=true;ready=false;localStorage.setItem('unsent-private-session-reset','resetting:'+Date.now()+'-'+Math.random());const r=await fetch('/api/identity/new',{method:'POST',headers:headers(true),credentials:'same-origin',body:'{}'});if(!r.ok)throw new Error('Private reset failed');for(const key of Object.keys(localStorage))if(key==='unsent-device'||key.startsWith('unsent-device:'))localStorage.removeItem(key);localStorage.setItem('unsent-private-session-reset','complete:'+Date.now()+'-'+Math.random())});invalidate()}catch(_){invalidate()}},
    copy:text=>navigator.clipboard?.writeText(text).catch(()=>{}),close:()=>{running.forEach(v=>v.abort());closed=true}
  };
  bootstrap();
})();
