(function () {
  const APK_DOWNLOAD_URL = "http://172.20.10.2:6060/android_downloads/app-release.apk";
  const modal = document.getElementById("comingSoonModal");
  const modalMessage = document.getElementById("modalMessage");
  const closeButton = document.getElementById("modalClose");

  function getComingSoonMessage(platform, language) {
    const platformNames = {
      "zh-CN": {
        windows: "Windows",
        macos: "macOS"
      },
      "en-US": {
        windows: "Windows",
        macos: "macOS"
      }
    };

    const templates = {
      "zh-CN": "{platform} 版本开发中，敬请期待。",
      "en-US": "{platform} version is under development. Stay tuned."
    };

    const lang = language === "en-US" ? "en-US" : "zh-CN";
    const name = (platformNames[lang] && platformNames[lang][platform]) || platform;
    return templates[lang].replace("{platform}", name);
  }

  function openModal(platform) {
    if (!modal) {
      return;
    }

    const language = window.UDAKEI18N ? window.UDAKEI18N.getCurrentLanguage() : "zh-CN";
    if (modalMessage && platform) {
      modalMessage.textContent = getComingSoonMessage(platform, language);
    }

    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    if (!modal) {
      return;
    }

    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    if (window.UDAKEI18N && modalMessage) {
      window.UDAKEI18N.applyLanguage(window.UDAKEI18N.getCurrentLanguage());
    }
  }

  function bindDownloadActions() {
    const androidButton = document.getElementById("androidDownload");
    if (androidButton) {
      androidButton.setAttribute("href", APK_DOWNLOAD_URL);
    }

    document.querySelectorAll(".coming-soon").forEach(function (button) {
      button.addEventListener("click", function () {
        const platform = button.getAttribute("data-platform") || "platform";
        openModal(platform);
      });
    });
  }

  function bindModalActions() {
    if (!modal) {
      return;
    }

    modal.addEventListener("click", function (event) {
      const target = event.target;
      if (target instanceof HTMLElement && target.dataset.closeModal === "true") {
        closeModal();
      }
    });

    if (closeButton) {
      closeButton.addEventListener("click", closeModal);
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeModal();
      }
    });
  }

  function bindLanguageAction() {
    const languageButton = document.getElementById("languageToggle");
    if (!languageButton || !window.UDAKEI18N) {
      return;
    }

    languageButton.addEventListener("click", function () {
      window.UDAKEI18N.toggleLanguage();
    });
  }

  function bindHeroAction() {
    const ctaButton = document.getElementById("heroCta");
    const target = document.getElementById("downloads");
    if (!ctaButton || !target) {
      return;
    }

    ctaButton.addEventListener("click", function () {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function setupRevealAnimation() {
    const items = document.querySelectorAll(".reveal");
    if (!items.length) {
      return;
    }

    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.12,
        rootMargin: "0px 0px -8% 0px"
      }
    );

    items.forEach(function (item) {
      observer.observe(item);
    });
  }

  function bootstrap() {
    if (window.UDAKEI18N) {
      window.UDAKEI18N.init();
    }

    bindLanguageAction();
    bindHeroAction();
    bindDownloadActions();
    bindModalActions();
    setupRevealAnimation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
