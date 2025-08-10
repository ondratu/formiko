document.addEventListener('click', (e) => {
  const toggler = e.target.closest('.jtoggler');
  if (!toggler) return;
  const block = toggler.parentElement;
  const collapsed = block.classList.toggle('collapsed');
  if (e.altKey) {
    block.querySelectorAll('.jblock').forEach((el) => {
      if (el === block) return;
      if (collapsed) el.classList.add('collapsed');
      else el.classList.remove('collapsed');
    });
  }
});
