// web/js/auth.js
console.log("✅ auth.js loaded OK");

// --- Lưu & lấy thông tin người dùng ---
function saveUser(user) {
  localStorage.setItem("user", JSON.stringify(user));
}

function getUser() {
  const u = localStorage.getItem("user");
  return u ? JSON.parse(u) : null;
}

function getUserRole() {
  const user = getUser();
  return user ? user.role : null;
}

// --- Đăng xuất ---
function logout() {
  localStorage.removeItem("user");
  window.location.href = "login.html";
}

// --- Kiểm tra đăng nhập khi vào trang ---
function ensureAuth() {
  const user = getUser();
  if (!user) {
    console.warn("⚠️ Người dùng chưa đăng nhập, quay về login.html");
    window.location.href = "login.html";
    return;
  }

  // Gọi API để xác minh lại (nếu muốn)
  fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: user.username,
      password: user.password
    })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        console.warn("❌ Xác thực thất bại, xóa user và quay về login");
        localStorage.removeItem("user");
        window.location.href = "login.html";
      } else {
        console.log(`🔐 Đăng nhập hợp lệ: ${user.username} (${user.role})`);
        document.querySelector("#currentUser")?.textContent = user.username;
      }
    })
    .catch(err => {
      console.error("⚠️ Không thể xác thực user:", err);
      window.location.href = "login.html";
    });
}

// --- Đăng nhập ---
function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    alert("⚠️ Vui lòng nhập đủ thông tin!");
    return;
  }

  fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        saveUser({
          username,
          password,
          role: data.role
        });
        console.log("✅ Đăng nhập thành công!");
        window.location.href = "index.html";
      } else {
        alert("❌ Sai tài khoản hoặc mật khẩu!");
      }
    })
    .catch(err => {
      console.error("Lỗi khi đăng nhập:", err);
      alert("Không thể kết nối tới server!");
    });
}
