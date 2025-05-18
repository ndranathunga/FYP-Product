window.addEventListener("DOMContentLoaded", function () {
  // If the dcc.Store exists, set it to the value in localStorage
  var jwtToken = localStorage.getItem("access_token");
  // Dash automatically exposes all window.dash_clientside functions
  if (window.dash_clientside) {
    window.dash_clientside.clientside = window.dash_clientside.clientside || {};
    window.dash_clientside.clientside.get_jwt_token = function () {
      return jwtToken || "";
    };
  }
  // For a one-time sync (to dcc.Store)
  var store = document.querySelector(
    '[data-dash-is-loading="false"][id="jwt-token-store"]'
  );
  if (store && jwtToken) {
    // Set value on first load (fallback)
    store.value = jwtToken;
  }
});
