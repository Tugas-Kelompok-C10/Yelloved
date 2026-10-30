(() => {
    document.querySelectorAll('.landing-faq').forEach(section => {
        const buttons = [...section.querySelectorAll('.landing-faq-trigger')];
        function setOpen(button, open) {
            const panel = section.querySelector(`#${button.getAttribute('aria-controls')}`);
            button.setAttribute('aria-expanded', String(open));
            button.closest('.landing-faq-card').classList.toggle('is-open', open);
            panel.setAttribute('aria-hidden', String(!open));
            panel.inert = !open;
        }
        buttons.forEach((button, index) => {
            button.addEventListener('click', () => {
                const opening = button.getAttribute('aria-expanded') !== 'true';
                buttons.forEach(other => setOpen(other, other === button && opening));
            });
            button.addEventListener('keydown', event => {
                let target;
                if (event.key === 'ArrowDown') target = (index + 1) % buttons.length;
                else if (event.key === 'ArrowUp') target = (index + buttons.length - 1) % buttons.length;
                else if (event.key === 'Home') target = 0;
                else if (event.key === 'End') target = buttons.length - 1;
                else return; // Enter and Space use the button's native click behavior.
                event.preventDefault();
                buttons[target].focus();
            });
        });
    });
})();
