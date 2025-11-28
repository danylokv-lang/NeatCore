// NeatCore website interactions
(function(){
  const root = document.documentElement;
  const toggle = document.getElementById('themeToggle');
  const downloadBtn = document.getElementById('downloadBtn');
  const downloadInstallerBtn = document.getElementById('downloadInstallerBtn');

  // Theme toggle
  toggle.addEventListener('click', ()=>{
    root.classList.toggle('light');
    toggle.textContent = root.classList.contains('light') ? '🌑' : '🌗';
  });

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
    // If opened as file:// we cannot reliably HEAD fetch; attempt direct navigation
    if(location.protocol === 'file:') {
      window.location.href = url; // Browser will attempt direct file open
      return;
    }
    try {
      const res = await fetch(url, { method: 'HEAD', cache: 'no-store' });
      if(res.ok) {
        window.location.href = url;
      } else {
        alert('File not found: ' + url + '\nBuild and copy it into website/downloads.');
      }
    } catch (e) {
      alert('Unable to access: ' + url + '\nStart a local server: `python -m http.server` inside the website folder.');
    }
  }

  if(downloadBtn){
    downloadBtn.addEventListener('click', function(e){
      e.preventDefault();
      tryDownload('downloads/NeatCore.zip');
    });
  }
  if(downloadInstallerBtn){
    downloadInstallerBtn.addEventListener('click', function(e){
      e.preventDefault();
      tryDownload('downloads/NeatCore-Setup.exe');
    });
  }
})();
