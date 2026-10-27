(() => {
    document.querySelectorAll("[data-wanted-budget]").forEach((input) => {
        const feedback = document.createElement("small");
        feedback.className = "form-error";
        feedback.id = `${input.id}-budget-error`;
        feedback.setAttribute("aria-live", "polite");
        input.after(feedback);
        input.setAttribute("aria-describedby", feedback.id);

        const validate = () => {
            const invalid = !input.value.trim() || !Number.isFinite(Number(input.value)) || Number(input.value) <= 0;
            const message = invalid ? "Please enter a maximum budget greater than Rp0." : "";
            input.setCustomValidity(message);
            input.setAttribute("aria-invalid", String(invalid));
            feedback.textContent = message;
        };
        input.addEventListener("input", validate);
        input.addEventListener("blur", validate);
        input.addEventListener("invalid", validate);
        input.form?.addEventListener("reset", () => {
            input.setCustomValidity("");
            input.removeAttribute("aria-invalid");
            feedback.textContent = "";
        });
    });
})();
