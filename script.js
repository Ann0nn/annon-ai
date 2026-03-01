const SERVER = "https://annon-ai-production.up.railway.app";

const chatBox = document.getElementById("chatBox");
const userInput = document.getElementById("userInput");
const chatList = document.getElementById("chatList");

let typewriterSpeed = 16;
let systemPrompt = "You are Annon AI, a helpful and friendly assistant.";
let aiName = "Annon AI";
let currentUsername = "";

let sessions = {};
let currentSessionId = null;

function getToken() {
  return localStorage.getItem("annon_token");
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getToken()}`
  };
}

window.onload = async () => {
  const token = getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  try {
    const res = await fetch(`${SERVER}/me`, { headers: authHeaders() });
    const data = await res.json();
    if (data.error) {
      window.location.href = "login.html";
      return;
    }
    currentUsername = data.username;
    document.getElementById("chatTitle").textContent = aiName;
  } catch (e) {
    window.location.href = "login.html";
    return;
  }

  await loadSessionsFromServer();
  if (Object.keys(sessions).length === 0) newChat();
};

userInput.addEventListener("keydown", e => {
  if (e.key === "Enter") sendMessage();
});

function getTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function generateId() {
  return Date.now().toString();
}

// ========== LOAD SESSIONS ==========
async function loadSessionsFromServer() {
  try {
    const res = await fetch(`${SERVER}/sessions`, { headers: authHeaders() });
    const data = await res.json();

    sessions = {};
    for (const s of data) {
      sessions[s.id] = {
        id: s.id,
        title: s.title,
        history: [{ role: "system", content: systemPrompt }],
        messages: []
      };
    }

    renderSidebar();

    if (data.length > 0) {
      await switchToSession(data[0].id);
    }
  } catch (e) {
    console.error("Failed to load sessions", e);
  }
}

// ========== SESSIONS ==========
function newChat() {
  const id = generateId();
  sessions[id] = {
    id,
    title: "New Chat",
    history: [{ role: "system", content: systemPrompt }],
    messages: []
  };
  switchToSession(id);
  renderSidebar();
}

async function switchToSession(id) {
  currentSessionId = id;
  document.querySelectorAll(".chat-list-item").forEach(i => {
    i.classList.toggle("active", i.dataset.id === id);
  });

  chatBox.innerHTML = "";

  try {
    const res = await fetch(`${SERVER}/sessions/${id}`, { headers: authHeaders() });
    const messages = await res.json();

    if (messages.length === 0) {
      appendBotWelcome();
    } else {
      sessions[id].messages = messages;
      sessions[id].history = [{ role: "system", content: systemPrompt }];
      messages.forEach(m => {
        renderMessage(m.text, m.sender, m.time, false);
        sessions[id].history.push({
          role: m.sender === "bot" ? "assistant" : "user",
          content: m.text
        });
      });
    }
  } catch (e) {
    appendBotWelcome();
  }
}

function renderSidebar() {
  chatList.innerHTML = "";
  Object.values(sessions).forEach(session => {
    const item = document.createElement("div");
    item.classList.add("chat-list-item");
    item.dataset.id = session.id;
    if (session.id === currentSessionId) item.classList.add("active");
    item.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      ${session.title}
    `;
    item.onclick = () => switchToSession(session.id);
    chatList.appendChild(item);
  });
}

// ========== MESSAGES ==========
function appendBotWelcome() {
  renderMessage(`Hey ${currentUsername}! I'm ${aiName}. Ask me anything 🙂`, "bot", getTime(), false);
}

function renderMessage(text, sender, time, animate) {
  const row = document.createElement("div");
  row.classList.add("message-row", sender);

  const avatar = document.createElement("div");
  avatar.classList.add("avatar", sender);
  avatar.innerHTML = sender === "bot"
    ? `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 3a3 3 0 1 1-3 3 3 3 0 0 1 3-3zm0 14.2a7.2 7.2 0 0 1-6-3.22c.03-2 4-3.08 6-3.08s5.97 1.09 6 3.08a7.2 7.2 0 0 1-6 3.22z"/></svg>`
    : currentUsername.charAt(0).toUpperCase();

  const wrap = document.createElement("div");
  wrap.classList.add("bubble-wrap");
  if (sender === "user") wrap.style.alignItems = "flex-end";

  const bubble = document.createElement("div");
  bubble.classList.add("message-bubble");

  const ts = document.createElement("span");
  ts.classList.add("timestamp");
  ts.textContent = time;

  wrap.appendChild(bubble);
  wrap.appendChild(ts);
  row.appendChild(avatar);
  row.appendChild(wrap);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;

  animate ? typeWriter(bubble, text) : (bubble.textContent = text);

  return { row, bubble, wrap };
}

