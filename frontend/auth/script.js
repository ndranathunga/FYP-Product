// For login form
const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const msgDiv = document.getElementById("login-msg");
    msgDiv.textContent = "Signing in...";
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (res.ok) {
        msgDiv.style.color = "#2574a9";
        msgDiv.textContent = "Success! Redirecting...";
        localStorage.setItem("access_token", data.access_token); // Store token
        setTimeout(() => {
          window.location.href = "/dashboard/"; // Redirect to dashboard
        }, 700);
      } else {
        msgDiv.style.color = "#b33c3c";
        msgDiv.textContent = data.detail || "Login failed";
      }
    } catch (err) {
      msgDiv.textContent = "Network error";
    }
  });
}

// For signup form
const signupForm = document.getElementById("signup-form");
if (signupForm) {
  signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("signup-email").value;
    const password = document.getElementById("signup-password").value;
    const org_name = document.getElementById("org_name").value;
    const msgDiv = document.getElementById("signup-msg");
    msgDiv.textContent = "Registering...";
    try {
      const res = await fetch("/api/v1/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, org_name }),
      });
      const data = await res.json();
      if (res.ok) {
        msgDiv.style.color = "#2574a9";
        msgDiv.textContent = "Signup successful! Redirecting...";
        localStorage.setItem("access_token", data.access_token); // Store token
        setTimeout(() => {
          window.location.href = "/dashboard/";
        }, 900);
      } else {
        msgDiv.style.color = "#b33c3c";
        msgDiv.textContent = data.detail || "Signup failed";
      }
    } catch (err) {
      msgDiv.textContent = "Network error";
    }
  });
}
