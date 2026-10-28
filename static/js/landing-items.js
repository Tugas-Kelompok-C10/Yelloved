(() => {
    const section = document.querySelector('.home-items-section');
    const track = section?.querySelector('.home-items-track');
    if (!track) return;
    const controls = section.querySelector('.home-items-controls');
    const previous = controls.querySelector('[data-board-prev]');
    const next = controls.querySelector('[data-board-next]');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const step = () => {
        const card = track.querySelector('.landing-latest-card');
        return card ? card.offsetWidth + parseFloat(getComputedStyle(track).gap) : track.clientWidth;
    };
    const move = direction => track.scrollBy({left: direction * step(), behavior: reduced.matches ? 'instant' : 'smooth'});
    const update = () => {
        const maximum = track.scrollWidth - track.clientWidth;
        controls.hidden = maximum <= 2;
        previous.disabled = track.scrollLeft <= 2;
        next.disabled = track.scrollLeft >= maximum - 2;
    };
    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    track.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            move(event.key === 'ArrowRight' ? 1 : -1);
        } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            track.scrollTo({left: event.key === 'Home' ? 0 : track.scrollWidth, behavior: reduced.matches ? 'instant' : 'smooth'});
        }
    });
    let drag;
    let suppressClick = false;
    track.addEventListener('pointerdown', event => {
        if (event.pointerType !== 'mouse' || event.button !== 0) return;
        suppressClick = false;
        drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: track.scrollLeft, moved: false};
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
        suppressClick = drag.moved;
        if (track.hasPointerCapture(drag.id)) track.releasePointerCapture(drag.id);
        track.classList.remove('is-dragging');
        drag = null;
    };
    track.addEventListener('pointerup', finish);
    track.addEventListener('pointercancel', finish);
    track.addEventListener('lostpointercapture', finish);
    track.addEventListener('pointerleave', () => { if (drag && !drag.moved) finish(); });
    track.addEventListener('click', event => {
        if (!suppressClick) return;
        event.preventDefault();
        event.stopPropagation();
        suppressClick = false;
    }, true);
    track.addEventListener('dragstart', event => event.preventDefault());
    track.addEventListener('scroll', update, {passive: true});
    new ResizeObserver(update).observe(track);
    update();
})();
