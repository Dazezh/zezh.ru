(() => {
    const favicon = document.getElementById('zezh-favicon');

    const syncFavicon = () => {
        if (!favicon) return;

        favicon.href = document.visibilityState === 'hidden'
            ? favicon.dataset.hidden
            : favicon.dataset.active;
    };

    syncFavicon();
    document.addEventListener('visibilitychange', syncFavicon);
})();
