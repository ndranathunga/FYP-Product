// auth.js - Script for Login and Signup forms

// Helper function to handle form submissions
async function handleAuthForm(formId, apiUrl, body) {
  const msgDiv = document.querySelector(`#${formId} + .auth-message`);
  const submitButton = document.querySelector(`#${formId} button[type="submit"]`);

  if (!msgDiv || !submitButton) return;

  // Provide visual feedback
  msgDiv.textContent = "Processing...";
  msgDiv.className = 'auth-message'; // Reset classes
  submitButton.disabled = true;

  try {
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (res.ok) {
      msgDiv.textContent = "Success! Redirecting...";
      msgDiv.classList.add('success');
      localStorage.setItem("access_token", data.access_token);
      setTimeout(() => {
        window.location.href = "/dashboard/"; // Redirect to dashboard
      }, 1000);
    } else {
      msgDiv.textContent = data.detail || "An error occurred. Please try again.";
      msgDiv.classList.add('error');
      submitButton.disabled = false;
    }
  } catch (err) {
    msgDiv.textContent = "Network error. Please check your connection.";
    msgDiv.classList.add('error');
    submitButton.disabled = false;
  }
}

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
  // For login form
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      handleAuthForm("login-form", "/api/v1/auth/login", { email, password });
    });
  }

  // For signup form
  const signupForm = document.getElementById("signup-form");
  if (signupForm) {
    signupForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      const org_name = document.getElementById("org_name").value;
      handleAuthForm("signup-form", "/api/v1/auth/signup", { email, password, org_name });
    });
  }
});