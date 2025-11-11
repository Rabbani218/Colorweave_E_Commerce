// Global site JS (CSP-compliant: served from /static)
(function(){
  // Persisted theme toggle (light/dark via data-theme on <html>)
  try {
    const root = document.documentElement;
    const saved = localStorage.getItem('cw-theme');
    if(saved === 'dark'){ root.setAttribute('data-theme','dark'); }
    const btns = document.querySelectorAll('#themeToggle');
    const setState = () => {
      const isDark = root.getAttribute('data-theme') === 'dark';
      btns.forEach(b=> {
        b.classList.toggle('active', isDark);
        const icon = b.querySelector('[data-icon]');
        const label = b.querySelector('[data-label]');
        if(icon){ icon.textContent = isDark ? '🌜' : '🌞'; }
        if(label){ label.textContent = isDark ? 'Dark' : 'Light'; }
        b.setAttribute('data-mode', isDark ? 'dark' : 'light');
        b.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        b.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
      });
    };
    setState();
    btns.forEach(btn=> btn.addEventListener('click', ()=>{
      const isDark = root.getAttribute('data-theme') === 'dark';
      if(isDark){ root.removeAttribute('data-theme'); localStorage.setItem('cw-theme','light'); }
      else { root.setAttribute('data-theme','dark'); localStorage.setItem('cw-theme','dark'); }
      setState();
    }));
  } catch {}

  // Navbar scroll effect
  const nav = document.querySelector('.navbar');
  if(nav){
    const onScroll = () => {
      if(window.scrollY > 10){ nav.classList.add('scrolled'); }
      else { nav.classList.remove('scrolled'); }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // AI Assistant Widget logic
  const panel = document.getElementById('aiPanel');
  const toggle = document.getElementById('aiToggle');
  const form = document.getElementById('aiForm');
  const input = document.getElementById('aiInput');
  const msgs = document.getElementById('aiMessages');
  function append(role, text){
    if(!msgs) return;
    const div = document.createElement('div');
    div.className = 'ai-msg ' + role;
    div.textContent = text;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }
  if(toggle && panel){
    toggle.addEventListener('click', ()=>{
      const isOpen = panel.style.display === 'flex';
      panel.style.display = isOpen ? 'none' : 'flex';
      if(!isOpen && input){ input.focus(); }
    });
  }
  if(form){
    form.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const q = (input?.value || '').trim();
      if(!q) return;
      append('user', q);
      if(input) input.value = '';
      try{
        const resp = await fetch('/api/ai/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:q})});
        const data = await resp.json();
        if(data.reply) append('assistant', data.reply);
      }catch(err){ append('assistant','Maaf, terjadi kesalahan.'); }
    });
  }

  // Image skeleton initializer
  function initSkeletons(scope=document){
    const imgs = scope.querySelectorAll('[data-skel-img]');
    imgs.forEach(img => {
      const wrap = img.closest('[data-skel]');
      const clear = ()=> wrap && wrap.classList.remove('skeleton');
      if(img.complete) { clear(); }
      else { img.addEventListener('load', clear, { once: true }); img.addEventListener('error', clear, { once: true }); }
    });
  }
  initSkeletons(document);

  // Expose for product page dynamic rendering
  window.__cwInitSkeletons = initSkeletons;

  // Image error fallback (CSP-friendly, no inline handlers)
  function initImageFallbacks(scope=document){
    const imgs = scope.querySelectorAll('img[data-fallback]');
    imgs.forEach(img => {
      const fallback = img.getAttribute('data-fallback');
      if(!fallback) return;
      const onErr = () => {
        // prevent infinite loop
        img.removeEventListener('error', onErr);
        img.src = fallback;
      };
      // Attach if not yet fallbacked
      if(img.src !== fallback){ img.addEventListener('error', onErr); }
    });
  }
  initImageFallbacks(document);
  window.__cwInitImageFallbacks = initImageFallbacks;
})();
