/* Shared navbar chat preview: only the current user's three latest conversations. */
(() => {
    const root = document.querySelector('[data-chat-notifications]');
    if (!root) return;
    const trigger = root.querySelector('button'), badge = root.querySelector('[data-chat-unread]');
    const preview = root.querySelector('[data-chat-preview]');
    let pending = false, stopped = false, timer, snapshot;
    const refresh = async () => {
        if (pending || stopped || document.hidden) return;
        pending = true;
        try {
            const data = await window.YellovedChatHTTP.request(root.dataset.chatNotificationsUrl);
            if (stopped) return;
            badge.hidden = !data.unread; badge.textContent = data.unread > 99 ? '99+' : String(data.unread);
            trigger.setAttribute('aria-label', data.unread ? `Chat, ${data.unread} unread messages` : 'Chat');
            const next = JSON.stringify(data.conversations);
            if (snapshot === next) return;
            snapshot = next;
            const fragment = document.createDocumentFragment();
            for (const row of data.conversations) {
                const link = document.createElement('a'); link.className = 'nav-chat-preview-row'; link.href = row.url;
                const avatar = document.createElement('span'); avatar.className = 'nav-chat-avatar'; avatar.textContent = row.initial;
                const text = document.createElement('span');
                const name = document.createElement('strong'); name.textContent = row.name;
                const message = document.createElement('small'); message.textContent = row.preview;
                text.append(name, message); link.append(avatar, text);
                if (row.unread) {const count = document.createElement('span'); count.className = 'nav-chat-row-count'; count.textContent = row.unread > 99 ? '99+' : String(row.unread); link.append(count);}
                fragment.append(link);
            }
            if (!data.conversations.length) {const empty = document.createElement('p'); empty.className = 'nav-chat-empty'; empty.textContent = 'No conversations yet.'; fragment.append(empty);}
            preview.replaceChildren(fragment);
        } catch (_) {
            if (stopped) return;
            if (!snapshot) {preview.textContent = 'Unable to load recent chats. Open Chat to try again.';}
        } finally {pending = false;}
    };
    const tick = async () => {await refresh(); if (!stopped) timer = setTimeout(tick, 10000);};
    trigger.addEventListener('click', refresh);
    window.addEventListener('chat:read', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('chat:session-ended', () => {
        stopped = true; clearTimeout(timer); snapshot = undefined;
        badge.hidden = true; badge.textContent = ''; trigger.setAttribute('aria-label', 'Chat');
        preview.textContent = 'Your chat session changed. Open Chat to continue.';
    });
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('pagehide', () => {stopped = true; clearTimeout(timer);});
    window.addEventListener('pageshow', event => {if (event.persisted) {stopped = false; tick();}});
    tick();
})();
