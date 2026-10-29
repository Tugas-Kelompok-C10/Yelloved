(() => {
    let destroy = () => {};
    const init = () => {
    const form = document.querySelector("[data-ajax-search]");
    const grid = document.querySelector(".wanted-grid");
    const queryInput = document.getElementById("wanted-query");
    const categoryChips = [...document.querySelectorAll("[data-category-chip]")];
    const pagination = document.querySelector("[data-wanted-pagination]");

    if (!form || !grid || !queryInput || !categoryChips.length || !pagination) return;
    if (form.dataset.searchBound) return;
    destroy();
    form.dataset.searchBound = 'true';

    const debounceDelay = 300;
    let debounceTimer;
    let activeRequest;
    let disposed = false;
    destroy = () => {
        disposed = true;
        window.clearTimeout(debounceTimer);
        activeRequest?.abort();
    };
    let selectedCategory = categoryChips.find((chip) => chip.classList.contains("is-active"))?.dataset.categoryChip || "";

    const updateCategoryChips = (category) => {
        selectedCategory = category;
        categoryChips.forEach((chip) => {
            const isActive = chip.dataset.categoryChip === category;
            chip.classList.toggle("is-active", isActive);
            chip.setAttribute("aria-pressed", String(isActive));
        });
    };

    const buildUrl = (page) => {
        const url = new URL(form.action, window.location.origin);
        const query = queryInput.value.trim().slice(0, 70);
        queryInput.value = query;

        if (query) url.searchParams.set("q", query);
        if (selectedCategory) url.searchParams.set("category", selectedCategory);
        if (page > 1) url.searchParams.set("page", page);

        return url;
    };

    // Search/category changes start at page one; page links retain current filters.
    const loadResults = async (page = 1, scrollToTop = false) => {
        if (disposed) return;
        const url = buildUrl(page);
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
            if (disposed || activeRequest !== request) return;
            grid.innerHTML = data.html;
            pagination.innerHTML = data.pagination_html;
            updateCategoryChips(data.selected_category);
            if (data.page_number > 1) url.searchParams.set("page", data.page_number);
            else url.searchParams.delete("page");
            window.history.replaceState({}, "", url);
            if (scrollToTop) window.scrollTo({ top: 0, left: 0, behavior: "instant" });
        } catch (error) {
            if (!disposed && error.name !== "AbortError") window.location.assign(url);
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

    categoryChips.forEach((chip) => {
        chip.addEventListener("click", () => {
            window.clearTimeout(debounceTimer);
            updateCategoryChips(chip.dataset.categoryChip);
            loadResults();
        });
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        loadResults();
    });

    pagination.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-wanted-page]");
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        loadResults(Number(link.dataset.wantedPage), true);
    });

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
    };
    window.YellovedWantedBoard = {init, destroy: () => destroy()};
    init();
})();
