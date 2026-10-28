(() => {
    const slot = document.querySelector('.landing-board-stickers');
    const board = slot?.closest('.wanted-grid');
    if (!board) return;
    const stickers = [...slot.querySelectorAll('[data-board-sticker]')];
    const position = (sticker, x, y) => {
        const maxX = Math.max(20, board.clientWidth - sticker.offsetWidth - 20);
        const maxY = Math.max(20, board.clientHeight - sticker.offsetHeight - 20);
        const left = Math.max(20, Math.min(maxX, x));
        const top = Math.max(20, Math.min(maxY, y));
        sticker.style.left = `${left}px`;
        sticker.style.top = `${top}px`;
        sticker.dataset.xRatio = String(left / board.clientWidth);
        sticker.dataset.yRatio = String(top / board.clientHeight);
    };
    new ResizeObserver(() => {
        const bounds = board.getBoundingClientRect();
        const initial = slot.getBoundingClientRect();
        stickers.forEach((sticker, index) => {
            const x = sticker.dataset.xRatio === undefined
                ? initial.left - bounds.left + initial.width * (index ? 0.76 : 0.33) - sticker.offsetWidth / 2
                : Number(sticker.dataset.xRatio) * board.clientWidth;
            const y = sticker.dataset.yRatio === undefined
                ? initial.top - bounds.top + initial.height / 2 - sticker.offsetHeight / 2
                : Number(sticker.dataset.yRatio) * board.clientHeight;
            position(sticker, x, y);
        });
    }).observe(board);
    stickers.forEach(sticker => {
        let drag;
        sticker.addEventListener('pointerdown', event => {
            if (event.button !== 0) return;
            event.preventDefault();
            drag = {x: event.clientX, y: event.clientY, left: parseFloat(sticker.style.left), top: parseFloat(sticker.style.top)};
            sticker.setPointerCapture(event.pointerId);
            sticker.classList.add('is-dragging');
            sticker.focus({preventScroll: true});
        });
        sticker.addEventListener('pointermove', event => {
            if (drag) position(sticker, drag.left + event.clientX - drag.x, drag.top + event.clientY - drag.y);
        });
        const finish = () => { drag = null; sticker.classList.remove('is-dragging'); };
        sticker.addEventListener('pointerup', finish);
        sticker.addEventListener('pointercancel', finish);
        sticker.addEventListener('lostpointercapture', finish);
        sticker.addEventListener('dragstart', event => event.preventDefault());
        sticker.addEventListener('keydown', event => {
            const directions = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
            if (!directions[event.key] || event.altKey || event.ctrlKey || event.metaKey) return;
            event.preventDefault();
            const [x, y] = directions[event.key];
            const distance = event.shiftKey ? 20 : 10;
            position(sticker, parseFloat(sticker.style.left) + x * distance, parseFloat(sticker.style.top) + y * distance);
        });
    });
})();
