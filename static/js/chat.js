/* Chat: asynchronous history, idempotent sends, and optimistic message changes. */
(() => {
    const app = document.querySelector('[data-chat-app]');
    if (!app) return;
    const list = app.querySelector('[data-chat-messages]');
    const compose = app.querySelector('[data-chat-compose]');
    const status = app.querySelector('[data-chat-status]');
    const fileInput = compose?.querySelector('[data-chat-file]');
    let restoredFile = null, composerTouched = false, drafts;
    const selectedFile = () => fileInput?.files[0] || restoredFile;
    const updateCompose = () => {
        if (!compose) return;
        const file = selectedFile();
        const body = compose.elements.body;
        if (body.style) {
            body.style.height = 'auto';
            body.style.height = `${Math.min(body.scrollHeight, 140)}px`;
        }
        compose.querySelector('[type=submit]').disabled = (!compose.elements.body.value.trim() && !file) || compose.elements.body.value.length > 1000;
        const preview = compose.querySelector('[data-chat-file-preview]');
        if (preview) {preview.hidden = !file; compose.querySelector('[data-chat-file-name]').textContent = file?.name || '';}
    };
    const older = app.querySelector('[data-chat-older]');
    const dialog = document.querySelector('[data-chat-dialog]');
    const actionForm = dialog.querySelector('form');
    const entries = new Map(), outgoing = new Map(), changing = new Set(), deferredRows = new Map();
    let timer, stopped = false, refreshing = false, actionTarget, threadSnapshot, navigation = 0;
    let syncCursor = null, initialVersion = null, acknowledging = false, threadsLoading = false, threadDepth = 1;
    const moreThreads = app.querySelector('[data-chat-more-threads]');
    const notify = (message, type = 'error') => window.YellovedToast?.show({title: type === 'error' ? 'Chat' : 'Success', message, type});
    const csrf = () => compose?.querySelector('[name=csrfmiddlewaretoken]').value;
    const request = async (url, data) => {
        return window.YellovedChatHTTP.request(url, data, csrf());
    };
    const node = (tag, text, className) => {
        const element = document.createElement(tag);
        // Messages and names are plain text, never executable HTML.
        if (text !== undefined) element.textContent = text;
        if (className) element.className = className;
        return element;
    };
    const button = (text, action, id) => {
        const element = node('button', text, 'chat-app-secondary');
        element.type = 'button'; element.dataset.chatAction = action; element.dataset.messageId = id;
        return element;
    };
    const render = (forceBottom = false) => {
        if (!list) return;
        const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 90;
        const rows = [...entries.values(), ...[...outgoing.values()].filter(row => !entries.has(row.id))]
            .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
        const fragment = document.createDocumentFragment();
        if (!rows.length) fragment.append(node('p', 'No messages yet. Say hello!', 'chat-app-muted'));
        for (const row of rows) {
            const bubble = node('article', undefined, `chat-app-message${row.mine ? ' is-mine' : ''}`);
            bubble.dataset.messageId = row.id;
            bubble.append(node('p', row.deleted ? 'Message deleted.' : row.body));
            if (!row.deleted && (row.attachment || row.file)) {
                const attachment = row.attachment;
                const link = node(attachment ? 'a' : 'span', attachment?.name || row.file.name, 'chat-app-attachment');
                if (attachment) {link.href = attachment.url; link.setAttribute('download', '');}
                bubble.append(link);
            }
            const time = node('time', new Date(row.created_at).toLocaleString([], {dateStyle: 'short', timeStyle: 'short'}));
            time.dateTime = row.created_at; bubble.append(time);
            const controls = node('div', undefined, 'chat-app-message-actions');
            if (row.state === 'failed') {
                controls.append(node('small', 'Not sent.', 'chat-app-required'), button('Retry', 'retry', row.id), button('Discard', 'discard', row.id));
            } else if (row.state === 'sending' || changing.has(row.id)) {
                controls.append(node('small', row.state === 'sending' ? 'Sending…' : 'Saving…'));
            } else if (row.mine && !row.deleted) controls.append(button('Edit', 'edit', row.id), button('Delete', 'delete', row.id));
            bubble.append(controls); fragment.append(bubble);
        }
        list.replaceChildren(fragment);
        if (nearBottom || forceBottom) list.scrollTop = list.scrollHeight;
    };
    const merge = (rows, delta = false) => {
        let changed = false;
        for (const row of rows) {
            if (changing.has(row.id)) {deferredRows.set(row.id, row); continue;}
            if (outgoing.delete(row.id)) {changed = true; drafts?.schedule();}
            const previous = entries.get(row.id);
            // An edit to unloaded older history must not skip the pages between
            // that message and the current window when loading older messages.
            if (delta && !previous && row.created_version <= initialVersion) continue;
            if (previous && (Number.isFinite(row.version) && Number.isFinite(previous.version)
                ? row.version < previous.version : Date.parse(row.revision) < Date.parse(previous.revision))) continue;
            if (!previous || previous.revision !== row.revision) {entries.set(row.id, row); changed = true;}
        }
        return changed;
    };
    const acknowledge = async () => {
        if (!list || stopped || acknowledging || document.hidden || document.hasFocus?.() === false ||
            list.scrollHeight - list.scrollTop - list.clientHeight >= 90) return;
        acknowledging = true;
        try {
            const unread = [...entries.values()].filter(row => row.unread);
            for (let offset = 0; offset < unread.length; offset += 50) {
                const batch = unread.slice(offset, offset + 50), data = new FormData();
                batch.forEach(row => data.append('ids', row.id));
                await request(app.dataset.readUrl, data);
                if (stopped) return;
                batch.forEach(row => {row.unread = false;});
            }
            if (unread.length) window.dispatchEvent(new Event('chat:read'));
        } finally {acknowledging = false;}
    };
    const loadMessages = async (previousPage = false) => {
        if (!list) return;
        const url = new URL(app.dataset.messagesUrl, location.origin);
        if (previousPage && entries.size) {
            const first = [...entries.values()].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))[0];
            url.searchParams.set('before', first.id);
        }
        const firstLoad = syncCursor === null;
        let more;
        do {
            if (!previousPage && !firstLoad) url.searchParams.set('after', syncCursor);
            const result = await request(url);
            if (stopped) return;
            const height = list.scrollHeight, top = list.scrollTop;
            if (merge(result.messages, !previousPage && !firstLoad)) render(firstLoad);
            if (!entries.size) render();
            if (previousPage) list.scrollTop = top + list.scrollHeight - height;
            if (previousPage || firstLoad) older.hidden = !result.has_older;
            if (!previousPage) {
                syncCursor = result.sync_cursor ?? 0;
                if (firstLoad) initialVersion = syncCursor;
            }
            more = !previousPage && !firstLoad && result.has_more_changes;
        } while (more && !stopped);
        status.textContent = '';
        await acknowledge();
    };
    const loadThreads = async () => {
        if (threadsLoading || stopped) return;
        threadsLoading = true;
        try {
        const rows = new Map(); let cursor;
        for (let page = 0; page < threadDepth; page++) {
            const url = new URL(app.dataset.inboxUrl, location.origin);
            if (cursor) url.searchParams.set('cursor', cursor);
            const result = await request(url);
            if (stopped) return;
            result.conversations.forEach(row => rows.set(row.peer_id, row));
            cursor = result.next_cursor;
            if (!cursor) break;
        }
        if (moreThreads) moreThreads.hidden = !cursor;
        const conversations = [...rows.values()], snapshot = JSON.stringify(conversations);
        if (snapshot === threadSnapshot) return;
        threadSnapshot = snapshot;
        const nav = app.querySelector('[data-chat-threads]'), fragment = document.createDocumentFragment();
        if (!conversations.length) fragment.append(node('p', 'No conversations yet.', 'chat-app-muted'));
        for (const row of conversations) {
            const link = node('a', undefined, `chat-app-thread${String(row.peer_id) === app.dataset.peerId ? ' is-active' : ''}`);
            link.href = row.url; link.append(node('strong', row.name), node('small', row.preview)); fragment.append(link);
        }
        nav.replaceChildren(fragment);
        } finally {threadsLoading = false;}
    };
    const refresh = async (explicit = false) => {
        if (refreshing || stopped) return;
        refreshing = true;
        try { await Promise.all([loadMessages(), loadThreads()]); }
        catch (error) {
            if (stopped) return;
            if (status) status.textContent = 'Reconnecting… Your current conversation is still shown. We will retry automatically.';
            if (explicit) notify(error.message);
        } finally {refreshing = false;}
    };
    const send = async row => {
        if (row.state === 'sending') return;
        const startedOn = navigation;
        row.state = 'sending'; outgoing.set(row.id, row); render(true);
        await drafts?.save();
        if (stopped || startedOn !== navigation) return;
        const data = new FormData(); data.set('body', row.body); data.set('client_id', row.id);
        if (row.file) data.set('attachment', row.file);
        try {
            const result = await request(app.dataset.messagesUrl, data);
            if (stopped || startedOn !== navigation) return;
            const alreadyDelivered = initialVersion !== null && result.entry.created_version <= initialVersion && !entries.has(result.entry.id);
            if (!alreadyDelivered) entries.set(result.entry.id, result.entry);
            else notify('This message was already delivered. Load older messages to find it.', 'success');
            outgoing.delete(row.id); render(true);
            drafts?.schedule();
            loadThreads().catch(() => {});
        } catch (error) {
            if (stopped || startedOn !== navigation) return;
            if (!entries.has(row.id)) {row.state = 'failed'; render(); drafts?.schedule(); notify(error.message);}
        }
    };
    if (compose) {
        const input = compose.elements.body, submit = compose.querySelector('[type=submit]');
        input.addEventListener('input', () => {composerTouched = true; updateCompose(); drafts?.schedule();});
        fileInput?.addEventListener('change', () => {
            restoredFile = null; composerTouched = true;
            const file = fileInput.files[0];
            if (file && file.size > 5 * 1024 * 1024) {notify('Attachments must not exceed 5 MB.'); fileInput.value = '';}
            updateCompose();
            drafts?.schedule();
        });
        compose.querySelector('[data-chat-choose-file]')?.addEventListener('click', () => fileInput.click());
        compose.querySelector('[data-chat-remove-file]')?.addEventListener('click', () => {fileInput.value = ''; restoredFile = null; composerTouched = true; updateCompose(); drafts?.schedule();});
        compose.addEventListener('submit', event => {
            event.preventDefault();
            const file = selectedFile();
            if ((!input.value.trim() && !file) || !compose.reportValidity()) return;
            const row = {id: crypto.randomUUID(), body: input.value.trim(), file, mine: true, deleted: false, created_at: new Date().toISOString()};
            composerTouched = true; input.value = ''; restoredFile = null; if (fileInput) fileInput.value = ''; updateCompose(); input.focus(); send(row);
        });
        updateCompose();
    }
    app.addEventListener('click', event => {
        if (event.target.closest('[data-chat-more-threads]') && !threadsLoading) {
            threadDepth++; moreThreads.disabled = true;
            loadThreads().catch(error => {threadDepth--; notify(error.message);}).finally(() => {moreThreads.disabled = false;});
        }
        if (event.target.closest('[data-chat-older]')) {
            older.disabled = true;
            loadMessages(true).catch(error => notify(error.message)).finally(() => {older.disabled = false;});
        }
        const control = event.target.closest('[data-chat-action]');
        if (!control) return;
        const id = control.dataset.messageId, action = control.dataset.chatAction;
        if (action === 'retry') {const row = outgoing.get(id); if (row) send(row); return;}
        if (action === 'discard') {outgoing.delete(id); render(); drafts?.schedule(); return;}
        const row = entries.get(id);
        if (!row || changing.has(id)) return;
        actionTarget = {row, action};
        const editing = action === 'edit';
        dialog.querySelector('[data-chat-dialog-title]').textContent = editing ? 'Edit message' : 'Delete message?';
        dialog.querySelector('[data-chat-edit-fields]').hidden = !editing;
        dialog.querySelector('[data-chat-delete-text]').hidden = editing;
        dialog.querySelector('[data-chat-confirm]').textContent = editing ? 'Save' : 'Delete';
        actionForm.elements.body.disabled = !editing;
        actionForm.elements.body.value = row.body;
        dialog.showModal();
    });
    dialog.querySelector('[data-chat-cancel]').addEventListener('click', () => dialog.close());
    actionForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (!actionForm.reportValidity() || !actionTarget) return;
        const {row, action} = actionTarget;
        if (changing.has(row.id)) return;
        const body = actionForm.elements.body.value.trim();
        if (action === 'edit' && !body) return;
        const data = new FormData(); data.set('revision', row.revision); if (action === 'edit') data.set('body', body);
        const optimistic = {...row, body: action === 'edit' ? body : '', deleted: action === 'delete'};
        changing.add(row.id); entries.set(row.id, optimistic); dialog.close(); render();
        try {
            const result = await request(action === 'edit' ? row.edit_url : row.delete_url, data);
            if (stopped) return;
            entries.set(row.id, result.entry); notify(result.message, 'success');
        } catch (error) {if (!stopped) {entries.set(row.id, row); notify(error.message);}}
        finally {
            changing.delete(row.id);
            if (!stopped) {
                if (deferredRows.has(row.id)) {merge([deferredRows.get(row.id)]); deferredRows.delete(row.id);}
                render(); refresh();
            }
        }
    });
    const tick = async () => {
        if (stopped) return;
        if (!document.hidden) await refresh();
        if (!stopped) timer = setTimeout(tick, 5000);
    };
    if (compose) {
        drafts = window.YellovedChatDrafts?.create({owner: window.YellovedChatHTTP.userId, peer: app.dataset.peerId,
            snapshot: () => ({composer: {body: compose.elements.body.value, file: selectedFile()},
                outgoing: [...outgoing.values()].map(row => ({...row, state: 'failed'}))}),
            restore: saved => {
                if (stopped) return;
                if (!composerTouched && saved.composer) {compose.elements.body.value = saved.composer.body || ''; restoredFile = saved.composer.file || null; updateCompose();}
                for (const row of saved.outgoing || []) if (!entries.has(row.id)) outgoing.set(row.id, {...row, state: 'failed'});
                render();
                // A response may have been lost before leaving the page. Resolve
                // stored tokens against the server before offering Retry again.
                const ids = [...outgoing.keys()];
                (async () => {
                    for (let offset = 0; offset < ids.length; offset += 50) {
                        const url = new URL(app.dataset.messagesUrl, location.origin);
                        url.searchParams.set('resolve', ids.slice(offset, offset + 50).join(','));
                        const result = await request(url);
                        if (stopped) return;
                        let resolved = false;
                        for (const row of result.messages) {
                            if (outgoing.delete(row.id)) resolved = true;
                            // Resolve confirms delivery only. It must never add an
                            // old unloaded message to the current history window.
                            if (entries.has(row.id)) merge([row]);
                        }
                        if (resolved) {drafts?.schedule(); render();}
                    }
                })().catch(error => {if (!stopped) notify(error.message);});
                if (saved.composer?.body || saved.composer?.file || saved.outgoing?.length) notify('Your draft and unsent messages were restored on this browser.', 'success');
            }, onError: message => notify(`${message} Keep this tab open or copy your text before leaving.`)});
    }
    window.addEventListener('beforeunload', event => {
        if (!window.YellovedChatHTTP.blocked && drafts?.dirty) {event.preventDefault(); event.returnValue = '';}
    });
    window.addEventListener('focus', () => refresh());
    list?.addEventListener('scroll', () => {acknowledge().catch(() => {});});
    window.addEventListener('chat:session-ended', event => {
        stopped = true; clearTimeout(timer); entries.clear(); outgoing.clear(); changing.clear(); deferredRows.clear();
        drafts?.stop(); restoredFile = null;
        if (compose) {compose.elements.body.value = ''; if (fileInput) fileInput.value = '';}
        actionForm.elements.body.value = ''; dialog.close();
        const message = node('p', event.detail.message, 'chat-app-status');
        const reload = node('a', 'Reload Chat', 'chat-app-secondary'); reload.href = '/chat/';
        app.replaceChildren(message, reload);
    });
    window.addEventListener('pagehide', () => {
        stopped = true; navigation++; clearTimeout(timer);
        // A restored browser snapshot must not keep an aborted request Sending.
        // Keep its original token: the next poll or Retry can confirm delivery.
        let interrupted = false;
        for (const row of outgoing.values()) {
            if (row.state === 'sending') {row.state = 'failed'; interrupted = true;}
        }
        if (interrupted) drafts?.schedule();
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted && !window.YellovedChatHTTP.blocked) {stopped = false; render(); tick();}
    });
    refresh(true).finally(() => {if (!stopped) timer = setTimeout(tick, 5000);});
})();
