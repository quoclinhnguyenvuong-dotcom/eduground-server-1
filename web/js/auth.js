// web/js/auth.js
// Quản lý login/identity cho Eduground (localStorage: 'eduground_user')

const API_BASE = ""; // nếu server chạy cùng origin để trống, nếu khác thì đặt full URL e.g. "https://eduground-server-1-3.onrender.com"

// Hiển thị thông báo nhỏ
function showMessage(msg, type = "info") {
  // simple: console + small toast if has #status element
  console[type === "error" ? "error" : "log"](msg);
  const el = document.getElementById("status") || document.getElementById("globalStatus");
  if (el) {
    el.textContent = msg;
    el.className = type;
    setTimeout(() => { if (el) el.textContent = ""; }, 4000);
  }
}

// Lưu user object: { user, role, remember: true/false }
function saveUser(obj, remember = false) {
  try {
    const u = { user: obj.user, role: obj.role, ts: Date.now() };
    localStorage.setItem("eduground_user", JSON.stringify(u));
    if (remember) {
      // also store separate key for auto-login (optional)
      localStorage.setItem("eduground_remember", JSON.stringify(u));
    } else {
      localStorage.removeItem("eduground_remember");
    }
  } catch (e) {
    console.error("saveUser failed", e);
  }
}

// Lấy user hiện tại (fallback: remember)
function getCurrentUser() {
  try {
    const raw = localStorage.getItem("eduground_user");
    if (raw) return JSON.parse(raw);
    const rem = localStorage.getItem("eduground_remember");
    if (rem) {
      localStorage.setItem("eduground_user", rem);
      return JSON.parse(rem);
    }
    return null;
  } catch (e) {
    return null;
  }
}

// Remove user
function clearUser() {
  localStorage.removeItem("eduground_user");
  // keep remember? we remove too to be safe on logout
  localStorage.removeItem("eduground_remember");
}

// Đăng xuất
function logout(redirect = "login.html") {
  clearUser();
  window.location.href = redirect;
}

// Kiểm tra auth khi vào trang (gọi từ DOMContentLoaded)
async function ensureAuth(allowGuest = false) {
  const u = getCurrentUser();
  if (!u) {
    if (allowGuest) return null;
    window.location.href = "login.html";
    return null;
  }
  // Optionally verify token/credentials server-side (best-effort)
  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u.user, password: "" }) // we don't have pw; server can support a "check user exists" endpoint — fallback skip check
    });
    // Some servers return 401 because empty password; treat success as presence check
    // We'll just assume local info is valid for now — update UI
  } catch (e) {
    // ignore network errors for now; still allow local usage
    console.warn("Auth check network failed", e);
  }
  // Update UI elements if present
  const nameEl = document.querySelector("#currentUser") || document.querySelector("#userLabel");
  if (nameEl) nameEl.textContent = u.user;
  return u;
}// Hàm login gọi từ form login.html
async function doLogin(username, password, remember=false) {
  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password })
    });
    if (!res.ok) {
      const err = await res.json().catch(()=>({error: "Không thể đọc lỗi"}));
      showMessage(err.error || ("Lỗi đăng nhập: " + res.status), "error");
      return false;
    }
    const data = await res.json();
    if (data.ok) {
      saveUser({ user: data.user, role: data.role }, remember);
      showMessage("Đăng nhập thành công: " + data.user, "info");
      // redirect: nếu đang ở login page, vào index; nếu query param next exists, redirect there
      const urlParams = new URLSearchParams(window.location.search);
      const next = urlParams.get("next") || "index.html";
      window.location.href = next;
      return true;
    } else {
      showMessage(data.error || "Sai tên/mật khẩu", "error");
      return false;
    }
  } catch (e) {
    console.error("doLogin err", e);
    showMessage("Lỗi kết nối máy chủ", "error");
    return false;
  }
}

// Utility: lấy role
function getUserRole() {
  const u = getCurrentUser();
  return u ? (u.role || null) : null;
}

// Export to global to be callable from inline onclicks
window.auth = {
  doLogin,
  logout,
  ensureAuth,
  getCurrentUser,
  getUserRole,
  saveUser,
  clearUser
};
