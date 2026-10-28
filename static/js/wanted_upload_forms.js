(() => {
    document.querySelectorAll("[data-ajax-upload]").forEach((form) => {
        const modal = form.closest("dialog");
        const summary = form.querySelector("[data-upload-form-errors]");
        let submitting = false;

        const showErrors = (errors) => {
            let firstInput;
            Object.entries(errors).forEach(([name, messages]) => {
                const field = [...form.querySelectorAll("[data-upload-field]")]
                    .find((element) => element.dataset.uploadField === name);
                const container = field || summary;
                const input = field?.querySelector("input, select, textarea");
                if (input) {
                    input.setAttribute("aria-invalid", "true");
                    firstInput ||= input;
                }
                messages.forEach((error) => {
                    const text = document.createElement("small");
                    text.className = "form-error";
                    text.dataset.serverError = "";
                    text.textContent = error.message;
                    container.append(text);
                });
            });
            firstInput?.focus();
        };

        modal?.addEventListener("cancel", (event) => {
            if (submitting) event.preventDefault();
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (submitting || !form.reportValidity()) return;
            submitting = true;
            modal.dataset.submitting = "true";
            form.setAttribute("aria-busy", "true");
            form.querySelectorAll("[data-server-error]").forEach((error) => error.remove());
            const body = new FormData(form);
            const buttons = [...modal.querySelectorAll("button")];
            const previousStates = buttons.map((button) => button.disabled);
            const submitButton = form.querySelector('[type="submit"]');
            const previousLabel = submitButton.textContent;
            buttons.forEach((button) => { button.disabled = true; });
            submitButton.textContent = "Saving…";

            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body,
                    credentials: "same-origin",
                    headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
                });
                if (response.redirected) {
                    throw new Error("Your session may have expired. Sign in again in another tab, then retry. Your selected photo is still here.");
                }
                if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
                    throw new Error("Unable to save. Please check your connection or sign in again, then retry.");
                }
                const data = await response.json();
                if (response.status === 422 && data.errors) {
                    showErrors(data.errors);
                } else if (response.ok && data.redirect_url) {
                    window.location.assign(data.redirect_url);
                } else {
                    throw new Error("Unable to save. Your photo and details have been kept; please retry.");
                }
            } catch (error) {
                showErrors({ __all__: [{ message: error.message || "Unable to save. Please retry." }] });
            } finally {
                submitting = false;
                modal.dataset.submitting = "false";
                form.setAttribute("aria-busy", "false");
                buttons.forEach((button, index) => { button.disabled = previousStates[index]; });
                submitButton.textContent = previousLabel;
            }
        });
    });
})();
