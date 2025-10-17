// static/chat.js - kompletny
document.addEventListener("DOMContentLoaded", function () {
    const socket = io();

    const messagesEl = document.getElementById("messages");
    const msgInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const roomInput = document.getElementById("roomInput");

    // helper: append message
    function appendMessage(username, message, timestamp) {
        const div = document.createElement("div");
        div.className = "message";
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = `${username} • ${timestamp}`;
        const body = document.createElement("div");
        body.className = "body";
        body.textContent = message;
        div.appendChild(meta);
        div.appendChild(body);
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // receive historical messages for a room (optional)
    socket.on("load_messages", (msgs) => {
        messagesEl.innerHTML = "";
        msgs.forEach(m => appendMessage(m.username, m.message, m.timestamp));
    });

    // receive real-time message
    socket.on("receive_message", (data) => {
        // if room filtering used, server sends room in payload (optional)
        appendMessage(data.username, data.message, data.timestamp || new Date().toISOString());
    });

    sendBtn.addEventListener("click", () => {
        const msg = msgInput.value.trim();
        const room = roomInput.value.trim() || null;
        if (!msg) return;
        socket.emit("send_message", { message: msg, room: room });
        msgInput.value = "";
    });

    // support Enter key
    msgInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            sendBtn.click();
        }
    });

    // join room button behaviour (if user enters room name and focuses out, join and load)
    roomInput.addEventListener("change", () => {
        const room = roomInput.value.trim();
        if (room) {
            socket.emit("join_room", { room: room });
        } else {
            // no room -> load global history by joining null (server returns global messages on default)
            socket.emit("join_room", { room: null });
        }
    });

    // auto-join nothing to load global chat
    socket.emit("join_room", { room: null });
});
