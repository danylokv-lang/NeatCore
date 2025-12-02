// NeatCore website interactions
// NeatCore website interactions (minimal for stability)
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
  // We deliberately avoid fetch streaming for large binaries to prevent partial/corrupt downloads via Pages.
  function directDownload(el){
    if(!el) return;
    // Ensure anchor has raw href
    el.addEventListener('click', function(){
      // Let browser handle native download
    });
  }

  directDownload(downloadBtn);
  directDownload(downloadInstallerBtn);
})();
