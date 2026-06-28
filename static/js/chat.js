const panel = document.getElementById("chat-panel");
const toggleBtn = document.getElementById("chat-toggle-btn");
const resetBtn = document.getElementById("chat-reset-btn");
const messagesEl = document.getElementById("chat-messages");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("chat-send-btn");

let ws = null;
let reconnectDelay = 1000;
let streamingEl = null;

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/chat`;
}

function connect() {
  ws = new WebSocket(wsUrl());
  ws.onopen = () => { reconnectDelay = 1000; };
  ws.onclose = () => {
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    switch (msg.type) {
      case "stream": handleStream(msg); break;
      case "stream_end": handleStreamEnd(msg); break;
      case "content_updated": handleContentUpdated(); break;
      case "history": handleHistory(msg); break;
      case "error": handleError(msg); break;
    }
  };
}

function handleStream(msg) {
  if (!streamingEl) {
    streamingEl = appendMessage("assistant", "");
  }
  streamingEl.textContent += msg.content;
  scrollToBottom();
}

function handleStreamEnd(_msg) {
  streamingEl = null;
  sendBtn.disabled = false;
  inputEl.disabled = false;
}

function handleContentUpdated() {
  if (typeof htmx !== "undefined") {
    htmx.ajax("GET", location.pathname, { target: "#main-content", swap: "innerHTML" });
  }
}

function handleHistory(msg) {
  messagesEl.innerHTML = "";
  for (const m of msg.messages) {
    appendMessage(m.role, m.content);
  }
}

function handleError(msg) {
  streamingEl = null;
  sendBtn.disabled = false;
  inputEl.disabled = false;
  appendMessage("assistant", `Error: ${msg.message}`);
}

function appendMessage(role, content) {
  const el = document.createElement("div");
  el.className = `chat-msg ${role}`;
  el.textContent = content;
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function sendMessage() {
  const content = inputEl.value.trim();
  if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;
  appendMessage("user", content);
  ws.send(JSON.stringify({ type: "message", content }));
  inputEl.value = "";
  sendBtn.disabled = true;
  inputEl.disabled = true;
}

function toggleChat() {
  const open = panel.style.display === "none";
  panel.style.display = open ? "flex" : "none";
  document.body.classList.toggle("chat-open", open);
  localStorage.setItem("chat-open", open ? "1" : "0");
}

function loadHistory() {
  fetch("/api/chat/history")
    .then((r) => r.json())
    .then((data) => handleHistory(data));
}

toggleBtn.addEventListener("click", toggleChat);
resetBtn.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "reset" }));
  }
});
sendBtn.addEventListener("click", sendMessage);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    sendMessage();
  }
});

if (localStorage.getItem("chat-open") === "1") {
  panel.style.display = "flex";
  document.body.classList.add("chat-open");
}

connect();
loadHistory();
