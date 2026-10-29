/* Protect unsaved Wanted Create/Edit changes; server-confirmed saves reset the baseline. */
(() => {
    const baselines = new WeakMap();
    const forms = () => [...document.querySelectorAll('#create-wanted-modal [data-ajax-upload], #edit-wanted-modal [data-ajax-upload]')];
    const values = form => [...form.elements].filter(field => field.name && field.type !== 'hidden' && field.type !== 'submit')
        .map(field => [field.name, field.value]);
    const markSaved = form => baselines.set(form, values(form));
    const dirty = form => baselines.has(form) && JSON.stringify(values(form)) !== JSON.stringify(baselines.get(form));
    const openDirty = () => forms().find(form => form.closest('dialog').open && dirty(form));
    let asking = false;
    const discard = form => {
        form.reset();
        for (const [name, value] of baselines.get(form)) form.elements.namedItem(name).value = value;
        form.querySelectorAll('[data-server-error]').forEach(node => node.remove());
        form.closest('dialog').close();
    };
    const confirm = async form => {
        if (asking) return false;
        asking = true;
        const dialog = document.createElement('dialog');
        dialog.className = 'wanted-modal';
        dialog.setAttribute('aria-labelledby', 'wanted-unsaved-title');
        dialog.innerHTML = '<h2 id="wanted-unsaved-title">Discard unsaved changes?</h2><p>Your changes have not been saved.</p><div class="wanted-modal-actions"><button type="button" class="wanted-button wanted-action-secondary" data-keep-editing>Keep editing</button><button type="button" class="wanted-button wanted-action-offer" data-discard-changes>Discard changes</button></div>';
        document.body.append(dialog);
        return new Promise(resolve => {
            const finish = accepted => {dialog.close(); dialog.remove(); asking = false; if (accepted) discard(form); resolve(accepted);};
            dialog.querySelector('[data-keep-editing]').addEventListener('click', () => finish(false));
            dialog.querySelector('[data-discard-changes]').addEventListener('click', () => finish(true));
            dialog.addEventListener('cancel', event => {event.preventDefault(); finish(false);});
            dialog.showModal();
        });
    };
    const init = () => forms().forEach(form => {if (!baselines.has(form)) markSaved(form);});
    document.addEventListener('click', event => {
        const close = event.target.closest('[data-close-wanted-modal], [data-close-edit-wanted-modal]');
        const modal = close?.closest('dialog') || (event.target.matches('#create-wanted-modal, #edit-wanted-modal') ? event.target : null);
        const form = modal?.querySelector('[data-ajax-upload]');
        if (!form || modal.dataset.submitting === 'true' || !dirty(form)) return;
        event.preventDefault(); event.stopImmediatePropagation(); confirm(form);
    }, true);
    document.addEventListener('cancel', event => {
        const modal = event.target;
        if (!modal.matches('#create-wanted-modal, #edit-wanted-modal')) return;
        const form = modal.querySelector('[data-ajax-upload]');
        if (modal.dataset.submitting !== 'true' && dirty(form)) {event.preventDefault(); event.stopImmediatePropagation(); confirm(form);}
    }, true);
    window.addEventListener('beforeunload', event => {if (openDirty()) {event.preventDefault(); event.returnValue = '';}});
    window.addEventListener('wanted:mounted', init);
    window.YellovedWantedUnsaved = {markSaved, dirty};
    init();
})();
