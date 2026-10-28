(() => {
    const root = document.querySelector('.item-detail-page');
    const dialog = root?.querySelector('#item-offer-dialog');
    const opener = root?.querySelector('#item-offer-open');
    if (!dialog || !opener) return;
    const form = dialog.querySelector('form');
    const message = dialog.querySelector('[role="status"]');
    opener.addEventListener('click', () => {
        message.textContent = '';
        dialog.showModal();
        const field = form.querySelector('input[type="number"]:not(:disabled), select:not(:disabled), textarea:not(:disabled)');
        if (field) field.focus();
    });
    dialog.querySelector('.item-offer-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
        const box = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right ||
            event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
    });
    // Native dialog provides focus trapping and Escape dismissal.
    dialog.addEventListener('close', () => opener.focus());
    form.addEventListener('submit', event => {
        if (form.dataset.authenticated !== 'true') {
            event.preventDefault();
            window.location.assign(form.dataset.loginUrl);
            return;
        }
        if (!form.reportValidity() || form.querySelector('[type="submit"]').disabled) {
            event.preventDefault();
            return;
        }
        // Native CSRF-protected POST: matching validates/saves, then redirects to
        // its sent requests dashboard. Never infer success before that response.
        form.querySelector('[type="submit"]').disabled = true;
        message.textContent = 'Sending request…';
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted) window.location.reload();
    });
})();
