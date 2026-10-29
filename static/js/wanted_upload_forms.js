/* Wanted CRUD: server-confirmed Create/Edit and optimistic Delete with rollback. */
(() => {
    const dialogs = '#create-wanted-modal, #edit-wanted-modal, #delete-wanted-modal, #item-offer-modal';
    const pending = new WeakSet();
    const savedCreates = new WeakMap();
    let deleting = false, cachedBoard;
    const notify = (message, type = 'success') => window.YellovedToast?.show({
        title: type === 'error' ? 'Unable to complete action' : 'Success', message, type,
    });
    const boardHTML = async url => {
        const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'text/html'}});
        if (!response.ok || response.redirected) throw new Error('Unable to refresh the board. Please retry.');
        const html = await response.text();
        if (!new DOMParser().parseFromString(html, 'text/html').querySelector('main.wanted-page')) {
            throw new Error('Unable to refresh the board. Please retry.');
        }
        cachedBoard = html;
        return html;
    };
    const renderBoard = (html, url, omittedDetail) => {
        const page = new DOMParser().parseFromString(html, 'text/html');
        const current = document.querySelector('main.wanted-page, main.wanted-detail-page');
        const main = document.importNode(page.querySelector('main.wanted-page'), true);
        window.YellovedWantedBoard?.destroy();
        if (omittedDetail) main.querySelectorAll('.wanted-card').forEach(card => {
            if (card.querySelector('.wanted-card-link')?.getAttribute('href') === omittedDetail) card.remove();
        });
        document.querySelectorAll(dialogs).forEach(node => node.remove());
        current.replaceWith(main);
        main.after(...[...page.querySelectorAll(dialogs)].map(node => document.importNode(node, true)));
        document.title = page.title;
        history.replaceState(history.state, '', url);
        window.YellovedWantedBoard?.init();
        window.dispatchEvent(new Event('wanted:mounted'));
        return main;
    };
    const post = async form => {
        const response = await fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin',
            headers: {Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest'}});
        if (response.redirected) throw new Error('Your session may have expired. Sign in again in another tab, then retry. Your details are still here.');
        if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
            if (response.status === 403) throw new Error('Your security token has expired or access was denied. Refresh this page and sign in again before retrying.');
            if (response.status === 404) throw new Error('This wanted post is no longer available. Return to the board and refresh.');
            throw new Error('Unable to confirm this action. Check your connection or sign in again, then retry.');
        }
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(data.message || 'Unable to complete this action. Your details are kept; please retry.');
            error.fields = data.errors;
            error.status = response.status;
            throw error;
        }
        return data;
    };
    const showErrors = (form, errors) => {
        let first;
        Object.entries(errors).forEach(([name, messages]) => {
            const field = [...form.querySelectorAll('[data-upload-field]')].find(node => node.dataset.uploadField === name);
            const input = field?.querySelector('input, select, textarea');
            if (input) { input.setAttribute('aria-invalid', 'true'); first ||= input; }
            const container = field || form.querySelector('[data-upload-form-errors]');
            messages.forEach(error => {
                const node = document.createElement('small');
                node.className = 'form-error'; node.dataset.serverError = ''; node.textContent = error.message;
                container.append(node);
            });
        });
        first?.focus();
    };
    const removeOptimistically = async form => {
        const main = document.querySelector('main.wanted-detail-page');
        const previous = {main, dialogs: [...document.querySelectorAll(dialogs)], url: location.href, title: document.title};
        const modal = form.closest('dialog');
        let committed = false;
        deleting = true;
        modal.close();
        // Prefetch makes the board available before deletion is confirmed.
        if (cachedBoard) renderBoard(cachedBoard, form.dataset.boardUrl, form.dataset.detailUrl).inert = true;
        else {
            main.querySelector('.wanted-detail-card').hidden = true;
            main.setAttribute('aria-busy', 'true');
            const status = document.createElement('p');
            status.dataset.deletePending = ''; status.setAttribute('role', 'status'); status.textContent = 'Deleting wanted post…';
            main.append(status);
        }
        try {
            const data = await post(form);
            committed = true;
            renderBoard(await boardHTML(data.board_url), data.board_url);
            notify(data.message);
            window.scrollTo({top: 0, behavior: 'instant'});
        } catch (error) {
            let confirmedPresent = false;
            if (!committed) {
                try {
                    const check = await fetch(form.dataset.deletionStateUrl, {credentials: 'same-origin', headers: {Accept: 'application/json'}, cache: 'no-store'});
                    if (check.ok && !check.redirected && (check.headers.get('Content-Type') || '').includes('application/json')) {
                        const state = (await check.json()).state;
                        committed = state === 'deleted';
                        confirmedPresent = state === 'present';
                    }
                } catch (_) { /* An unknown outcome must stay unknown, never pretend rollback succeeded. */ }
            }
            if (!committed) {
                document.querySelectorAll(dialogs).forEach(node => node.remove());
                const current = document.querySelector('main.wanted-page, main.wanted-detail-page');
                if (current !== previous.main) current.replaceWith(previous.main);
                previous.main.after(...previous.dialogs);
                previous.main.querySelector('.wanted-detail-card').hidden = !confirmedPresent;
                previous.main.querySelector('[data-delete-pending]')?.remove();
                previous.main.removeAttribute('aria-busy');
                document.title = previous.title;
                history.replaceState(history.state, '', previous.url);
                window.dispatchEvent(new Event('wanted:mounted'));
                modal.showModal();
                const message = confirmedPresent ? error.message
                    : 'Unable to confirm whether this post was deleted. Retry Delete to safely confirm the result; it will not delete anything twice.';
                showErrors(form, {__all__: [{message}]});
                notify(message, 'error');
            } else {
                try {
                    renderBoard(await boardHTML(form.dataset.boardUrl), form.dataset.boardUrl);
                    notify('Your wanted post has been deleted.');
                    return;
                } catch (_) { /* Deletion is confirmed even when refreshing still fails. */ }
                // Never restore a post after the server confirmed its deletion.
                if (cachedBoard) renderBoard(cachedBoard, form.dataset.boardUrl, form.dataset.detailUrl);
                else {
                    previous.main.querySelector('[data-delete-pending]').textContent = 'Post deleted. Open the board to refresh the list.';
                    previous.main.removeAttribute('aria-busy');
                }
                notify('Your post was deleted, but the board could not refresh. Open the board to refresh the list.', 'error');
            }
        } finally { deleting = false; }
    };
    document.addEventListener('submit', async event => {
        const form = event.target;
        if (!form.matches('[data-ajax-upload], [data-ajax-delete]')) return;
        event.preventDefault();
        if (pending.has(form) || deleting || !form.reportValidity()) return;
        pending.add(form);
        const modal = form.closest('dialog');
        modal.dataset.submitting = 'true'; form.setAttribute('aria-busy', 'true');
        form.querySelectorAll('[data-server-error]').forEach(node => node.remove());
        form.querySelectorAll('[aria-invalid]').forEach(node => node.removeAttribute('aria-invalid'));
        const buttons = [...modal.querySelectorAll('button')];
        const states = buttons.map(button => button.disabled);
        const submit = form.querySelector('[type=submit]');
        const label = submit.textContent;
        buttons.forEach(button => { button.disabled = true; }); submit.textContent = 'Saving…';
        try {
            if (form.matches('[data-ajax-delete]')) await removeOptimistically(form);
            else {
                const data = savedCreates.get(form) || await post(form);
                if (data.detail_html) {
                    document.querySelector('.wanted-detail-card').innerHTML = data.detail_html;
                    form.elements.revision.value = data.revision;
                    document.querySelector('[data-delete-title]').textContent = data.title;
                    document.title = `${data.title} | Yelloved`;
                    modal.close();
                } else {
                    savedCreates.set(form, data);
                    renderBoard(await boardHTML(data.board_url), data.board_url);
                }
                notify(data.message);
            }
        } catch (error) {
            showErrors(form, error.fields || {__all__: [{message: savedCreates.has(form)
                ? 'Your post was saved. Click Refresh board to refresh the list without creating another post.' : error.message}]});
            if (!error.fields || error.status === 429) notify(error.message, 'error');
        } finally {
            pending.delete(form); modal.dataset.submitting = 'false'; form.removeAttribute('aria-busy');
            buttons.forEach((button, index) => { button.disabled = states[index]; });
            submit.textContent = savedCreates.has(form) && form.isConnected ? 'Refresh board' : label;
            if (savedCreates.has(form)) form.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(input => { input.disabled = true; });
        }
    });
    const modalControls = [
        ['create-wanted-modal', '[data-open-wanted-modal]', '[data-close-wanted-modal]'],
        ['edit-wanted-modal', '[data-open-edit-wanted-modal]', '[data-close-edit-wanted-modal]'],
        ['delete-wanted-modal', '[data-open-delete-wanted-modal]', '[data-close-delete-wanted-modal]'],
    ];
    document.addEventListener('click', event => {
        for (const [id, open, close] of modalControls) {
            const modal = document.getElementById(id);
            if (!modal) continue;
            if (event.target.closest(open)) { event.preventDefault(); if (!deleting) modal.showModal(); }
            if ((event.target.closest(close) || event.target === modal) && modal.dataset.submitting !== 'true') modal.close();
        }
    });
    document.addEventListener('cancel', event => {
        if (event.target.matches(dialogs) && event.target.dataset.submitting === 'true') event.preventDefault();
    }, true);
    document.querySelectorAll('dialog[data-auto-open=true]').forEach(modal => modal.showModal());
    const deletion = document.querySelector('[data-ajax-delete]');
    if (deletion) boardHTML(deletion.dataset.boardUrl).catch(() => { /* The optimistic placeholder remains available. */ });
})();
