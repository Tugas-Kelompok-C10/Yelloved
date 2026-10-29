
document.addEventListener("DOMContentLoaded", () => {
    // ==========================================
    // 1. REFERENSI ELEMEN
    // ==========================================
    const addressModal = document.getElementById("address-modal");
    const newAddressModal = document.getElementById("new-address-modal");
    const newAddressForm = document.getElementById("new-address-form");

    const provinceSelect = document.getElementById("province");
    const regencySelect = document.getElementById("regency");
    const districtSelect = document.getElementById("district");
    const villageSelect = document.getElementById("village");

    // ==========================================
    // 2. FUNGSI MODAL ALAMAT
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
    // 3. DROPDOWN WILAYAH INDONESIA
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
            throw new Error("Gagal mengambil data wilayah.");
        }

        return response.json();
    }

    if (provinceSelect && regencySelect && districtSelect && villageSelect) {
        const apiBase =
            "https://www.emsifa.com/api-wilayah-indonesia/api";

        fetchRegions(`${apiBase}/provinces.json`)
            .then((data) => {
                populateSelect(provinceSelect, data, "Pilih Provinsi");
            })
            .catch((error) => {
                console.error(error);
                resetSelect(provinceSelect, "Gagal memuat provinsi");
            });

        provinceSelect.addEventListener("change", async () => {
            resetSelect(regencySelect, "Memuat kota/kabupaten...");
            resetSelect(districtSelect, "Pilih Kecamatan");
            resetSelect(villageSelect, "Pilih Kelurahan/Desa");

            const provinceId =
                provinceSelect.selectedOptions[0]?.dataset.regionId;

            if (!provinceId) {
                resetSelect(regencySelect, "Pilih Kota/Kabupaten");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/regencies/${provinceId}.json`
                );

                populateSelect(
                    regencySelect,
                    data,
                    "Pilih Kota/Kabupaten"
                );
            } catch (error) {
                console.error(error);
                resetSelect(regencySelect, "Gagal memuat kota/kabupaten");
            }
        });

        regencySelect.addEventListener("change", async () => {
            resetSelect(districtSelect, "Memuat kecamatan...");
            resetSelect(villageSelect, "Pilih Kelurahan/Desa");

            const regencyId =
                regencySelect.selectedOptions[0]?.dataset.regionId;

            if (!regencyId) {
                resetSelect(districtSelect, "Pilih Kecamatan");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/districts/${regencyId}.json`
                );

                populateSelect(districtSelect, data, "Pilih Kecamatan");
            } catch (error) {
                console.error(error);
                resetSelect(districtSelect, "Gagal memuat kecamatan");
            }
        });

        districtSelect.addEventListener("change", async () => {
            resetSelect(villageSelect, "Memuat kelurahan/desa...");

            const districtId =
                districtSelect.selectedOptions[0]?.dataset.regionId;

            if (!districtId) {
                resetSelect(villageSelect, "Pilih Kelurahan/Desa");
                return;
            }

            try {
                const data = await fetchRegions(
                    `${apiBase}/villages/${districtId}.json`
                );

                populateSelect(
                    villageSelect,
                    data,
                    "Pilih Kelurahan/Desa"
                );
            } catch (error) {
                console.error(error);
                resetSelect(villageSelect, "Gagal memuat kelurahan/desa");
            }
        });
    }

    // ==========================================
    // 4. RESET FORM ALAMAT
    // ==========================================
    function resetAddressForm() {
        if (!newAddressForm) return;

        newAddressForm.reset();

        const idInput = newAddressForm.querySelector(
            'input[name="address_id"]'
        );
        if (idInput) idInput.value = "";

        const title = document.getElementById("new-address-title");
        if (title) title.textContent = "Alamat Baru";

        const submitButton = newAddressForm.querySelector(
            'button[type="submit"]'
        );
        if (submitButton) submitButton.textContent = "Simpan Alamat";

        resetSelect(regencySelect, "Pilih Kota/Kabupaten");
        resetSelect(districtSelect, "Pilih Kecamatan");
        resetSelect(villageSelect, "Pilih Kelurahan/Desa");
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
    // 5. METODE PEMBAYARAN
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

        // Ganti alamat pengiriman dengan jadwal pertemuan untuk COD.
        if (shippingAddressFields) {
            shippingAddressFields.hidden = isCOD;
        }

        if (codMeetingSection) {
            codMeetingSection.hidden = !isCOD;
        }

        // Tampilkan pilihan bank hanya untuk Virtual Account.
        if (bankSelection) {
            bankSelection.hidden = !isBankTransfer;
        }

        if (bankSelect) {
            bankSelect.required = isBankTransfer;
        }

        // Jadwal wajib diisi jika COD dipilih.
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
    // 6. TOMBOL EDIT ALAMAT
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
            if (title) title.textContent = "Ubah Alamat";

            const submitButton = newAddressForm.querySelector(
                'button[type="submit"]'
            );

            if (submitButton) {
                submitButton.textContent = "Simpan Perubahan";
            }

            closeModal(addressModal);
            openModal(newAddressModal);
        });
    });
});
