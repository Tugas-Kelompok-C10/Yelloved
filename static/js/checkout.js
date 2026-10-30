document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. ELEMENT REFERENCES
    // ==========================================
    const addressModal = document.getElementById("address-modal");
    const newAddressModal = document.getElementById("new-address-modal");
    const newAddressForm = document.getElementById("new-address-form");

    const provinceSelect = document.getElementById("province");
    const regencySelect = document.getElementById("regency");
    const districtSelect = document.getElementById("district");
    const villageSelect = document.getElementById("village");

    // ==========================================
    // 2. ADDRESS MODAL FUNCTIONS
    // ==========================================
    function openModal(modal) {
        if (!modal) return;

        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("address-modal-open");
    }

    function closeModal(modal) {
        if (!modal) return;

        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");

        if (!document.querySelector(".address-modal-overlay.is-open")) {
            document.body.classList.remove("address-modal-open");
        }
    }

    document.querySelectorAll("[data-open-address-modal]").forEach((button) => {
        button.addEventListener("click", () => {
            openModal(addressModal);
        });
    });

    document.querySelectorAll("[data-close-address-modal]").forEach((button) => {
        button.addEventListener("click", () => {
            closeModal(addressModal);
        });
    });

    document.querySelectorAll("[data-open-new-address-modal]").forEach((button) => {
        button.addEventListener("click", () => {
            closeModal(addressModal);
            openModal(newAddressModal);
        });
    });

    document.querySelectorAll("[data-close-new-address-modal]").forEach((button) => {
        button.addEventListener("click", () => {
            closeModal(newAddressModal);
        });
    });

    document.querySelectorAll(".address-modal-overlay").forEach((overlay) => {
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                closeModal(overlay);
            }
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeModal(addressModal);
            closeModal(newAddressModal);
        }
    });

    // ==========================================
    // 3. INDONESIAN REGION DROPDOWNS
    // ==========================================
    function resetSelect(select, placeholder) {
        if (!select) return;

        select.innerHTML = "";

        const option = document.createElement("option");
        option.value = "";
        option.textContent = placeholder;

        select.appendChild(option);
        select.disabled = true;
    }

    function populateSelect(select, data, placeholder) {
        if (!select) return;

        select.innerHTML = "";

        const firstOption = document.createElement("option");
        firstOption.value = "";
        firstOption.textContent = placeholder;
        select.appendChild(firstOption);

        data.forEach((item) => {
            const option = document.createElement("option");
            option.value = item.name;
            option.textContent = item.name;
            option.dataset.regionId = item.id;

            select.appendChild(option);
        });

        select.disabled = false;
    }

    async function fetchRegions(url) {
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error("Failed to fetch regional data.");
        }

        return response.json();
    }

    if (provinceSelect && regencySelect && districtSelect && villageSelect) {
        const apiBase =
            "https://www.emsifa.com/api-wilayah-indonesia/api";

        fetchRegions(`${apiBase}/provinces.json`)
            .then((data) => {
                populateSelect(provinceSelect, data, "Select a province");
            })
            .catch((error) => {
                console.error(error);
                resetSelect(provinceSelect, "Failed to load provinces");
            });

        provinceSelect.addEventListener("change", async () => {
            resetSelect(regencySelect, "Loading cities/regencies...");
            resetSelect(districtSelect, "Select a district");
            resetSelect(villageSelect, "Select a subdistrict/village");

            const provinceId =
                provinceSelect.selectedOptions[0]?.dataset.regionId;

            if (!provinceId) {
                resetSelect(regencySelect, "Select a city/regency");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/regencies/${provinceId}.json`
                );

                populateSelect(
                    regencySelect,
                    data,
                    "Select a city/regency"
                );
            } catch (error) {
                console.error(error);
                resetSelect(regencySelect, "Failed to load cities/regencies");
            }
        });

        regencySelect.addEventListener("change", async () => {
            resetSelect(districtSelect, "Loading districts...");
            resetSelect(villageSelect, "Select a subdistrict/village");

            const regencyId =
                regencySelect.selectedOptions[0]?.dataset.regionId;

            if (!regencyId) {
                resetSelect(districtSelect, "Select a district");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/districts/${regencyId}.json`
                );

                populateSelect(districtSelect, data, "Select a district");
            } catch (error) {
                console.error(error);
                resetSelect(districtSelect, "Failed to load districts");
            }
        });

        districtSelect.addEventListener("change", async () => {
            resetSelect(villageSelect, "Loading subdistricts/villages...");

            const districtId =
                districtSelect.selectedOptions[0]?.dataset.regionId;

            if (!districtId) {
                resetSelect(villageSelect, "Select a subdistrict/village");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/villages/${districtId}.json`
                );

                populateSelect(
                    villageSelect,
                    data,
                    "Select a subdistrict/village"
                );
            } catch (error) {
                console.error(error);
                resetSelect(villageSelect, "Failed to load subdistricts/villages");
            }
        });
    }

    // ==========================================
    // 4. RESET ADDRESS FORM
    // ==========================================
    function resetAddressForm() {
        if (!newAddressForm) return;

        newAddressForm.reset();

        const idInput = newAddressForm.querySelector(
            'input[name="address_id"]'
        );

        if (idInput) idInput.value = "";

        const title = document.getElementById("new-address-title");
        if (title) title.textContent = "New Address";

        const submitButton = newAddressForm.querySelector(
            'button[type="submit"]'
        );

        if (submitButton) submitButton.textContent = "Save Address";

        resetSelect(regencySelect, "Select a city/regency");
        resetSelect(districtSelect, "Select a district");
        resetSelect(villageSelect, "Select a subdistrict/village");
    }

    document.querySelectorAll("[data-reset-address-form]").forEach((button) => {
        button.addEventListener("click", resetAddressForm);
    });

    const shouldOpenAddressForm =
        document.querySelector("[data-show-address-form='true']");

    if (shouldOpenAddressForm) {
        openModal(newAddressModal);
    }

    // ==========================================
    // 5. PAYMENT METHOD
    // ==========================================
    const paymentRadios = document.querySelectorAll(
        'input[name="payment_method"]'
    );

    const bankSelection = document.getElementById(
        "payment-bank-selection"
    );

    const bankSelect = document.getElementById("payment-bank");

    const shippingAddressFields = document.getElementById(
        "shipping-address-fields"
    );

    const codMeetingSection = document.getElementById(
        "cod-meeting-section"
    );

    const codMeetingLocation = document.getElementById(
        "cod-meeting-location"
    );

    const codMeetingTime = document.getElementById(
        "cod-meeting-time"
    );

    function updatePaymentFields() {
        const selectedPayment = document.querySelector(
            'input[name="payment_method"]:checked'
        );

        const paymentMethod = selectedPayment
            ? selectedPayment.value
            : "qris";

        const isCOD = paymentMethod === "cod";
        const isBankTransfer = paymentMethod === "bank_transfer";

        // Replace the shipping address section with the meeting schedule for COD.
        if (shippingAddressFields) {
            shippingAddressFields.hidden = isCOD;
        }

        if (codMeetingSection) {
            codMeetingSection.hidden = !isCOD;
        }

        // Show bank selection only for Virtual Account payments.
        if (bankSelection) {
            bankSelection.hidden = !isBankTransfer;
        }

        if (bankSelect) {
            bankSelect.required = isBankTransfer;
        }

        // Meeting details are required when COD is selected.
        if (codMeetingLocation) {
            codMeetingLocation.required = isCOD;
        }

        if (codMeetingTime) {
            codMeetingTime.required = isCOD;
        }
    }

    paymentRadios.forEach((radio) => {
        radio.addEventListener("change", updatePaymentFields);
    });

    updatePaymentFields();

    // ==========================================
    // 6. EDIT ADDRESS BUTTON
    // ==========================================
    document.querySelectorAll("[data-edit-address]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!newAddressForm) return;

            const idInput = newAddressForm.querySelector(
                'input[name="address_id"]'
            );

            if (idInput) {
                idInput.value = button.dataset.editAddress;
            }

            const title = document.getElementById("new-address-title");
            if (title) title.textContent = "Edit Address";

            const submitButton = newAddressForm.querySelector(
                'button[type="submit"]'
            );

            if (submitButton) {
                submitButton.textContent = "Save Changes";
            }

            closeModal(addressModal);
            openModal(newAddressModal);
        });
    });
});