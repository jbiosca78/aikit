// Widget de chat propio de esta variante: implementado sin framework.
(function () {
    const API_URL = "http://localhost:8001";
    const STORE_KEY = "armarios-bedrock-v1";

    function loadState() {
        try {
            const raw = localStorage.getItem(STORE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                return {
                    open: Boolean(parsed.open),
                    conversation_id: parsed.conversation_id || "chat-" + Date.now(),
                    messages: Array.isArray(parsed.messages) ? parsed.messages : [],
                    token: typeof parsed.token === "string" ? parsed.token : "",
                };
            }
        } catch (err) {
            // estado corrupto: se descarta y se empieza de nuevo
        }
        return { open: false, conversation_id: "chat-" + Date.now(), messages: [], token: "" };
    }

    function saveState(state) {
        localStorage.setItem(STORE_KEY, JSON.stringify(state));
    }

    const state = loadState();

    async function ensureToken() {
        if (state.token) return state.token;
        try {
            const res = await fetch(API_URL + "/session", { method: "POST" });
            if (!res.ok) return "";
            const data = await res.json();
            state.token = data.token || "";
            saveState(state);
            return state.token;
        } catch (err) {
            return "";
        }
    }

    const widget = document.createElement("section");
    widget.className = "chat-widget";
    widget.innerHTML = `
        <button class="chat-toggle" type="button">Chat IA</button>
        <div class="chat-panel" hidden>
            <header class="chat-header">
                <span>Asistente</span>
                <button class="chat-close" type="button" aria-label="Cerrar chat">&times;</button>
            </header>
            <div class="chat-messages" aria-live="polite"></div>
            <form class="chat-form">
                <textarea class="chat-input" rows="2" placeholder="Pregunta por medidas, stock..."></textarea>
                <button class="chat-send" type="submit">Enviar</button>
            </form>
        </div>`;
    document.body.appendChild(widget);

    const panel = widget.querySelector(".chat-panel");
    const messagesEl = widget.querySelector(".chat-messages");
    const form = widget.querySelector(".chat-form");
    const input = widget.querySelector(".chat-input");
    const send = widget.querySelector(".chat-send");

    function appendMessage(role, text, error) {
        const node = document.createElement("div");
        node.className = "chat-message chat-" + role + (error ? " chat-error" : "");
        node.textContent = text;
        messagesEl.appendChild(node);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return node;
    }

    state.messages.forEach(function (m) {
        appendMessage(m.role, m.content, Boolean(m.error));
    });

    widget.querySelector(".chat-toggle").addEventListener("click", function () {
        panel.hidden = !panel.hidden;
        state.open = !panel.hidden;
        saveState(state);
        if (!panel.hidden) input.focus();
    });

    widget.querySelector(".chat-close").addEventListener("click", function () {
        panel.hidden = true;
        state.open = false;
        saveState(state);
    });

    if (state.open) panel.hidden = false;

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const message = input.value.trim();
        if (!message) return;

        appendMessage("user", message, false);
        state.messages.push({ role: "user", content: message });
        saveState(state);
        input.value = "";

        send.disabled = true;
        input.disabled = true;
        const pending = appendMessage("assistant", "Pensando...", false);
        pending.classList.add("chat-loading");

        try {
            const token = await ensureToken();
            const headers = { "Content-Type": "application/json" };
            if (token) headers["x-session-token"] = token;

            const res = await fetch(API_URL + "/chat", {
                method: "POST",
                headers: headers,
                body: JSON.stringify({
                    conversation_id: state.conversation_id,
                    message: message,
                }),
            });
            if (!res.ok) throw new Error("HTTP " + res.status);

            const data = await res.json();
            const answer = data.answer || "Sin respuesta del asistente";
            pending.classList.remove("chat-loading");
            pending.textContent = answer;
            state.messages.push({ role: "assistant", content: answer });
            saveState(state);
        } catch (err) {
            pending.classList.add("chat-error");
            pending.classList.remove("chat-loading");
            pending.textContent = "No se pudo conectar con el asistente: " + err.message;
            state.messages.push({ role: "assistant", content: pending.textContent, error: true });
            saveState(state);
        } finally {
            send.disabled = false;
            input.disabled = false;
            input.focus();
        }
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
})();
