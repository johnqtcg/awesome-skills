document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname.replace(/\/+$/, "");
  const isLandingPage =
    path.endsWith("/awesome-skills") ||
    path.endsWith("/awesome-skills/index-zh");

  if (isLandingPage) {
    document.body.classList.add("landing-page");
  }
});
