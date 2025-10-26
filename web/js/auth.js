// -------------------------------
// AUTH.JS - Eduground Auth System
// -------------------------------

// Hiển thị thông báo ra màn hình
function showMessage(message, type = "info") {
  const msg = document.createElement("div");
  msg.className = `alert ${type}`;
  msg.textContent = message;
  document.body.appendChild(msg);
  setTimeout(() => msg.remove(), 3000);
}

// Xác thực đăng nhập
function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const remember = document.getElementById("remember").checked;

  if (!username || !password) {
    showMessage("Vui lòng nhập đủ thông tin đăng nhập!", "error");
    return;
  }

  fetch("accounts.json")
    .then(res => res.json())
    .then(data => {
      const user = data.users.find(
        u => u.username.toLowerCase() === username.toLowerCase() && u.password === password
      );

      if (user) {
        localStorage.setItem("user", JSON.stringify(user));

        if (remember) {
          localStorage.setItem("rememberUser", JSON.stringify(user));
        } else {
          localStorage.removeItem("rememberUser");
        }

        showMessage(`Xin chào ${user.username}!`, "success");
        window.location.href = "index.html";
      } else {
        showMessage("Sai tài khoản hoặc mật khẩu!", "error");
      }
    })
    .catch(err => {
      console.error(err);
      showMessage("Không thể kết nối đến server!", "error");
    });
}

// Kiểm tra quyền truy cập (tự động redirect nếu chưa đăng nhập)
function ensureAuth() {
  const user = JSON.parse(localStorage.getItem("user") || "null");

  if (!user) {
    console.warn("⚠️ Không có user đăng nhập, quay lại login...");
    window.location.href = "login.html";
    return;
  }

  console.log(`✅ Authenticated: ${user.username} (${user.role})`);

  // Cập nhật giao diện người dùng hiện tại
  const userDisplay = document.querySelector("#currentUser");
  if (userDisplay) {
    userDisplay.textContent = user.username;
  }

  // Nếu là reminder page → chỉ giáo viên mới được sửa
  const isReminder = window.location.pathname.includes("reminders.html");
  if (isReminder && user.role !== "teacher" && user.role !== "admin") {
    const editButtons = document.querySelectorAll(".edit-btn");
    editButtons.forEach(btn => (btn.disabled = true));
    showMessage("Bạn không có quyền chỉnh sửa nhắc nhở!", "warning");
  }
}

// Lấy role hiện tại
function getUserRole() {
  const user = JSON.parse(localStorage.getItem("user") || "null");
  return user ? user.role : null;
}

// Đăng xuất
function logout() {
  localStorage.removeItem("user");
  localStorage.removeItem("rememberUser");
  showMessage("Đã đăng xuất!", "info");
  window.location.href = "login.html";
}

// Tự động xác thực khi load trangdocument.addEventListener("DOMContentLoaded", () => {
  const isLoginPage = window.location.pathname.includes("login.html");
  const savedUser = JSON.parse(localStorage.getItem("rememberUser") || "null");

  if (isLoginPage && savedUser) {
    localStorage.setItem("user", JSON.stringify(savedUser));
    window.location.href = "index.html";
  } else if (!isLoginPage) {
    ensureAuth();
  }
});
