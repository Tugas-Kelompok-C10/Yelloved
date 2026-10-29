(() => {
    const region = document.getElementById("site-toast-region");
    if (!region) return;

    const dismiss = (toast) => {
        toast.classList.remove("is-visible");
        toast.classList.add("is-leaving");
        window.setTimeout(() => toast.remove(), 140);
    };

    const showElement = (toast, duration = 3000) => {
        toast.hidden = false;
        window.requestAnimationFrame(() => toast.classList.add("is-visible"));
        window.setTimeout(() => dismiss(toast), duration);
        return toast;
    };

    const show = ({ title = "Success", message = "Action completed.", type = "success", duration = 3000 } = {}) => {
        const toast = document.createElement("article");
        toast.className = "site-toast";
        toast.dataset.toastType = type;
        toast.setAttribute("role", type === "error" ? "alert" : "status");

        const icon = document.createElement("span");
        icon.className = "site-toast-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"></path></svg>';

        const copy = document.createElement("span");
        copy.className = "site-toast-copy";
        const heading = document.createElement("strong");
        const detail = document.createElement("small");
        heading.textContent = title;
        detail.textContent = message;
        copy.append(heading, detail);
        toast.append(icon, copy);
        region.append(toast);
        return showElement(toast, duration);
    };

    // One-time feedback survives full navigation and browser Back (bfcache).
    const navigationKey = 'yelloved-navigation-toast';
    const queue = options => {
        try {
            sessionStorage.setItem(navigationKey, JSON.stringify({options, expires: Date.now() + 60000}));
        } catch (_) { /* Storage can be blocked; navigation must remain usable. */ }
    };
    const consume = () => {
        try {
            const raw = sessionStorage.getItem(navigationKey);
            sessionStorage.removeItem(navigationKey);
            if (!raw) return;
            const feedback = JSON.parse(raw);
            if (feedback.expires > Date.now() && feedback.options && typeof feedback.options.message === 'string') {
                show(feedback.options);
            }
        } catch (_) { /* Ignore invalid or unavailable browser storage. */ }
    };
    window.YellovedToast = { show, queue };
    window.addEventListener('pageshow', consume);
    consume();
    region.querySelectorAll("[data-global-toast]").forEach((toast, index) => {
        const duration = Number(toast.dataset.toastDuration) || 3000;
        window.setTimeout(() => showElement(toast, duration), index * 80);
    });
})();
