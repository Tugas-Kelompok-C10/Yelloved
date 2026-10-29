/* A stored file name can outlive its file. Fall back without retry loops. */
(() => {
    const script = document.currentScript;
    const avatar = script.dataset.avatarFallback;
    const avatars = '.nav-profile-trigger img, .profile-dropdown-heading > img, .profile-avatar img, .biodata-photo-placeholder img, .public-profile-avatar, .security-card-icon img, .wanted-detail-avatar img, .item-seller-avatar img';
    const fallback = image => {
        if (!(image instanceof HTMLImageElement)) return;
        // Explore has its own placeholder treatment and error handler.
        if (image.matches('.explore-page img[data-fallback]')) return;
        const replacement = image.dataset.fallback || (image.matches(avatars) ? avatar : '');
        if (!replacement) return;
        if (image.src === new URL(replacement, document.baseURI).href) {
            image.hidden = true;
            return;
        }
        image.src = replacement;
    };
    const scan = root => {
        const images = root instanceof HTMLImageElement ? [root] : root.querySelectorAll('img');
        images.forEach(image => {
            if (image.complete && !image.naturalWidth) fallback(image);
        });
    };
    document.addEventListener('error', event => fallback(event.target), true);
    scan(document);
    // Account navigation replaces content via AJAX, including cached images.
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
        if (node instanceof Element) scan(node);
    }))).observe(document.body, {childList: true, subtree: true});
})();
