// auth.js — Dùng chung cho mọi trang trừ login.html

window.auth = {
  // Kiểm tra xác thực
  ensureAuth: async function () {
    const userData = localStorage.getItem("eduground_user");
    if (!userData) {
      console.warn("❌ Không có user → redirect về login.html");
      window.location.replace("login.html");
      return null;
    }

    try {
      const user = JSON.parse(userData);
      const res = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, role: user.role })
      });
      const data = await res.json();

      if (!data.ok) {
        console.warn("❌ Hết hạn hoặc sai → logout");
        localStorage.removeItem("eduground_user");
        window.location.replace("login.html");
        return null;
      }

      console.log("✅ Auth OK:", user.username, user.role);
      return user;
    } catch (err) {
      console.error("⚠️ Lỗi xác thực:", err);
      localStorage.removeItem("eduground_user");
      window.location.replace("login.html");
      return null;
    }
  },

  // Đăng xuất
  logout: function () {
    localStorage.removeItem("eduground_user");
    window.location.replace("login.html");
  }
};
