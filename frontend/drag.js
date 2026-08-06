// Draggable panel functionality (Mobile + Desktop)
(function () {
    function isMobile() {
        return window.innerWidth <= 768;
    }

    function resetPanelPosition() {
        const panel = document.getElementById('infoPanel');
        if (!panel) return;

        if (isMobile()) {
            // Mobile: centered
            panel.style.left = '50%';
            panel.style.top = '50%';
            panel.style.right = 'auto';
            panel.style.transform = 'translate(-50%, -50%)';
        } else {
            // Desktop: top-right (reset to default CSS position)
            panel.style.left = '';
            panel.style.top = '';
            panel.style.right = '';
            panel.style.transform = '';
        }
    }

    function makePanelDraggable() {
        const panel = document.getElementById('infoPanel');
        if (!panel) {
            setTimeout(makePanelDraggable, 100);
            return;
        }

        const header = panel.querySelector('.panel-header');
        if (!header) {
            setTimeout(makePanelDraggable, 100);
            return;
        }

        let isDragging = false;
        let startX, startY;

        function dragStart(e) {
            if (e.target.classList.contains('close-btn')) return;

            isDragging = true;

            // Get current position
            const rect = panel.getBoundingClientRect();

            if (e.type === "touchstart") {
                startX = e.touches[0].clientX - rect.left;
                startY = e.touches[0].clientY - rect.top;
            } else {
                startX = e.clientX - rect.left;
                startY = e.clientY - rect.top;
            }

            panel.style.transition = 'none';
        }

        function drag(e) {
            if (!isDragging) return;

            e.preventDefault();

            let clientX, clientY;
            if (e.type === "touchmove") {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else {
                clientX = e.clientX;
                clientY = e.clientY;
            }

            // Position relative to viewport
            panel.style.left = (clientX - startX) + 'px';
            panel.style.top = (clientY - startY) + 'px';
            panel.style.right = 'auto';
            panel.style.transform = 'none';
        }

        function dragEnd() {
            isDragging = false;
            panel.style.transition = '';
        }

        // Touch events (mobile)
        header.addEventListener('touchstart', dragStart, { passive: false });
        document.addEventListener('touchmove', drag, { passive: false });
        document.addEventListener('touchend', dragEnd);

        // Mouse events (desktop)
        header.addEventListener('mousedown', dragStart);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', dragEnd);

        console.log('Drag enabled (mobile + desktop)');
    }

    // Reset position when panel is shown
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'class') {
                const panel = mutation.target;
                const isHidden = panel.classList.contains('hidden');

                // Reset position when panel becomes visible
                if (!isHidden) {
                    resetPanelPosition();
                }
            }
        });
    });

    // Initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            makePanelDraggable();
            const panel = document.getElementById('infoPanel');
            if (panel) observer.observe(panel, { attributes: true });
        });
    } else {
        makePanelDraggable();
        const panel = document.getElementById('infoPanel');
        if (panel) observer.observe(panel, { attributes: true });
    }
})();
