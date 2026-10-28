(() => {
    const modal = document.getElementById("item-offer-modal");
    // Delegation keeps buttons working after AJAX search and page changes.
    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-open-item-offer-modal]");
        if (trigger && modal) {
            const form = modal.querySelector("[data-item-offer-form]");
            if (form.elements.wanted_post.value !== trigger.dataset.offerPost) form.reset();
            form.elements.wanted_post.value = trigger.dataset.offerPost;
            modal.querySelector("[data-offer-target]").textContent = `${trigger.dataset.offerTitle} · Max budget ${trigger.dataset.offerBudget}`;
            modal.showModal();
        }
        if (event.target.closest("[data-close-item-offer-modal]")) modal?.close();
    });
    modal?.addEventListener("click", (event) => {
        if (event.target === modal) modal.close();
    });
    document.querySelectorAll("[data-item-offer-form]").forEach((form) => {
        const submit = form.querySelector("[data-send-item-offer]");
        const message = form.elements.description;
        const update = () => {
            message.setCustomValidity(message.value.trim() ? "" : "Describe your item and pickup location.");
            submit.disabled = form.querySelector("fieldset").disabled || !form.checkValidity();
        };
        form.addEventListener("input", update);
        form.addEventListener("change", update);
        form.addEventListener("offer-image-validated", update);
        form.addEventListener("reset", () => {
            submit.disabled = true;
            form.querySelector("[data-offer-feedback]").textContent = "";
            queueMicrotask(update);
        });
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            update();
            if (submit.disabled || !form.reportValidity()) return;
            // Offer delivery remains deferred: keep the draft without claiming success.
            form.querySelector("[data-offer-feedback]").textContent = "Your offer is ready. Sending offers is not connected yet.";
        });
        update();
    });
})();
