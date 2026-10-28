(() => {
    const section = document.querySelector('[data-hanging-carousel]');
    const track = section?.querySelector('.landing-hanging-grid');
    if (!track) return;
    const cards = [...track.querySelectorAll('.landing-hanging-card')];
    const controls = section.querySelector('[data-carousel-controls]');
    const previous = controls.querySelector('[data-carousel-prev]');
    const next = controls.querySelector('[data-carousel-next]');
    const status = section.querySelector('[data-carousel-status]');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let desiredPage = null;
    let settleTimer;
    let firstVisible = 0;
    let drag;
    let suppressClick = false;
    const geometry = () => {
        const css = getComputedStyle(track);
        const size = Math.max(1, Number(css.getPropertyValue('--carousel-page-size')) || 4);
        const padding = parseFloat(css.paddingLeft) || 0;
        const maximum = Math.max(0, track.scrollWidth - track.clientWidth);
        const targets = [...new Set(cards.filter((_, i) => i % size === 0)
            .map(card => Math.max(0, Math.min(maximum, card.offsetLeft - padding))))];
        return {size, targets: targets.length ? targets : [0]};
    };
    const nearest = targets => targets.reduce((best, x, i) =>
        Math.abs(x - track.scrollLeft) < Math.abs(targets[best] - track.scrollLeft) ? i : best, 0);
    const update = () => {
        const {size, targets} = geometry();
        const page = Math.min(targets.length - 1, desiredPage ?? nearest(targets));
        firstVisible = page * size;
        controls.hidden = targets.length <= 1;
        previous.disabled = page === 0;
        next.disabled = page === targets.length - 1;
        const text = `Items ${firstVisible + 1}–${Math.min(cards.length, firstVisible + size)} of ${cards.length}`;
        if (status && status.textContent !== text) status.textContent = text;
    };
    const settle = () => {
        if (drag?.moved) return;
        const {targets} = geometry();
        const page = Math.min(targets.length - 1, desiredPage ?? nearest(targets));
        if (Math.abs(track.scrollLeft - targets[page]) > 2) {
            desiredPage = page;
            track.scrollTo({left: targets[page], behavior: reduced.matches ? 'instant' : 'smooth'});
            return;
        }
        desiredPage = null;
        track.classList.remove('is-sliding');
        update();
    };
    const jump = page => {
        const {targets} = geometry();
        desiredPage = Math.max(0, Math.min(targets.length - 1, page));
        track.classList.toggle('is-sliding', !reduced.matches);
        track.scrollTo({left: targets[desiredPage], behavior: reduced.matches ? 'instant' : 'smooth'});
        update();
        window.clearTimeout(settleTimer);
        settleTimer = window.setTimeout(settle, 160);
    };
    const move = direction => jump((desiredPage ?? nearest(geometry().targets)) + direction);
    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    track.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            move(event.key === 'ArrowRight' ? 1 : -1);
        } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            jump(event.key === 'Home' ? 0 : geometry().targets.length - 1);
        }
    });
    track.addEventListener('pointerdown', event => {
        if (event.pointerType !== 'mouse' || event.button !== 0) return;
        suppressClick = false;
        desiredPage = null;
        drag = {id: event.pointerId, x: event.clientX, y: event.clientY,
            left: track.scrollLeft, page: nearest(geometry().targets), moved: false};
    });
    track.addEventListener('pointermove', event => {
        if (!drag) return;
        const delta = event.clientX - drag.x;
        if (!drag.moved && Math.abs(delta) > 6 && Math.abs(delta) > Math.abs(event.clientY - drag.y)) {
            drag.moved = true;
            track.setPointerCapture(event.pointerId);
            track.classList.add('is-dragging');
        }
        if (drag.moved) {
            event.preventDefault();
            track.scrollLeft = drag.left - delta;
        }
    });
    const finish = () => {
        if (!drag) return;
        const previousDrag = drag;
        drag = null;
        suppressClick = previousDrag.moved;
        if (track.hasPointerCapture(previousDrag.id)) track.releasePointerCapture(previousDrag.id);
        track.classList.remove('is-dragging');
        if (previousDrag.moved) {
            const delta = track.scrollLeft - previousDrag.left;
            jump(Math.abs(delta) > 35 ? previousDrag.page + Math.sign(delta) : nearest(geometry().targets));
        }
    };
    track.addEventListener('pointerup', finish);
    track.addEventListener('pointercancel', finish);
    track.addEventListener('lostpointercapture', finish);
    track.addEventListener('pointerleave', () => { if (drag && !drag.moved) finish(); });
    let touch;
    track.addEventListener('touchstart', event => {
        const point = event.touches[0];
        touch = {x: point.clientX, y: point.clientY, page: nearest(geometry().targets)};
    }, {passive: true});
    track.addEventListener('touchend', event => {
        if (!touch) return;
        const point = event.changedTouches[0];
        const dx = touch.x - point.clientX;
        if (Math.abs(dx) > 35 && Math.abs(dx) > Math.abs(touch.y - point.clientY)) jump(touch.page + Math.sign(dx));
        touch = null;
    }, {passive: true});
    let wheelTimer;
    let wheelLocked = false;
    track.addEventListener('wheel', event => {
        const dx = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.shiftKey ? event.deltaY : 0;
        if (Math.abs(dx) < 2) return;
        event.preventDefault();
        if (!wheelLocked) move(Math.sign(dx));
        wheelLocked = true;
        window.clearTimeout(wheelTimer);
        wheelTimer = window.setTimeout(() => { wheelLocked = false; }, 180);
    }, {passive: false});
    track.addEventListener('click', event => {
        if (!suppressClick) return;
        event.preventDefault();
        event.stopPropagation();
        suppressClick = false;
    }, true);
    track.addEventListener('dragstart', event => event.preventDefault());
    track.addEventListener('scroll', () => {
        update();
        track.classList.toggle('is-sliding', !reduced.matches);
        window.clearTimeout(settleTimer);
        settleTimer = window.setTimeout(settle, 160);
    }, {passive: true});
    // Resizing preserves the visible item and recalculates whole-page stops.
    new ResizeObserver(() => {
        const {size, targets} = geometry();
        const page = Math.min(targets.length - 1, Math.floor(firstVisible / size));
        desiredPage = null;
        track.classList.remove('is-sliding');
        track.scrollTo({left: targets[page], behavior: 'instant'});
        update();
    }).observe(track);
    update();
})();
