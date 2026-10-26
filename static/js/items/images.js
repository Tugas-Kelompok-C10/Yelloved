(() => {
    function fallback(image) {
        if (!image.matches('.explore-page img[data-fallback]')) return;
        const source = image.dataset.fallback;
        if (!source) return;
        delete image.dataset.fallback;
        image.hidden = true;
        image.closest('.explore-image')?.classList.add('explore-image-failed');
    }
    // Capture also handles catalog cards inserted by AJAX.
    document.addEventListener('error', event => {
        if (event.target instanceof HTMLImageElement) fallback(event.target);
    }, true);
    document.querySelectorAll('.explore-page img[data-fallback]').forEach(image => {
        if (image.complete && !image.naturalWidth) fallback(image);
    });
})();
