/* Shared Activity preview; data always belongs to the session rendered in this tab. */
(() => {
    const root = document.querySelector('[data-activity-preview]');
    if (!root) return;
    let busy = false, stopped = false, timer;
    const refresh = async () => {
        if (busy || stopped || document.hidden) return;
        busy = true;
        try {
            const data = await window.YellovedChatHTTP.request(root.dataset.activityPreview);
            if (stopped) return;
            root.querySelector('[data-activity-content]').innerHTML = data.html;
            const badge = root.querySelector('[data-activity-count]');
            badge.hidden = !data.pending; badge.textContent = data.pending > 99 ? '99+' : data.pending;
            root.querySelector('button').setAttribute('aria-label', data.pending ? `Activity, ${data.pending} need your action` : 'Activity');
        } catch (_) { /* Keep the last preview; View all remains available. */ }
        finally {busy = false;}
    };
    const tick = async () => {await refresh(); if (!stopped) timer = setTimeout(tick, 10000);};
    root.querySelector('button').addEventListener('click', refresh);
    window.addEventListener('activity:changed', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('chat:session-ended', () => {
        stopped = true; clearTimeout(timer);
        root.querySelector('[data-activity-count]').hidden = true;
        root.querySelector('[data-activity-content]').textContent = 'Your session changed. Reload to view Activity.';
    });
    window.addEventListener('pagehide', () => {stopped = true; clearTimeout(timer);});
    window.addEventListener('pageshow', event => {if (event.persisted && !window.YellovedChatHTTP.blocked) {stopped = false; tick();}});
    tick();
})();
