async function login() {
  const user = document.getElementById("username").value.trim();
  const pass = document.getElementById("password").value.trim();
  const error = document.getElementById("error");

  try {
    const res = await fetch("accounts.json");
    const accounts = await res.json();

    const found = accounts.find(acc => acc.user === user && acc.pass === pass);
    if (!found) {
      error.textContent = "❌ Sai tên đăng nhập hoặc mật khẩu!";
      return;
    }

    localStorage.setItem("userRole", found.role);
    localStorage.setItem("username", found.user);
    window.location.href = "index.html";
  } catch (err) {
    error.textContent = "⚠️ Không thể tải dữ liệu tài khoản!";
  }
}
