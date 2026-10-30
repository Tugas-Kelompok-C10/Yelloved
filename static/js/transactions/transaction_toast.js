
document.addEventListener("DOMContentLoaded", () => {
    const toasts = document.querySelectorAll("[data-transaction-toast]");

    toasts.forEach((toast) => {
        const closeButton = toast.querySelector(".transaction-toast-close");
        let dismissTimer;

        const dismissToast = () => {
            if (toast.hidden || toast.classList.contains("is-leaving")) {
                return;
            }

            window.clearTimeout(dismissTimer);
            toast.classList.add("is-leaving");

            const duration = window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches ? 0 : 250;

            window.setTimeout(() => {
                toast.hidden = true;
                toast.classList.remove("is-leaving");
            }, duration);
        };

        toast.hidden = false;

        dismissTimer = window.setTimeout(dismissToast, 4000);

        closeButton?.addEventListener("click", dismissToast);
    });
});
