// js/auth.js
const API_BASE = ""; // relative to same origin

function showMessage(msg, type = "info") {
  const el = document.getElementById("msg");
  if (el) {
    el.textContent = msg;
    el.style.color = type === "error" ? "red" : "green";
  }
}

// Kiểm tra session khi load trang
window.addEventListener("DOMContentLoaded", () => {
  const user = JSON.parse(localStorage.getItem("user") || "null");

  // Nếu đã đăng nhập, redirect sang index
  if (user && window.location.pathname.includes("login.html")) {
    window.location.href = "index.html";
    return;
  }

  // Nếu chưa đăng nhập mà vào trang khác, redirect về login
  if (!user && !window.location.pathname.includes("login.html")) {
    window.location.href = "login.html";
  }
});

// Đăng nhập
function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const remember = document.getElementById("remember").checked;

  if (!username || !password) {
    showMessage("Vui lòng nhập đủ thông tin!", "error");
    return;
  }

  fetch(`${API_BASE}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.ok) {
        const userData = {
          username: data.user,
          role: data.role,
          time: Date.now(),
        };
        if (remember) localStorage.setItem("user", JSON.stringify(userData));
        else sessionStorage.setItem("user", JSON.stringify(userData));

        showMessage("Đăng nhập thành công!");
        setTimeout(() => (window.location.href = "index.html"), 800);
      } else {
        showMessage("Sai tài khoản hoặc mật khẩu!", "error");
      }
    })
    .catch((err) => {
      console.error(err);
      showMessage("Lỗi kết nối tới server!", "error");
    });
}

// Lấy user role
function getUserRole() {
  const user = JSON.parse(localStorage.getItem("user") || sessionStorage.getItem("user") || "null");
  return user ? user.role : null;
}

// Đăng xuất
function logout() {
  localStorage.removeItem("user");
  sessionStorage.removeItem("user");
  window.location.href = "login.html";
}
