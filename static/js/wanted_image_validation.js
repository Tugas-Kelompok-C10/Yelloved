(() => {
    const bound = new WeakSet();
    const init = () => {
    // Only offered items have photos; wanted posts do not upload images.
    document.querySelectorAll("[data-offer-image]").forEach((input) => {
        if (bound.has(input)) return;
        bound.add(input);
        const feedback = document.createElement("small");
        feedback.className = "form-error";
        feedback.setAttribute("aria-live", "polite");
        feedback.id = `${input.id}-image-error`;
        input.setAttribute("aria-describedby", feedback.id);
        input.after(feedback);
        let generation = 0;

        const setError = (message) => {
            input.setCustomValidity(message);
            input.setAttribute("aria-invalid", String(Boolean(message)));
            feedback.textContent = message;
            input.dispatchEvent(new Event("offer-image-validated", { bubbles: true }));
        };

        input.addEventListener("change", async () => {
            const currentGeneration = ++generation;
            const file = input.files[0];
            setError("");
            if (!file) return;
            if (!/\.(jpe?g|png|webp)$/i.test(file.name)) {
                setError("Please upload a JPG, JPEG, PNG, or WEBP image.");
                return;
            }
            if (file.size > 5 * 1024 * 1024) {
                setError("Image size must not exceed 5 MB.");
                return;
            }

            setError("Checking image…");
            const url = URL.createObjectURL(file);
            try {
                const image = new Image();
                image.src = url;
                await image.decode();
                if (currentGeneration !== generation) return;
                setError(Math.max(image.naturalWidth, image.naturalHeight) > 4096
                    ? "Image dimensions must not exceed 4096 × 4096 pixels."
                    : "");
            } catch {
                if (currentGeneration === generation) setError("Please upload a valid image.");
            } finally {
                URL.revokeObjectURL(url);
            }
        });

        input.form?.addEventListener("reset", () => {
            generation += 1;
            setError("");
        });
    });
    };
    window.addEventListener('wanted:mounted', init);
    init();
})();
