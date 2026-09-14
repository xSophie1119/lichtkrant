/* Visibility only: fields and unsaved edits stay in the form. */
(() => {
  function navigate() {
    const hash=location.hash.slice(1),target=document.getElementById(hash);
    const category=['appearance','audio','filters','vehicles','system'].includes(hash)?hash:target?.closest('[data-category-panel]')?.dataset.categoryPanel||'appearance';
    for(const panel of document.querySelectorAll('[data-category-panel]'))panel.toggleAttribute('data-page-hidden',panel.dataset.categoryPanel!==category);
    for(const link of document.querySelectorAll('[data-category]')){
      if(link.dataset.category===category)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    }
  }
  window.addEventListener('hashchange',navigate);navigate();
})();
