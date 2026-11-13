(() => {
  const meta = document.querySelector('meta[name="visual-editor-csrf"]');
  if (!meta) return;
  let changes={}, tierPrices={}, layout={}, csrf=meta.content, active=false, dirty=false, current=null, drag=null;
  const page=location.pathname.replace(/\/$/,'')||'/';
  const launch=document.createElement('button');
  launch.type='button'; launch.className='visual-edit-launch'; launch.textContent='✎ Website bearbeiten';
  document.body.appendChild(launch);
  const bar=document.createElement('div');
  bar.className='visual-editor-bar';
  bar.innerHTML='<span>Editor · Texte anklicken, Buttons ziehen</span><span class="visual-editor-status">Bereit</span><button type="button" class="secondary" data-action="cancel">Abbrechen</button><button type="button" data-action="save">Speichern</button>';
  document.body.appendChild(bar);
  const status=bar.querySelector('.visual-editor-status'), saveButton=bar.querySelector('[data-action="save"]');
  function key(el){
    const parts=[];let node=el;
    while(node&&node!==document.body){
      const parent=node.parentElement;if(!parent)break;
      const siblings=Array.from(parent.children).filter(x=>x.tagName===node.tagName);
      parts.unshift(node.tagName.toLowerCase()+':'+siblings.indexOf(node));node=parent;
    }
    return page+'|'+parts.join('/');
  }
  function editable(el){
    if(!el||!el.isConnected||el.closest('.visual-editor-bar,.visual-edit-launch,script,style,select,option,input,textarea,svg'))return false;
    if(['A','BUTTON'].includes(el.tagName))return el.textContent.trim().length>0;
    return ['H1','H2','H3','P','SMALL','STRONG','SPAN','LABEL','DIV','FOOTER','LI','TD','TH'].includes(el.tagName)
      && el.children.length===0 && Array.from(el.childNodes).some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());
  }
  function apply(){
    document.querySelectorAll('body *').forEach(el=>{
      if(editable(el)){
        const k=key(el);
        if(Object.prototype.hasOwnProperty.call(changes,k))el.textContent=changes[k];
        if(el.dataset.tierPrice&&tierPrices[el.dataset.tierPrice])el.textContent='€'+tierPrices[el.dataset.tierPrice];
      }
      const k=key(el);
      if(layout[k]){el.style.transform='translate('+layout[k].x+'px,'+layout[k].y+'px)';el.dataset.visualMovable='1';}
    });
  }
  async function load(){
    const r=await fetch('/api/visual-editor');if(!r.ok)throw new Error('Editor konnte nicht geladen werden.');
    const data=await r.json();changes=data.changes||{};tierPrices=data.tierPrices||{};layout=data.layout||{};csrf=data.csrf||csrf;apply();
  }
  function markDirty(){dirty=true;status.textContent='Nicht gespeichert';}
  function finish(){
    if(!current)return;
    const k=current.dataset.visualKey,value=current.textContent;
    if(k&&changes[k]!==value){changes[k]=value;markDirty();}
    if(current.dataset.tierPrice){const m=value.match(/([0-9]{1,4},[0-9]{2})/);if(m){tierPrices[current.dataset.tierPrice]=m[1];markDirty();}}
    current.removeAttribute('contenteditable');current=null;
  }
  function start(el){
    if(!editable(el)||current===el)return;finish();
    const k=key(el);el.dataset.visualKey=k;el.dataset.visualEditable='1';current=el;
    el.setAttribute('contenteditable','true');el.focus();
    const range=document.createRange();range.selectNodeContents(el);range.collapse(false);
    const sel=window.getSelection();sel.removeAllRanges();sel.addRange(range);status.textContent='Text bearbeiten';
  }
  async function save(){
    finish();if(!dirty){status.textContent='Alles gespeichert';return;}
    saveButton.disabled=true;status.textContent='Speichert …';
    try{
      const r=await fetch('/api/visual-editor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf,changes,tierPrices,layout})});
      if(!r.ok)throw new Error('Speichern fehlgeschlagen');
      const data=await r.json();dirty=false;
      status.textContent=data.githubSynced?'Gespeichert · Commit in main ✓':'Gespeichert · GitHub-Sync nicht eingerichtet';
    }catch(e){status.textContent='Fehler beim Speichern';}
    finally{saveButton.disabled=false;}
  }
  function mode(on){active=on;document.body.classList.toggle('visual-editing',on);bar.classList.toggle('is-visible',on);launch.textContent=on?'✕ Bearbeitung schließen':'✎ Website bearbeiten';if(!on)finish();}
  launch.addEventListener('click',async()=>{
    if(active){if(dirty&&!confirm('Ungespeicherte Änderungen verwerfen?'))return;mode(false);return;}
    try{await load();mode(true);status.textContent='Text anklicken · Button ziehen';}catch(e){alert(e.message);}
  });
  document.addEventListener('click',e=>{
    if(!active||e.target.closest('.visual-editor-bar,.visual-edit-launch'))return;
    if(suppressClick){suppressClick=false;e.preventDefault();e.stopPropagation();return;}
    let el=e.target;while(el&&el!==document.body&&!editable(el))el=el.parentElement;
    if(el&&el!==document.body){e.preventDefault();e.stopPropagation();start(el);}
  },true);
  document.addEventListener('pointerdown',e=>{
    if(!active||e.target.closest('.visual-editor-bar,.visual-edit-launch'))return;
    const el=e.target.closest('a,button,[role="button"]');if(!el)return;
    const k=key(el),old=layout[k]||{x:0,y:0};
    drag={el,k,sx:e.clientX,sy:e.clientY,x:old.x,y:old.y,moved:false};
  },true);
  document.addEventListener('pointermove',e=>{
    if(!drag)return;
    const dx=e.clientX-drag.sx,dy=e.clientY-drag.sy;
    if(Math.abs(dx)+Math.abs(dy)<5)return;
    drag.moved=true;const pos={x:Math.round(drag.x+dx),y:Math.round(drag.y+dy)};
    drag.el.style.transform='translate('+pos.x+'px,'+pos.y+'px)';drag.el.dataset.visualMovable='1';layout[drag.k]=pos;markDirty();
  },true);
  document.addEventListener('pointerup',()=>{if(drag){if(drag.moved){status.textContent='Position geändert';suppressClick=true;}drag=null;}},true);
  document.addEventListener('keydown',e=>{
    if(active&&e.key==='Escape'&&current){current.textContent=changes[current.dataset.visualKey]??current.textContent;current.removeAttribute('contenteditable');current=null;}
    if(active&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save();}
  });
  saveButton.addEventListener('click',save);
  bar.querySelector('[data-action="cancel"]').addEventListener('click',()=>{if(dirty&&!confirm('Ungespeicherte Änderungen verwerfen?'))return;location.reload();});
})();