/* All Chat AJAX requests are bound to the account/session that rendered this tab. */
(() => {
    const root = document.querySelector('[data-chat-session]');
    if (!root) return;
    const identity = root.dataset.chatSession, controllers = new Set();
    let blocked = false;
    const stop = message => {
        if (blocked) return;
        blocked = true;
        controllers.forEach(controller => controller.abort());
        window.dispatchEvent(new CustomEvent('chat:session-ended', {detail: {message}}));
    };
    const request = async (url, data, csrf) => {
        if (blocked) throw new Error('Reload Chat to continue with your current account.');
        const controller = new AbortController(); controllers.add(controller);
        try {
            const response = await fetch(url, {method: data ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
                signal: controller.signal, headers: {Accept: 'application/json', 'X-Chat-Session': identity,
                    ...(data ? {'X-CSRFToken': csrf} : {})}, body: data});
            if (blocked) throw new Error('Chat session ended.');
            if (response.redirected || response.status === 401 || response.status === 403 ||
                (response.headers.get('X-Chat-Session') && response.headers.get('X-Chat-Session') !== identity)) {
                const message = 'Your account or session changed. Chat was cleared. Reload Chat and sign in again to continue.';
                stop(message); throw new Error(message);
            }
            if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw new Error('Unable to connect. Please retry.');
            const result = await response.json();
            if (blocked) throw new Error('Chat session ended.');
            if (result.code === 'chat_session_changed') {stop(result.message); throw new Error(result.message);}
            if (!response.ok) throw new Error(result.message || 'Unable to complete this action. Please retry.');
            return result;
        } finally {controllers.delete(controller);}
    };
    window.YellovedChatHTTP = {request, get blocked() {return blocked;}, identity, userId: root.dataset.chatUser};
})();
