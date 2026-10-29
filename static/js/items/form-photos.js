(() => {
    const root = document.querySelector('.item-form-page');
    const input = root?.querySelector('input[name="images"]');
    if (!input) return;
    const preview = root.querySelector('#item-new-photo-preview');
    const feedback = root.querySelector('.item-photo-feedback');
    let files = [];
    let urls = [];
    function render() {
        urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
        preview.replaceChildren();
        const transfer = new DataTransfer();
        files.forEach((file, index) => {
            transfer.items.add(file);
            const tile = document.createElement('div'); tile.className = 'item-photo-tile';
            const image = document.createElement('img');
            const url = URL.createObjectURL(file); urls.push(url);
            image.src = url; image.alt = `New photo ${index + 1}`;
            const remove = document.createElement('button'); remove.type = 'button';
            remove.textContent = 'Remove'; remove.setAttribute('aria-label', `Remove new photo ${index + 1}`);
            remove.addEventListener('click', () => { files.splice(index, 1); render(); });
            tile.append(image, remove); preview.append(tile);
        });
        input.files = transfer.files;
        const kept = [...root.querySelectorAll('input[name="delete_images"]')].filter(box => !box.checked).length;
        const tooMany = kept + files.length > 5;
        input.setCustomValidity(tooMany ? 'An item can have up to 5 photos. Remove a photo first.' : '');
        feedback.textContent = tooMany ? input.validationMessage : (files.length ? `${files.length} new photo${files.length === 1 ? '' : 's'} selected. ${kept ? 'Existing photos stay first.' : 'The first photo is used as the thumbnail.'}` : '');
    }
    input.addEventListener('change', () => {
        const incoming = [...input.files];
        const invalid = incoming.some(file => !/\.(jpe?g|png|webp)$/i.test(file.name) || file.size > 5 * 1024 * 1024);
        if (invalid) {
            render(); feedback.textContent = 'Use JPG, PNG, or WebP photos up to 5 MB each.'; return;
        }
        files.push(...incoming); render();
    });
    root.querySelectorAll('input[name="delete_images"]').forEach(box => box.addEventListener('change', render));
    window.addEventListener('pagehide', () => urls.forEach(url => URL.revokeObjectURL(url)));
})();
