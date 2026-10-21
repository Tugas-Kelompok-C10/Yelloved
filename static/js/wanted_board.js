(() => {
    const form = document.querySelector("[data-ajax-search]");
    const grid = document.querySelector(".wanted-grid");
    const queryInput = document.getElementById("wanted-query");
    const resultCount = document.querySelector(".wanted-results-count");

    if (!form || !grid || !queryInput || !resultCount) return;

    const categoryButtons = [...form.querySelectorAll(".wanted-category-chips button")];
    const debounceDelay = 300;
    let selectedCategory = form.querySelector(".wanted-category-chips .active")?.value || "";
    let debounceTimer;
    let activeRequest;

    const buildUrl = () => {
        const url = new URL(form.action, window.location.origin);
        const query = queryInput.value.trim();

        if (query) url.searchParams.set("q", query);
        if (selectedCategory) url.searchParams.set("category", selectedCategory);

        return url;
    };

    const updateCategoryState = (category) => {
        selectedCategory = category;
        categoryButtons.forEach((button) => {
            const isActive = button.value === category;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
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
            resultCount.textContent = data.result_label;
            updateCategoryState(data.selected_category);
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

    categoryButtons.forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            window.clearTimeout(debounceTimer);
            updateCategoryState(button.value);
            loadResults();
        });
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        loadResults();
    });
})();
