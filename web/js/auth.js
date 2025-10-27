// web/js/auth.js
// Simple auth helper for Eduground (works with /api/login POST)
// NOTE: stores credentials in localStorage if "remember" checked. For real prod, use tokens.

function saveUserObj(u){
  localStorage.setItem('user', JSON.stringify(u));
}
function getUserObj(){
  try { return JSON.parse(localStorage.getItem('user')||'null'); } catch(e){ return null; }
}
function removeUser(){ localStorage.removeItem('user'); }

// gọi server /api/login để kiểm tra
function doLogin(){
  const username = (document.getElementById('username')||{value:''}).value.trim();
  const password = (document.getElementById('password')||{value:''}).value;
  const remember = document.getElementById('remember')?.checked;
  const msgEl = document.getElementById('msg');

  msgEl.textContent = '';
  if(!username || !password){ msgEl.textContent = 'Nhập đủ tên và mật khẩu'; return; }

  fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ username, password })
  })
  .then(r => r.json().then(j=>({ok:r.ok, body:j})))
  .then(({ok, body}) => {
    if(ok && body.ok){
      // lưu user (tạm) - bao gồm password để ensureAuth có thể recheck
      const user = { username, password, role: body.role || 'student' };
      if(remember) saveUserObj(user); else { removeUser(); saveUserObj(user); } // lưu session-like
      // vào thẳng index
      window.location.href = 'index.html';
    } else {
      msgEl.textContent = (body && body.error) ? body.error : 'Đăng nhập thất bại';
    }
  })
  .catch(err=>{
    console.error('login error', err);
    msgEl.textContent = 'Lỗi kết nối đến server';
  });
}

// đảm bảo người dùng đã login; nếu chưa => redirect login
function ensureAuth(){
  const user = getUserObj();
  if(!user || !user.username || !user.password){
    window.location.href = 'login.html';
    return;
  }
  // kiểm tra lại với server (best-effort)
  fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ username: user.username, password: user.password })
  })
  .then(r => r.json().then(j=>({ok:r.ok, body:j})))
  .then(({ok, body}) => {
    if(!ok || !body.ok){
      removeUser();
      window.location.href = 'login.html';
    } else {
      // đã xác thực, có thể cập nhật UI tên user
      const el = document.querySelector('#currentUser') || document.querySelector('.user-name');
      if(el) el.textContent = user.username;
    }
  })
  .catch(err=>{
    console.warn('Auth check failed', err);
    // nếu server unreachable: nếu có user lưu thì cho qua, nếu ko thì redirect
    if(!user) window.location.href = 'login.html';
  });
}

// helper lấy role
function getUserRole(){
  const u = getUserObj();
  return u ? u.role : null;
}

// logout
function logout(){
  removeUser();
  window.location.href = 'login.html';
}
