(() => {
    const form = document.getElementById('cart-selection-form');
    if (!form) return;
    const all = form.querySelector('#cart-select-all');
    const boxes = [...form.querySelectorAll('.cart-item-checkbox')];
    const checkout = form.querySelector('.cart-checkout-button');
    const remove = form.querySelector('.cart-remove-selected');
    const hint = form.querySelector('.cart-selection-hint');
    const rupiah = value => 'Rp' + new Intl.NumberFormat('id-ID', {maximumFractionDigits: 0}).format(value);
    function syncToggle(toggle, members) {
        const count = members.filter(box => box.checked).length;
        toggle.checked = members.length > 0 && count === members.length;
        toggle.indeterminate = count > 0 && count < members.length;
    }
    function update() {
        const selected = boxes.filter(box => box.checked);
        const invalid = selected.some(box => box.closest('[data-cart-entry]').dataset.eligible !== 'true');
        const total = selected.reduce((sum, box) => sum + Number(box.closest('[data-cart-entry]').dataset.price), 0);
        form.querySelectorAll('[data-selected-count], [data-checkout-count]').forEach(node => node.textContent = selected.length);
        form.querySelectorAll('[data-selected-total]').forEach(node => node.textContent = rupiah(total));
        checkout.disabled = !selected.length || invalid;
        remove.disabled = !selected.length;
        hint.hidden = selected.length > 0 && !invalid;
        hint.textContent = invalid ? 'Remove unavailable items from your selection before checkout.' : 'Select at least one item to check out.';
        syncToggle(all, boxes);
        form.querySelectorAll('.cart-seller-group').forEach(group => syncToggle(group.querySelector('.cart-select-seller'), [...group.querySelectorAll('.cart-item-checkbox')]));
    }
    all.addEventListener('change', () => { boxes.forEach(box => box.checked = all.checked); update(); });
    form.querySelectorAll('.cart-select-seller').forEach(toggle => toggle.addEventListener('change', () => {
        toggle.closest('.cart-seller-group').querySelectorAll('.cart-item-checkbox').forEach(box => box.checked = toggle.checked);
        update();
    }));
    boxes.forEach(box => box.addEventListener('change', update));
    form.addEventListener('submit', event => {
        if (event.submitter === checkout && checkout.disabled) event.preventDefault();
    });
    window.addEventListener('pageshow', update);
    update();
})();
