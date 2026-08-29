(function () {
    // Edit here to customize the widget for this project
    const CONFIG = {
        apiUrl:      'http://localhost:8000/chat',
        storageKey:  'armarios-mario-v1',
        title:       'Chat IA',
        placeholder: 'Pregunta por medidas, baldas, stock...',
        initialText: 'Te ayudo a decidir qué armario te encaja mejor.',
    };

    // Inject chat trigger link into the site nav
    const nav = document.querySelector('.nav-links');
    if (nav) {
        const a = document.createElement('a');
        a.href = '#';
        a.dataset.chatTrigger = '';
        a.textContent = CONFIG.title;
        nav.appendChild(a);
    }

    // Inject chat-popup.js with config as data-* attributes
    const s = document.createElement('script');
    s.src = 'chat-popup.js';
    s.dataset.apiUrl      = CONFIG.apiUrl;
    s.dataset.storageKey  = CONFIG.storageKey;
    s.dataset.title       = CONFIG.title;
    s.dataset.placeholder = CONFIG.placeholder;
    s.dataset.initialText = CONFIG.initialText;
    document.body.appendChild(s);
})();
