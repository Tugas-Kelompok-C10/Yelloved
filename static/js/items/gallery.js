(() => {
    const root = document.querySelector('.item-detail-page');
    const main = root?.querySelector('.explore-detail-image img');
    const data = root?.querySelector('#item-gallery-data');
    if (!main || !data) return;
    const photos = JSON.parse(data.textContent);
    if (!photos.length) return;
    const thumbnails = [...root.querySelectorAll('[data-gallery-src]')];
    const status = root.querySelector('#item-gallery-status');
    const dialog = root.querySelector('#item-photo-dialog');
    const viewer = dialog?.querySelector('.item-photo-viewer');
    let current = 0;
    let opener;
    function select(index) {
        current = (index + photos.length) % photos.length;
        main.hidden = false;
        main.dataset.fallback = main.dataset.fallback || 'gallery';
        main.closest('.explore-image').classList.remove('explore-image-failed');
        main.src = photos[current].url;
        thumbnails.forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.galleryIndex) === current)));
        const label = `Photo ${current + 1} of ${photos.length}`;
        status.textContent = label;
        if (dialog?.open) {
            viewer.hidden = false;
            dialog.querySelector('[data-photo-error]').hidden = true;
            viewer.src = photos[current].url;
            dialog.querySelector('[data-photo-count]').textContent = label;
        }
    }
    thumbnails.forEach(button => button.addEventListener('click', () => {
        select(Number(button.dataset.galleryIndex));
        if (button.dataset.galleryMore && dialog) {
            opener = button;
            dialog.showModal();
            select(current);
        }
    }));
    if (!dialog) return;
    viewer.addEventListener('error', () => { viewer.hidden = true; dialog.querySelector('[data-photo-error]').hidden = false; });
    dialog.querySelector('[data-photo-close]').addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-photo-prev]').addEventListener('click', () => select(current - 1));
    dialog.querySelector('[data-photo-next]').addEventListener('click', () => select(current + 1));
    dialog.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); select(current + (event.key === 'ArrowRight' ? 1 : -1)); }
    });
    dialog.addEventListener('click', event => {
        const bounds = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
    });
    dialog.addEventListener('close', () => opener?.focus());
})();
