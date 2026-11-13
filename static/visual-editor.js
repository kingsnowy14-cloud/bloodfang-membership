(() => {
  const launch = document.getElementById('visualEditLaunch');
  const csrfMeta = document.querySelector('meta[name="visual-editor-csrf"]');
  if (!launch || !csrfMeta) return;
  let changes = {}, csrf = csrfMeta.content, active = false, dirty = false, current = null;
  const bar = document.createElement('div');
  bar.className = 'visual-editor-bar';
  bar.innerHTML = '<span>Bearbeitungsmodus · Text anklicken</span><span class="visual-editor-status" aria-live="polite">Bereit</span><button type="button" class="secondary" data-action="cancel">Abbrechen</button><button type="button" data-action="save">Speichern</button>';
  document.body.appendChild(bar);
  const status = bar.querySelector('.visual-editor-status');
  const saveButton = bar.querySelector('[data-action="save"]');

  function elementKey(el) {
    const parts = [];
    let node = el;
    while (node && node !== document.body) {
      const parent = node.parentElement;
      if (!parent) break;
      const siblings = Array.from(parent.children).filter(child => child.tagName === node.tagName);
      parts.unshift(node.tagName.toLowerCase() + ':' + siblings.indexOf(node));
      node = parent;
    }
    return parts.join('/');
  }
  function eligible(el) {
    if (!el || !el.isConnected || el.closest('.visual-editor-bar, header, script, style, select, option, button, input, textarea, svg')) return false;
    return ['A','H1','H2','H3','P','SMALL','STRONG','SPAN','LABEL','DIV','FOOTER'].includes(el.tagName) &&
      Array.from(el.childNodes).some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
  }
  function applySavedContent() {
    document.querySelectorAll('main, footer').forEach(root => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT), nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(el => {
        if (!eligible(el)) return;
        const key = elementKey(el);
        if (Object.prototype.hasOwnProperty.call(changes, key)) el.textContent = changes[key];
      });
    });
  }
  async function load() {
    const response = await fetch('/api/visual-editor');
    if (!response.ok) throw new Error('Editor konnte nicht geladen werden.');
    const data = await response.json();
    changes = data.changes || {};
    csrf = data.csrf || csrf;
    applySavedContent();
  }
  function finishCurrent() {
    if (!current) return;
    const key = current.dataset.visualKey, value = current.textContent;
    if (key && changes[key] !== value) { changes[key] = value; dirty = true; status.textContent = 'Nicht gespeichert'; }
    current.removeAttribute('contenteditable'); current = null;
  }
  function startEditing(el) {
    if (!eligible(el) || current === el) return;
    finishCurrent();
    const key = elementKey(el);
    el.dataset.visualKey = key; el.dataset.visualEditable = '1'; current = el;
    el.setAttribute('contenteditable', 'true'); el.focus();
    const range = document.createRange(); range.selectNodeContents(el); range.collapse(false);
    const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
    status.textContent = 'Text bearbeiten';
  }
  async function save() {
    finishCurrent();
    if (!dirty) { status.textContent = 'Alles gespeichert'; return; }
    saveButton.disabled = true; status.textContent = 'Speichert …';
    try {
      const response = await fetch('/api/visual-editor', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf,changes})});
      if (!response.ok) throw new Error('Speichern fehlgeschlagen');
      dirty = false; status.textContent = 'Gespeichert ✓';
    } catch (error) { status.textContent = 'Fehler beim Speichern'; }
    finally { saveButton.disabled = false; }
  }
  function setMode(on) {
    active = on; document.body.classList.toggle('visual-editing', on); bar.classList.toggle('is-visible', on);
    launch.textContent = on ? '✕ Bearbeitung schließen' : '✎ Website bearbeiten';
    if (!on) finishCurrent();
  }
  launch.addEventListener('click', async () => {
    if (active) { if (dirty && !window.confirm('Ungespeicherte Änderungen verwerfen?')) return; setMode(false); return; }
    try { await load(); setMode(true); status.textContent = 'Bereit zum Bearbeiten'; }
    catch (error) { window.alert(error.message); }
  });
  document.addEventListener('click', event => {
    if (!active || event.target.closest('.visual-editor-bar, #visualEditLaunch')) return;
    let target = event.target;
    while (target && target !== document.body && !eligible(target)) target = target.parentElement;
    if (target && target !== document.body) { event.preventDefault(); event.stopPropagation(); startEditing(target); }
  }, true);
  document.addEventListener('keydown', event => {
    if (active && event.key === 'Escape' && current) {
      current.textContent = changes[current.dataset.visualKey] ?? current.textContent;
      current.removeAttribute('contenteditable'); current = null;
    }
    if (active && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); save(); }
  });
  saveButton.addEventListener('click', save);
  bar.querySelector('[data-action="cancel"]').addEventListener('click', () => {
    if (dirty && !window.confirm('Ungespeicherte Änderungen verwerfen?')) return;
    window.location.reload();
  });
})();