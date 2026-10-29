(() => {
    if (!document.querySelector('.explore-page')) return;
    // Only exact Items UI messages are translated; user content is never replaced.
    const messages = new Map([
        ['Item berhasil ditambahkan.', 'Item added successfully.'],
        ['Item berhasil diperbarui.', 'Item updated successfully.'],
        ['Item berhasil dihapus.', 'Item deleted successfully.'],
    ]);
    document.querySelectorAll('.site-toast-copy small').forEach(element => {
        const translated = messages.get(element.textContent.trim());
        if (translated) element.textContent = translated;
    });
})();
