/* Address picker: location access starts only after the user presses the button. */
(() => {
    let map;
    let marker;
    let selected = null;
    let lastLookup = 0;

    const get = selector => document.querySelector(selector);
    const status = message => {
        const node = get('[data-address-map-status]');
        if (node) node.textContent = message;
    };

    const writeCoordinates = ({lat, lng}) => {
        selected = {lat: Number(lat), lng: Number(lng)};
        const form = get('.address-form');
        if (form) {
            form.elements.latitude.value = selected.lat.toFixed(7);
            form.elements.longitude.value = selected.lng.toFixed(7);
        }
        if (map) {
            if (marker) marker.setLatLng(selected);
            else marker = L.marker(selected).addTo(map);
            map.setView(selected, Math.max(map.getZoom(), 16));
        }
        status(`Selected: ${selected.lat.toFixed(5)}, ${selected.lng.toFixed(5)}`);
    };

    const initializeMap = () => {
        const element = get('#address-map');
        if (!element || element.closest('[hidden]') || !window.L) return;
        if (map && element._leaflet_id) {
            requestAnimationFrame(() => map.invalidateSize());
            return;
        }
        const picker = element.closest('.address-map-picker');
        const initialLat = Number(picker.dataset.latitude);
        const initialLng = Number(picker.dataset.longitude);
        const hasInitial = Number.isFinite(initialLat) && Number.isFinite(initialLng) && picker.dataset.latitude !== '' && picker.dataset.longitude !== '';
        const initial = hasInitial ? {lat: initialLat, lng: initialLng} : {lat: -2.5, lng: 118};
        map = L.map(element, {scrollWheelZoom: false}).setView(initial, hasInitial ? 15 : 5);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        }).addTo(map);
        if (hasInitial) {
            selected = initial;
            marker = L.marker(initial).addTo(map);
            status(`Saved location: ${initial.lat.toFixed(5)}, ${initial.lng.toFixed(5)}`);
        }
        map.on('click', event => writeCoordinates(event.latlng));
        requestAnimationFrame(() => map.invalidateSize());
    };

    const lookupAddress = async () => {
        if (!selected) {
            status('First select a point on the map or use your current location.');
            return;
        }
        const wait = 1100 - (Date.now() - lastLookup);
        if (wait > 0) await new Promise(resolve => setTimeout(resolve, wait));
        lastLookup = Date.now();
        status('Looking up the selected location…');
        try {
            const query = new URLSearchParams({
                format: 'jsonv2', lat: selected.lat, lon: selected.lng, 'accept-language': 'id',
            });
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?${query}`, {
                headers: {Accept: 'application/json'}, credentials: 'omit',
            });
            if (!response.ok) throw new Error('Location lookup is unavailable. You can fill the address fields manually.');
            const result = await response.json();
            const parts = result.address || {};
            const form = get('.address-form');
            const street = [parts.road || parts.pedestrian || parts.footway, parts.house_number,
                parts.neighbourhood || parts.suburb || parts.hamlet].filter(Boolean).join(', ');
            const city = parts.city || parts.town || parts.village || parts.municipality || parts.county;
            if (street) form.elements.street_address.value = street;
            if (city) form.elements.city.value = city;
            if (parts.state) form.elements.province.value = parts.state;
            if (parts.postcode) form.elements.postal_code.value = parts.postcode;
            status(result.display_name ? 'Address found. Please check the fields before saving.' : 'Point selected. Please fill the address fields manually.');
        } catch (error) {
            status(error.message || 'Unable to look up this location. Fill the fields manually.');
        }
    };

    document.addEventListener('click', event => {
        if (event.target.closest('#toggle-address-form')) {
            setTimeout(() => { initializeMap(); map?.invalidateSize(); }, 0);
            return;
        }
        if (event.target.closest('[data-address-locate]')) {
            initializeMap();
            if (!navigator.geolocation) {
                status('Location access is not available in this browser.');
                return;
            }
            status('Requesting your location…');
            navigator.geolocation.getCurrentPosition(position => {
                writeCoordinates({lat: position.coords.latitude, lng: position.coords.longitude});
                lookupAddress();
            }, error => {
                const message = error.code === error.PERMISSION_DENIED
                    ? 'Location permission was denied. You can select a point on the map instead.'
                    : 'Could not detect your location. Select a point on the map instead.';
                status(message);
            }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 60000});
            return;
        }
        if (event.target.closest('[data-address-map-use]')) lookupAddress();
    });

    document.addEventListener('DOMContentLoaded', initializeMap, {once: true});
    new MutationObserver(() => initializeMap()).observe(document.documentElement, {childList: true, subtree: true});
})();
