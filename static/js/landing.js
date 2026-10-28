(() => {
    const hero = document.querySelector("[data-landing-hero]");
    const form = hero?.querySelector("[data-love-form]");
    if (!hero || !form) return;

    const count = hero.querySelector("[data-heart-count]");
    const feedback = hero.querySelector("[data-love-message]");
    const template = hero.querySelector("[data-love-burst]");
    let pending = false;

    // Replay from the start for each heart/logo activation, including keyboard input.
    const popAudio = hero.querySelector("[data-landing-pop]");
    const playPop = () => {
        if (!popAudio) return;
        popAudio.currentTime = 0;
        popAudio.play().catch(() => {
            // Sound restrictions must not interrupt the heart interaction.
        });
    };
    if (popAudio) {
        popAudio.volume = 0.35;

        // Start the sound immediately with the logo entrance, without a peak delay.
        playPop();
    }

    const burstHeart = (button) => {
        const burst = template.content.firstElementChild.cloneNode(true);
        const origin = button.getBoundingClientRect();
        const bounds = hero.getBoundingClientRect();
        burst.style.left = `${origin.left + origin.width / 2 - bounds.left}px`;
        burst.style.top = `${origin.top + origin.height / 2 - bounds.top}px`;
        hero.append(burst);
        window.setTimeout(() => burst.remove(), 850);
    };

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (pending) return;
        pending = true;
        const button = event.submitter || hero.querySelector(".landing-love-logo");
        playPop();

        // Allow one request at a time; extra clicks never build a delayed queue.
        (async () => {
            button.setAttribute("aria-busy", "true");
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    credentials: "same-origin",
                    signal: AbortSignal.timeout(10000),
                    headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
                });
                if (!response.ok) throw new Error("Unable to send a heart");
                const data = await response.json();
                count.textContent = `${data.count} hearts shared in this visit.`;
                feedback.textContent = "";
                burstHeart(button);
            } catch {
                feedback.textContent = "That heart couldn't reach us. Please try again.";
                window.YellovedToast?.show({title: "Oops", message: feedback.textContent, type: "error"});
            } finally {
                button.removeAttribute("aria-busy");
                pending = false;
            }
        })();
    });
})();
