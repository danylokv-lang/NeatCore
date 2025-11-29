// NeatCore website interactions
(function(){
  const downloadBtn = document.getElementById('downloadBtn');
  const downloadInstallerBtn = document.getElementById('downloadInstallerBtn');

  // Smooth scroll for in-page anchors
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const id = a.getAttribute('href').slice(1);
      if(id){
        const el = document.getElementById(id);
        if(el){
          e.preventDefault();
          el.scrollIntoView({behavior:'smooth'});
        }
      }
    });
  });

  // Simple visibility animation
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if(entry.isIntersecting){
        entry.target.classList.add('reveal');
      }
    });
  }, {threshold:0.15});
  document.querySelectorAll('.card, .steps li, .faq details').forEach(el => {
    el.classList.add('pre-reveal');
    observer.observe(el);
  });

  // Helper to test file exists before navigating
  async function tryDownload(url){
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if(!res.ok) throw new Error('Status '+res.status);
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      const parts = url.split('/');
      a.download = parts[parts.length-1];
      document.body.appendChild(a);
      a.click();
      setTimeout(()=>{
        URL.revokeObjectURL(a.href);
        a.remove();
      }, 1500);
    } catch (e){
      alert('Download failed for: '+url+'\nEnsure the file exists and a proper server serves it.');
    }
  }

  function wire(btn){
    if(!btn) return;
    const file = btn.getAttribute('data-file');
    btn.addEventListener('click', e => {
      e.preventDefault();
      if(file) tryDownload(file);
    });
  }
  wire(downloadBtn);
  wire(downloadInstallerBtn);
})();
