// web/js/auth.js
console.log("🔐 auth.js loaded");

// Lưu user
function saveUser(user) {
  localStorage.setItem("user", JSON.stringify(user));
}

// Lấy user hiện tại
function getUser() {
  const u = localStorage.getItem("user");
  return u ? JSON.parse(u) : null;
}

// Lấy role
function getUserRole() {
  const user = getUser();
  return user ? user.role : null;
}

// Đăng xuất
function logout() {
  localStorage.removeItem("user");
  window.location.href = "login.html";
}

// Hàm xác thực người dùng (gọi ở đầu mỗi trang)
function ensureAuth() {
  const user = getUser();

  if (!user) {
    console.warn("⚠️ Chưa đăng nhập, chuyển hướng về login.html");
    window.location.href = "login.html";
    return;
  }

  fetch("/api/login-check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: user.username, password: user.password })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        console.warn("❌ Token hết hạn hoặc sai. Quay về login.");
        localStorage.removeItem("user");
        window.location.href = "login.html";
      } else {
        console.log(`✅ Auth ok: ${user.username} (${user.role})`);
        document.querySelector("#currentUser")?.textContent = user.username;
      }
    })
    .catch(err => {
      console.error("Auth check error:", err);
      window.location.href = "login.html";
    });
}

// Hàm login (dành cho login.html)
function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!username || !password) {
    alert("Vui lòng nhập đủ thông tin!");
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
        saveUser({ username, password, role: data.role });
        console.log("✅ Login thành công, chuyển hướng về index.html");
        window.location.href = "index.html";
      } else {
        alert("Sai tài khoản hoặc mật khẩu!");
      }
    })
    .catch(err => {
      console.error("Lỗi khi đăng nhập:", err);
      alert("Không thể kết nối tới server!");
    });
}
