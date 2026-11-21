// eagleeye.sh: copy buttons (install rows + step 01) and the phone menu.
(() => {
  const copy = async (text) => {
    try { await navigator.clipboard.writeText(text); return true; } catch (_) {}
    const ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (_) {}
    ta.remove(); return ok;
  };
  document.querySelectorAll('[data-copy]').forEach((el) => {
    const status = el.querySelector('.status');
    const idle = status ? status.textContent : '';
    el.addEventListener('click', async () => {
      const ok = await copy(el.dataset.copy);
      if (!status) return;
      status.textContent = ok ? 'Copied' : 'Select and copy';
      el.classList.toggle('done', ok);
      clearTimeout(el._t);
      el._t = setTimeout(() => { status.textContent = idle; el.classList.remove('done'); }, 1600);
    });
  });
  // features: open rows on desktop (opencode's grid), collapsed rows on a phone (opencode's accordion)
  const phone = matchMedia('(max-width: 900px)');
  const setRows = () => document.querySelectorAll('.features details').forEach((d) => { d.open = !phone.matches; });
  setRows(); phone.addEventListener('change', setRows);
  const rail = document.querySelector('.rail');
  const btn = document.querySelector('.menu-btn');
  if (rail && btn) btn.addEventListener('click', () => {
    const open = rail.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
  });
})();
