// web/js/auth.js

const API_BASE = window.location.origin.includes("onrender.com")
  ? window.location.origin
  : "https://eduground-server-1.onrender.com";

// Hiện thông báo (message UI)
function showMessage(msg, type = "info") {
  const el = document.querySelector("#messageBox");
  if (!el) return console.log(`[${type}]`, msg);
  el.textContent = msg;
  el.className = `msg ${type}`;
  setTimeout(() => {
    el.textContent = "";
    el.className = "msg";
  }, 3000);
}

// Đăng nhập
async function doLogin() {
  const username = document.querySelector("#username").value.trim();
  const password = document.querySelector("#password").value.trim();

  if (!username || !password) {
    showMessage("⚠️ Vui lòng nhập đầy đủ thông tin!", "error");
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!resp.ok) {
      showMessage("❌ Sai tài khoản hoặc mật khẩu!", "error");
      return;
    }

    const data = await resp.json();
    if (data.ok) {
      localStorage.setItem("user", JSON.stringify(data));
      showMessage("✅ Đăng nhập thành công!", "success");
      setTimeout(() => (window.location.href = "index.html"), 800);
    } else {
      showMessage(data.error || "Đăng nhập thất bại!", "error");
    }
  } catch (e) {
    console.error(e);
    showMessage("🚫 Không thể kết nối tới server.", "error");
  }
}

// Kiểm tra trạng thái đăng nhập
function ensureAuth() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  if (!user) {
    window.location.href = "login.html";
    return;
  }

  fetch(`${API_BASE}/api/check-auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: user.username }),
  })
    .then(res => res.json())
    .then(data => {
      if (!data.ok) {
        localStorage.removeItem("user");
        window.location.href = "login.html";
      } else {
        console.log(`✅ Auth ok: ${user.username} (${user.role})`);
        document.querySelector("#currentUser")?.textContent = user.username;
      }
    })
    .catch(() => {
      showMessage("Không thể xác thực người dùng!", "error");
      window.location.href = "login.html";
    });
}

// Lấy role
function getUserRole() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  return user ? user.role : null;
}

// Đăng xuất
function logout() {
  localStorage.removeItem("user");
  window.location.href = "login.html";
}