function appendTyping() {
  const row = document.createElement("div");
  row.classList.add("message-row", "bot");

  const avatar = document.createElement("div");
  avatar.classList.add("avatar", "bot");
  avatar.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 3a3 3 0 1 1-3 3 3 3 0 0 1 3-3zm0 14.2a7.2 7.2 0 0 1-6-3.22c.03-2 4-3.08 6-3.08s5.97 1.09 6 3.08a7.2 7.2 0 0 1-6 3.22z"/></svg>`;

  const wrap = document.createElement("div");
  wrap.classList.add("bubble-wrap");

  const bubble = document.createElement("div");
  bubble.classList.add("message-bubble");
  bubble.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div>`;

  wrap.appendChild(bubble);
  row.appendChild(avatar);
  row.appendChild(wrap);
  chatBox.appendChild(row);
  chatBox.scrollTop = chatBox.scrollHeight;
  return { row, bubble, wrap };
}

// ========== SEND ==========
async function sendMessage() {
  const message = userInput.value.trim();
  if (!message) return;

  const session = sessions[currentSessionId];
  const time = getTime();

  renderMessage(message, "user", time, false);
  session.history.push({ role: "user", content: message });
  if (!session.messages) session.messages = [];
  session.messages.push({ text: message, sender: "user", time });

  if (session.messages.length === 1) {
    session.title = message.length > 28 ? message.slice(0, 28) + "..." : message;
    renderSidebar();
  }

  userInput.value = "";
  const typing = appendTyping();

  try {
    const response = await fetch(`${SERVER}/chat`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        messages: session.history,
        session_id: currentSessionId,
        user_message: message,
        session_title: session.title
      })
    });

    const data = await response.json();
    const reply = data.reply;
    const replyTime = data.time;

    session.history.push({ role: "assistant", content: reply });
    session.messages.push({ text: reply, sender: "bot", time: replyTime });

    typing.bubble.innerHTML = "";
    typeWriter(typing.bubble, reply);

    const ts = document.createElement("span");
    ts.classList.add("timestamp");
    ts.textContent = replyTime;
    typing.wrap.appendChild(ts);

  } catch (error) {
    typing.bubble.textContent = "Oops! Something went wrong.";
  }
}

// ========== TYPEWRITER ==========
function typeWriter(element, text) {
  let i = 0;
  element.textContent = "";
  function type() {
    if (i < text.length) {
      element.textContent += text.charAt(i);
      i++;
      chatBox.scrollTop = chatBox.scrollHeight;
      setTimeout(type, typewriterSpeed);
    }
  }
  type();
}

// ========== MODALS ==========
function openModal(id) { document.getElementById(id).classList.add("open"); }
function closeModal(id) { document.getElementById(id).classList.remove("open"); }
function closeModalOutside(event, id) { if (event.target.id === id) closeModal(id); }

// ========== SETTINGS ==========
function saveSettings() {
  aiName = document.getElementById("settingAIName").value.trim() || "Annon AI";
  systemPrompt = document.getElementById("settingSystemPrompt").value.trim();
  typewriterSpeed = parseInt(document.getElementById("settingSpeed").value);
  document.getElementById("chatTitle").textContent = aiName;
  const theme = document.getElementById("settingTheme").value;
  document.body.classList.toggle("light", theme === "light");
  closeModal("settingsModal");
}

// ========== SHARE / DELETE ==========
function shareChat() {
  navigator.clipboard.writeText(window.location.href);
  alert("Link copied to clipboard!");
}

async function deleteChat() {
  if (confirm("Delete this chat?")) {
    await fetch(`${SERVER}/sessions/${currentSessionId}`, {
      method: "DELETE",
      headers: authHeaders()
    });
    delete sessions[currentSessionId];
    const remaining = Object.keys(sessions);
    remaining.length > 0 ? switchToSession(remaining[remaining.length - 1]) : newChat();
    renderSidebar();
  }
}

// ========== LOGOUT ==========
async function logout() {
  await fetch(`${SERVER}/logout`, {
    method: "POST",
    headers: authHeaders()
  });
  localStorage.removeItem("annon_token");
  localStorage.removeItem("annon_username");
  window.location.href = "login.html";
}