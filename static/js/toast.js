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

    window.YellovedToast = { show };
    region.querySelectorAll("[data-global-toast]").forEach((toast, index) => {
        const duration = Number(toast.dataset.toastDuration) || 3000;
        window.setTimeout(() => showElement(toast, duration), index * 80);
    });
})();
