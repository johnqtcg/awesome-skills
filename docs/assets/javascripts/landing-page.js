document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname.replace(/\/+$/, "");
  const isLandingPage =
    path.endsWith("/awesome-skills") ||
    path.endsWith("/awesome-skills/index-zh");

  if (isLandingPage) {
    document.body.classList.add("landing-page");
    initCountUp();
  }
});

function initCountUp() {
  const els = document.querySelectorAll("[data-count-to]");
  if (!els.length) return;

  const run = (el) => {
    const target = parseInt(el.getAttribute("data-count-to"), 10);
    const suffix = el.getAttribute("data-suffix") || "";
    const duration = 900;
    const start = performance.now();

    const step = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * target);
      el.textContent = current + suffix;
      if (progress < 1) requestAnimationFrame(step);
    };

    requestAnimationFrame(step);
  };

  // Use IntersectionObserver so counters fire when hero enters view
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            run(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 }
    );
    els.forEach((el) => observer.observe(el));
  } else {
    els.forEach(run);
  }
}