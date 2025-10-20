// localchat-core.js
const currentUser = sessionStorage.getItem("username");
if (!currentUser) {
  window.location.href = "login.html";
}

// UI elements
const msgContainer = document.getElementById("messages");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const sidebar = document.getElementById("sidebar");

// load messages from localStorage (array)
function loadMessages() {
  const msgs = JSON.parse(localStorage.getItem("messages") || "[]");
  msgContainer.innerHTML = "";
  msgs.forEach(m => addMessage(m.text, m.user === currentUser ? 'sent' : 'received', m.user, m.time));
}

// render one message
function addMessage(text, type, user="?", time=null) {
  const div = document.createElement("div");
  div.classList.add("message", type);
  const when = time ? new Date(time).toLocaleTimeString() : "";
  div.innerHTML = `<strong style="font-size:12px">${user}</strong> <small style="color:#666">${when}</small><div style="margin-top:6px">${escapeHtml(text)}</div>`;
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

// send and save
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text) return;
  const msgs = JSON.parse(localStorage.getItem("messages") || "[]");
  const obj = { user: currentUser, text: text, time: Date.now() };
  msgs.push(obj);
  localStorage.setItem("messages", JSON.stringify(msgs));
  addMessage(text, 'sent', currentUser, obj.time);
  msgInput.value = "";
}

// escape html
function escapeHtml(s){ return String(s).replaceAll('<','&lt;').replaceAll('>','&gt;'); }

// event handlers
sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keypress", e => { if (e.key === "Enter") { e.preventDefault(); sendMessage(); } });

// show basic sidebar (history) from messages
function loadSidebar() {
  sidebar.innerHTML = "<p style='padding:10px;font-weight:bold;'>Danh sách đoạn chat</p>";
  // simple grouping by user (most recent)
  const msgs = JSON.parse(localStorage.getItem("messages") || "[]");
  const map = {};
  for (let i=msgs.length-1;i>=0;i--){
    const u = msgs[i].user || "unknown";
    if (!map[u]) map[u] = msgs[i];
  }
  Object.keys(map).forEach(u => {
    const el = document.createElement("div");
    el.style.padding = "10px";
    el.style.cursor = "pointer";
    el.textContent = u;
    el.onclick = () => { openChatWith(u); };
    sidebar.appendChild(el);
  });
}

// open chat with user (quick simulate: prefill)
function openChatWith(u){
  msgInput.value = `@${u} `;
  msgInput.focus();
}

window.onload = () => {
  document.getElementById("usernameDisplay").innerText = currentUser || "Khách";
  loadMessages();
  loadSidebar();
};
