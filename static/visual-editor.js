(() => {
  const meta=document.querySelector('meta[name="visual-editor-csrf"]'); if(!meta)return;
  let changes={},tierPrices={},layout={},images={},csrf=meta.content,active=false,dirty=false,current=null,drag=null,suppressClick=false,selectedImage=null;
  const page=location.pathname.replace(/\/$/,'')||'/';
  const launch=document.createElement('button');launch.type='button';launch.className='visual-edit-launch';launch.textContent='✎ Edit website';document.body.appendChild(launch);
  const bar=document.createElement('div');bar.className='visual-editor-bar';
  bar.innerHTML='<span class="visual-editor-help">Editor · click text or image · drag links</span><span class="visual-editor-status">Ready</span><button type="button" class="secondary" data-action="upload">Upload image</button><button type="button" class="secondary" data-action="cancel">Cancel</button><button type="button" data-action="save">Save</button>';
  document.body.appendChild(bar);
  const status=bar.querySelector('.visual-editor-status'),saveButton=bar.querySelector('[data-action="save"]');
  const picker=document.createElement('input');picker.type='file';picker.accept='image/png,image/jpeg,image/webp,image/gif';picker.hidden=true;document.body.appendChild(picker);
  function key(el){const p=[];let n=el;while(n&&n!==document.body){const parent=n.parentElement;if(!parent)break;const sib=Array.from(parent.children).filter(x=>x.tagName===n.tagName);p.unshift(n.tagName.toLowerCase()+':'+sib.indexOf(n));n=parent;}return page+'|'+p.join('/');}
  function editable(el){if(!el||!el.isConnected||el.closest('.visual-editor-bar,.visual-edit-launch,script,style,select,option,input,textarea,svg'))return false;
    if(['A','BUTTON'].includes(el.tagName))return el.textContent.trim().length>0;
    return ['H1','H2','H3','P','SMALL','STRONG','SPAN','LABEL','DIV','FOOTER','LI','TD','TH'].includes(el.tagName)&&el.children.length===0&&Array.from(el.childNodes).some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());}
  function apply(){document.querySelectorAll('body *').forEach(el=>{const k=key(el);if(editable(el)&&Object.prototype.hasOwnProperty.call(changes,k))el.textContent=changes[k];
    if(el.dataset.tierPrice&&tierPrices[el.dataset.tierPrice])el.textContent='€'+tierPrices[el.dataset.tierPrice];
    if(el.tagName==='IMG'&&images[k])el.src=images[k];
    if(layout[k]){el.style.transform='translate('+layout[k].x+'px,'+layout[k].y+'px)';el.dataset.visualMovable='1';}});}
  async function load(){const r=await fetch('/api/visual-editor');if(!r.ok)throw new Error('Could not load editor');const d=await r.json();changes=d.changes||{};tierPrices=d.tierPrices||{};layout=d.layout||{};images=d.images||{};csrf=d.csrf||csrf;apply();}
  function markDirty(){dirty=true;status.textContent='Unsaved changes';}
  function finish(){if(!current)return;const k=current.dataset.visualKey,v=current.innerText;if(k&&changes[k]!==v){changes[k]=v;markDirty();}if(current.dataset.tierPrice){const m=v.match(/([0-9]{1,4},[0-9]{2})/);if(m){tierPrices[current.dataset.tierPrice]=m[1];markDirty();}}current.removeAttribute('contenteditable');current=null;}
  function start(el){if(!editable(el)||current===el)return;finish();const k=key(el);el.dataset.visualKey=k;el.dataset.visualEditable='1';current=el;el.setAttribute('contenteditable','true');el.focus();const range=document.createRange();range.selectNodeContents(el);range.collapse(false);const sel=getSelection();sel.removeAllRanges();sel.addRange(range);status.textContent='Editing text';}
  async function upload(file,target){if(!file)return;const form=new FormData();form.append('image',file);form.append('csrf',csrf);status.textContent='Uploading…';
    try{const r=await fetch('/api/visual-editor/upload',{method:'POST',body:form});const d=await r.json();if(!r.ok)throw new Error(d.error||'Upload failed');
      let img=target;if(!img){img=document.createElement('img');img.alt='Uploaded image';img.className='visual-editor-added-image';const host=document.querySelector('main')||document.querySelector('.section')||document.body;host.appendChild(img);}
      const k=key(img);img.src=d.url;images[k]=d.url;selectedImage=img;markDirty();status.textContent='Image uploaded · Save to publish';
    }catch(e){status.textContent=e.message||'Upload failed';}}
  function save(){finish();if(!dirty){status.textContent='All changes saved';return;}saveButton.disabled=true;status.textContent='Saving…';
    fetch('/api/visual-editor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf,changes,tierPrices,layout,images})})
      .then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error||'Save failed');dirty=false;status.textContent=d.githubSynced?'Saved · committed to main ✓':'Saved · GitHub sync not configured';})
      .catch(e=>status.textContent=e.message||'Save failed').finally(()=>saveButton.disabled=false);}
  function mode(on){active=on;document.body.classList.toggle('visual-editing',on);bar.classList.toggle('is-visible',on);launch.textContent=on?'✕ Close editor':'✎ Edit website';if(!on)finish();}
  launch.addEventListener('click',async()=>{if(active){if(dirty&&!confirm('Discard unsaved changes?'))return;mode(false);return;}try{await load();mode(true);status.textContent='Click text/image · drag links · links disabled';}catch(e){alert(e.message);}});
  document.addEventListener('click',e=>{if(!active||e.target.closest('.visual-editor-bar,.visual-edit-launch'))return;
    e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();
    if(suppressClick){suppressClick=false;return;}
    const img=e.target.closest('img');if(img){selectedImage=img;picker.onchange=()=>{upload(picker.files[0],img);picker.value='';};picker.click();return;}
    let el=e.target;while(el&&el!==document.body&&!editable(el))el=el.parentElement;if(el&&el!==document.body)start(el);
  },true);
  document.addEventListener('pointerdown',e=>{if(!active||e.target.closest('.visual-editor-bar,.visual-edit-launch'))return;const el=e.target.closest('a,button,[role="button"]');if(!el)return;const k=key(el),old=layout[k]||{x:0,y:0};drag={el,k,sx:e.clientX,sy:e.clientY,x:old.x,y:old.y,moved:false};},true);
  document.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.sx,dy=e.clientY-drag.sy;if(Math.abs(dx)+Math.abs(dy)<5)return;drag.moved=true;const pos={x:Math.round(drag.x+dx),y:Math.round(drag.y+dy)};drag.el.style.transform='translate('+pos.x+'px,'+pos.y+'px)';drag.el.dataset.visualMovable='1';layout[drag.k]=pos;markDirty();},true);
  document.addEventListener('pointerup',()=>{if(drag){if(drag.moved){status.textContent='Link position changed';suppressClick=true;}drag=null;}},true);
  bar.querySelector('[data-action="upload"]').addEventListener('click',()=>{picker.onchange=()=>{upload(picker.files[0],selectedImage);picker.value='';};picker.click();});
  bar.querySelector('[data-action="cancel"]').addEventListener('click',()=>{if(dirty&&!confirm('Discard unsaved changes?'))return;location.reload();});
  saveButton.addEventListener('click',save);
  document.addEventListener('keydown',e=>{if(active&&e.key==='Escape'&&current){current.textContent=changes[current.dataset.visualKey]??current.textContent;current.removeAttribute('contenteditable');current=null;}if(active&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save();}});
})();