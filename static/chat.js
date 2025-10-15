const socket = io();

let currentChatUserId = null;

document.querySelectorAll("#user-list li").forEach(li => {
    li.addEventListener("click", () => {
        const receiverId = li.getAttribute("data-id");
        currentChatUserId = receiverId;
        document.getElementById("chat-with").textContent = "Rozmowa z: " + li.textContent;
        document.getElementById("chat-box").innerHTML = "";

        socket.emit("join_chat", {receiver_id: parseInt(receiverId)});
    });
});

socket.on("load_messages", messages => {
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";
    messages.forEach(msg => {
        const div = document.createElement("div");
        div.className = "message" + (msg.sender === "{{ username }}" ? " sender" : "");
        div.textContent = msg.sender + ": " + msg.body;
        chatBox.appendChild(div);
    });
    chatBox.scrollTop = chatBox.scrollHeight;
});

document.getElementById("chat-form").addEventListener("submit", e => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const body = input.value.trim();
    if (body && currentChatUserId) {
        socket.emit("send_message", {receiver_id: parseInt(currentChatUserId), body: body});
        input.value = "";
    }
});

socket.on("receive_message", data => {
    if (data.room === `room_${Math.min({{ my_id }}, ${currentChatUserId})}_${Math.max({{ my_id }}, ${currentChatUserId})}`) {
        const chatBox = document.getElementById("chat-box");
        const div = document.createElement("div");
        div.className = "message" + (data.sender === "{{ username }}" ? " sender" : "");
        div.textContent = data.sender + ": " + data.body;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});
