document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.dashboard-sidebar a');
    const dashboardSections = document.querySelectorAll('.dashboard-section');

    function switchSection(targetId) {
        // Remove 'active' from all links and sections
        navLinks.forEach(link => link.classList.remove('active'));
        dashboardSections.forEach(section => section.classList.remove('active'));

        // Activate the clicked link and target section
        const targetLink = document.querySelector(`.dashboard-sidebar a[href="#${targetId}"]`);
        const targetSection = document.getElementById(targetId);

        if (targetLink) targetLink.classList.add('active');
        if (targetSection) targetSection.classList.add('active');
    }

    // Add click handlers to sidebar links
    navLinks.forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const id = link.getAttribute('href').replace('#', '');
            switchSection(id);
            history.replaceState(null, '', `#${id}`);
        });
    });

    // On page load, activate section by hash (if exists)
    const hash = window.location.hash.substring(1);
    if (hash && document.getElementById(hash)) {
        switchSection(hash);
    } else {
        // Fallback to first section
        const defaultId = navLinks[0].getAttribute('href').replace('#', '');
        switchSection(defaultId);
    }
});
