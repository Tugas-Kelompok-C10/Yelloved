(() => {
    const form = document.querySelector("[data-ajax-search]");
    const grid = document.querySelector(".wanted-grid");
    const queryInput = document.getElementById("wanted-query");
    const categorySelect = document.getElementById("wanted-category");
    const conditionSelect = document.getElementById("wanted-condition");
    const resetButton = document.getElementById("wanted-filter-reset");
    const seeMoreButton = document.querySelector(".wanted-see-more");

    if (!form || !grid || !queryInput || !categorySelect || !conditionSelect || !resetButton || !seeMoreButton) return;

    const debounceDelay = 300;
    let debounceTimer;
    let activeRequest;
    let resizeTimer;
    let expanded = false;

    const applyCardLimit = () => {
        const cards = [...grid.querySelectorAll(".wanted-card")];
        const buttonLabel = seeMoreButton.querySelector("span");
        const columns = Math.max(
            1,
            window.getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length,
        );
        const visibleLimit = columns * 5;
        const hasOverflow = cards.length > visibleLimit;

        if (!hasOverflow) expanded = false;

        cards.forEach((card, index) => {
            card.hidden = !expanded && index >= visibleLimit;
        });
        seeMoreButton.hidden = !hasOverflow;
        seeMoreButton.classList.toggle("is-expanded", expanded);
        seeMoreButton.setAttribute("aria-expanded", String(expanded));
        if (buttonLabel) buttonLabel.textContent = expanded ? "See Less" : "See More";
    };

    const buildUrl = () => {
        const url = new URL(form.action, window.location.origin);
        const query = queryInput.value.trim();

        if (query) url.searchParams.set("q", query);
        if (categorySelect.value) url.searchParams.set("category", categorySelect.value);
        if (conditionSelect.value) url.searchParams.set("condition", conditionSelect.value);

        return url;
    };

    const loadResults = async () => {
        const url = buildUrl();
        activeRequest?.abort();
        const request = new AbortController();
        activeRequest = request;
        grid.classList.add("is-loading");
        grid.setAttribute("aria-busy", "true");

        try {
            const response = await fetch(url, {
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                signal: request.signal,
            });

            if (!response.ok) throw new Error(`Search failed with status ${response.status}`);

            const data = await response.json();
            grid.innerHTML = data.html;
            expanded = false;
            applyCardLimit();
            categorySelect.value = data.selected_category;
            conditionSelect.value = data.selected_condition;
            window.history.replaceState({}, "", url);
        } catch (error) {
            if (error.name !== "AbortError") window.location.assign(url);
        } finally {
            if (activeRequest === request) {
                grid.classList.remove("is-loading");
                grid.setAttribute("aria-busy", "false");
            }
        }
    };

    queryInput.addEventListener("input", () => {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(loadResults, debounceDelay);
    });

    [categorySelect, conditionSelect].forEach((select) => {
        select.addEventListener("change", () => {
            window.clearTimeout(debounceTimer);
            loadResults();
        });
    });

    resetButton.addEventListener("click", () => {
        window.clearTimeout(debounceTimer);
        queryInput.value = "";
        categorySelect.value = "";
        conditionSelect.value = "";
        loadResults();
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        loadResults();
    });

    seeMoreButton.addEventListener("click", () => {
        expanded = !expanded;
        applyCardLimit();
    });

    window.addEventListener("resize", () => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(applyCardLimit, 120);
    });

    applyCardLimit();

    const placeholder = queryInput.dataset.typingPlaceholder;
    if (!queryInput.value && placeholder) {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            queryInput.placeholder = placeholder;
        } else {
            let characterIndex = 0;
            const typeNextCharacter = () => {
                characterIndex += 1;
                queryInput.placeholder = placeholder.slice(0, characterIndex);
                if (characterIndex < placeholder.length) {
                    window.setTimeout(typeNextCharacter, 70);
                }
            };
            window.setTimeout(typeNextCharacter, 250);
        }
    }
})();
