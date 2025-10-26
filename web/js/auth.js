// auth.js – quản lý đăng nhập, lưu phiên, kiểm tra quyền truy cập

// Lưu session
function saveUser(user, remember = false) {
  if (remember) localStorage.setItem("eduground_user", JSON.stringify(user));
  else sessionStorage.setItem("eduground_user", JSON.stringify(user));
}

// Lấy session
function getUser() {
  const s1 = sessionStorage.getItem("eduground_user");
  const s2 = localStorage.getItem("eduground_user");
  return s1 ? JSON.parse(s1) : s2 ? JSON.parse(s2) : null;
}

// Xóa session
function clearUser() {
  sessionStorage.removeItem("eduground_user");
  localStorage.removeItem("eduground_user");
}

// Hàm đăng nhập chính
async function doLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const remember = document.getElementById("rememberMe").checked;
  const msg = document.getElementById("errorMsg");

  if (!username || !password) {
    msg.textContent = "Vui lòng nhập đủ thông tin.";
    return;
  }

  try {
    const res = await fetch("data/accounts.json");
    const data = await res.json();
    const user = data.users.find(
      u => u.username.toLowerCase() === username.toLowerCase() && u.password === password
    );

    if (!user) {
      msg.textContent = "Sai tài khoản hoặc mật khẩu.";
      return;
    }

    saveUser(user, remember);
    redirectByRole(user.role);
  } catch (e) {
    console.error(e);
    msg.textContent = "Không thể kết nối server.";
  }
}

// Tự động chuyển hướng theo role
function redirectByRole(role) {
  switch (role) {
    case "teacher":
      window.location.href = "reminders.html";
      break;
    case "leader":
    case "assistant":
      window.location.href = "index.html";
      break;
    case "admin":
      window.location.href = "dashboard.html";
      break;
    default:
      window.location.href = "chatbot.html";
  }
}

// Kiểm tra người chưa login
function requireLogin() {
  const user = getUser();
  if (!user) {
    window.location.href = "login.html";
    return false;
  }
  return true;
}

// Dành cho mỗi trang khác, gọi ở đầu <script>
function setupPageAccess(requiredRoles = []) {
  const user = getUser();
  if (!user) {
    window.location.href = "login.html";
    return;
  }
  if (requiredRoles.length && !requiredRoles.includes(user.role)) {
    alert("Bạn không có quyền truy cập trang này.");
    redirectByRole(user.role);
  }
}