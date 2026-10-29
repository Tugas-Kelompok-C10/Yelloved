(() => {
    const root = document.querySelector('.item-detail-page');
    const main = root?.querySelector('.explore-detail-image img');
    if (!main) return;
    root.querySelectorAll('[data-gallery-src]').forEach(button => button.addEventListener('click', () => {
        root.querySelectorAll('[data-gallery-src]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        main.hidden = false;
        main.closest('.explore-image').classList.remove('explore-image-failed');
        main.src = button.dataset.gallerySrc;
    }));
})();
