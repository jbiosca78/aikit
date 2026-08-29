(function () {
    const _script = document.currentScript || document.querySelector('script[src*="chat-popup"]');

    function getConfig() {
        const d = _script ? _script.dataset : {};
        return {
            title:       d.title       || "Chat IA",
            initialText: d.initialText || "Pregunta lo que quieras y nuestro asistente de IA te responderá.",
            placeholder: d.placeholder || "¿En qué puedo ayudarte?",
            apiUrl:      d.apiUrl      || "http://localhost:8000/chat",
            storageKey:  d.storageKey  || "aikit-chat-popup-v1",
        };
    }

    function loadState(cfg) {
        const newId = () => `chat-${Date.now()}`;
        try {
            const raw = localStorage.getItem(cfg.storageKey);
            if (!raw) {
                return { open: false, conversation_id: newId(), messages: [] };
            }
            const parsed = JSON.parse(raw);
            return {
                open: Boolean(parsed.open),
                conversation_id: parsed.conversation_id || newId(),
                messages: Array.isArray(parsed.messages) ? parsed.messages : [],
            };
        } catch (_err) {
            return { open: false, conversation_id: newId(), messages: [] };
        }
    }

    function saveState(cfg, state) {
        localStorage.setItem(cfg.storageKey, JSON.stringify(state));
    }

    // Sesión firmada por el backend: aísla el historial de cada visitante.
    async function getSessionToken(cfg) {
        const key = `${cfg.storageKey}-session`;
        const cached = localStorage.getItem(key);
        if (cached) return cached;

        try {
            const res = await fetch(cfg.apiUrl.replace(/\/chat$/, "/session"), { method: "POST" });
            if (!res.ok) return "";
            const data = await res.json();
            const token = data && data.token ? String(data.token) : "";
            if (token) localStorage.setItem(key, token);
            return token;
        } catch (_err) {
            return "";
        }
    }

    function createWidget(cfg) {
        const widget = document.createElement("section");
        widget.className = "chat-popup";
        widget.innerHTML = `
            <header class="chat-popup-header">
                <div>
                    <strong>${cfg.title}</strong>
                </div>
                <button class="chat-popup-close" type="button" aria-label="Cerrar chat">x</button>
            </header>
            <div class="chat-popup-messages" aria-live="polite"></div>
            <form class="chat-popup-form">
                <textarea class="chat-popup-input" rows="2" placeholder="${cfg.placeholder}"></textarea>
                <button class="chat-popup-send" type="submit">Enviar</button>
            </form>
        `;
        document.body.appendChild(widget);
        return widget;
    }

    function appendMessage(container, role, content, error) {
        const node = document.createElement("article");
        node.className = `chat-popup-msg ${role}${error ? " error" : ""}`;
        node.textContent = content;
        container.appendChild(node);
        container.scrollTop = container.scrollHeight;
        return node;
    }

    function renderMessages(container, state, cfg) {
        container.innerHTML = "";
        if (!state.messages.length) {
            const empty = document.createElement("div");
            empty.className = "chat-popup-empty";
            empty.textContent = cfg.initialText;
            container.appendChild(empty);
            return;
        }

        state.messages.forEach((msg) => {
            appendMessage(container, msg.role, msg.content, Boolean(msg.error));
        });
    }

    async function sendMessage(cfg, state, elements) {
        const message = elements.input.value.trim();
        if (!message) {
            return;
        }

        state.messages.push({ role: "user", content: message, ts: Date.now() });
        saveState(cfg, state);
        appendMessage(elements.messages, "user", message, false);

        elements.input.value = "";
        elements.send.disabled = true;

        const thinkingNode = appendMessage(elements.messages, "assistant", "Pensando...", false);
        thinkingNode.classList.add("loading");

        try {
            const token = await getSessionToken(cfg);
            const headers = { "Content-Type": "application/json" };
            if (token) headers["x-session-token"] = token;

            const response = await fetch(cfg.apiUrl, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    conversation_id: state.conversation_id,
                    message,
                }),
            });

            if (!response.ok) {
                const detail = await response.text();
                throw new Error(`HTTP ${response.status}: ${detail}`);
            }

            const data = await response.json();
            const answer = data && data.answer ? String(data.answer) : "Sin respuesta del asistente";

            thinkingNode.classList.remove("loading");
            thinkingNode.textContent = answer;

            state.messages.push({ role: "assistant", content: answer, ts: Date.now() });
            saveState(cfg, state);
        } catch (err) {
            const text = `No se pudo conectar con el asistente: ${err.message}`;
            thinkingNode.classList.remove("loading");
            thinkingNode.classList.add("error");
            thinkingNode.textContent = text;

            state.messages.push({ role: "assistant", content: text, error: true, ts: Date.now() });
            saveState(cfg, state);
        } finally {
            elements.send.disabled = false;
            elements.input.focus();
        }
    }

    function openWidget(cfg, state, widget) {
        state.open = true;
        saveState(cfg, state);
        widget.classList.add("open");
    }

    function closeWidget(cfg, state, widget) {
        state.open = false;
        saveState(cfg, state);
        widget.classList.remove("open");
    }

    function bindTriggers(cfg, state, widget) {
        const triggers = document.querySelectorAll('[data-chat-trigger]');
        triggers.forEach((trigger) => {
            trigger.addEventListener("click", (event) => {
                event.preventDefault();
                openWidget(cfg, state, widget);
            });
        });
    }

    function init() {
        const cfg = getConfig();
        const state = loadState(cfg);
        const widget = createWidget(cfg);
        const messages = widget.querySelector(".chat-popup-messages");
        const form = widget.querySelector(".chat-popup-form");
        const input = widget.querySelector(".chat-popup-input");
        const send = widget.querySelector(".chat-popup-send");
        const closeBtn = widget.querySelector(".chat-popup-close");

        renderMessages(messages, state, cfg);
        bindTriggers(cfg, state, widget);

        if (state.open) {
            widget.classList.add("open");
        }

        closeBtn.addEventListener("click", () => closeWidget(cfg, state, widget));

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            await sendMessage(cfg, state, { messages, input, send });
        });

        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                form.requestSubmit();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
