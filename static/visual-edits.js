(() => {
  const page = location.pathname.replace(/\/$/, '') || '/';
  const key = el => {
    const path = [];
    let node = el;
    while (node && node !== document.body) {
      const parent = node.parentElement;
      if (!parent) break;
      const siblings = [...parent.children].filter(item => item.tagName === node.tagName);
      path.unshift(node.tagName.toLowerCase() + ':' + siblings.indexOf(node));
      node = parent;
    }
    return page + '|' + path.join('/');
  };
  const safeHTML = value => {
    const doc = new DOMParser().parseFromString(String(value), 'text/html');
    const allowed = new Set(['B','STRONG','I','EM','U','S','SPAN','BR','FONT','IMG']);
    doc.body.querySelectorAll('*').forEach(el => {
      if (!allowed.has(el.tagName)) { el.replaceWith(...el.childNodes); return; }
      [...el.attributes].forEach(attr => {
        if (el.tagName === 'IMG' && attr.name === 'src' && attr.value.startsWith('/uploads/')) return;
        if (el.tagName === 'IMG' && attr.name === 'alt') return;
        if (el.tagName === 'IMG' && attr.name === 'class' && /^(visual-editor-added-image|visual-editor-logo)( visual-editor-added-image| visual-editor-logo)*$/.test(attr.value)) return;
        if (el.tagName === 'IMG' && ['width','height'].includes(attr.name) && /^\d{1,4}$/.test(attr.value)) return;
        if (attr.name === 'style') {
          const safe = [];
          for (const part of attr.value.split(';')) {
            const ix = part.indexOf(':');
            if (ix < 0) continue;
            const prop = part.slice(0, ix).trim().toLowerCase();
            const val = part.slice(ix + 1).trim();
            if (['color','font-size','font-family','font-weight','font-style','text-decoration'].includes(prop) && !/url\s*\(|expression|javascript/i.test(val)) safe.push(prop + ':' + val);
          }
          el.setAttribute('style', safe.join(';'));
        } else if (!['color','face','size'].includes(attr.name)) el.removeAttribute(attr.name);
      });
    });
    return doc.body.innerHTML;
  };
  fetch('/api/visual-edits-public', { cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error('Live editor data unavailable'); return response.json(); })
    .catch(() => fetch('/static/visual-edits.json?v=20261113-live-public-api', { cache: 'no-store' }).then(response => response.ok ? response.json() : null))
    .then(data => {
      if (!data || typeof data !== 'object') return;
      const changes = data.content || {};
      const prices = data.tierPrices || {};
      const layout = data.layout || {};
      const images = data.images || {};
      const styles = data.styles || {};
      if (styles['__visual_global__']) { const g=styles['__visual_global__']; Object.assign(document.body.style,g); let tag=document.getElementById('ve-global-style'); if(!tag){tag=document.createElement('style');tag.id='ve-global-style';document.head.appendChild(tag);} tag.textContent=(g.color?'body *{color:'+g.color+'!important;}':'')+(g.background?'html,body{background:'+g.background+'!important;}':''); }
      if (styles[key(document.body)]) Object.assign(document.body.style, styles[key(document.body)]);
      document.querySelectorAll('body *').forEach(el => {
        const id = key(el);
        if (el.tagName === 'IMG' && images[id]) el.src = images[id];
        if (el.dataset.tierPrice && prices[el.dataset.tierPrice]) el.textContent = '€' + prices[el.dataset.tierPrice];
        if (layout[id]) el.style.transform = 'translate(' + layout[id].x + 'px,' + layout[id].y + 'px)';
        if (styles[id] && typeof styles[id] === 'object') Object.assign(el.style, styles[id]);
        if (Object.prototype.hasOwnProperty.call(changes, id) && !['IMG','BODY','MAIN','SECTION','HEADER','FOOTER','DIV','ARTICLE','ASIDE','NAV','UL','OL'].includes(el.tagName)) el.innerHTML = safeHTML(changes[id]);
      });
      Object.keys(images).filter(id => id.startsWith('__visual_overlay__:') || id.startsWith('__visual_global_overlay__:')).forEach(id => {
        let img = document.querySelector('img[data-ve-overlay-key="' + id + '"]');
        if (!img) {
          img = document.createElement('img');
          img.alt = 'Neues Bild';
          img.className = 'visual-editor-added-image';
          img.dataset.veOverlayKey = id;
          document.body.appendChild(img);
        }
        img.src = images[id];
        Object.assign(img.style, styles[id] || {});
        if (layout[id]) img.style.transform = 'translate(' + layout[id].x + 'px,' + layout[id].y + 'px)';
      });
    })
    .catch(() => {});
})();
