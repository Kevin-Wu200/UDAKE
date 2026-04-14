(function () {
  const APK_DOWNLOAD_URL =
    "http://172.20.10.2:6060/android_downloads/app-release.apk";
  const HOME_SCROLL_KEY = "udake_home_scroll_y";
  const HOME_SCROLL_MARK_KEY = "udake_restore_home_scroll";
  const FEATURE_PAGE_MAP = {
    interpolation: "interpolation.html",
    uncertainty: "uncertainty.html",
    sampling: "sampling.html",
    optimization: "optimization.html",
    realtime: "realtime.html",
    deepLearning: "deepLearning.html",
    anomaly: "anomaly.html",
    risk: "risk.html",
  };

  const modal = document.getElementById("comingSoonModal");
  const modalMessage = document.getElementById("modalMessage");
  const closeButton = document.getElementById("modalClose");

  function getComingSoonMessage(platform, language) {
    const platformNames = {
      "zh-CN": {
        windows: "Windows",
        macos: "macOS",
      },
      "en-US": {
        windows: "Windows",
        macos: "macOS",
      },
    };

    const templates = {
      "zh-CN": "{platform} 版本开发中，敬请期待。",
      "en-US": "{platform} version is under development. Stay tuned.",
    };

    const lang = language === "en-US" ? "en-US" : "zh-CN";
    const name =
      (platformNames[lang] && platformNames[lang][platform]) || platform;
    return templates[lang].replace("{platform}", name);
  }

  function openModal(platform) {
    if (!modal) {
      return;
    }

    const language = window.UDAKEI18N
      ? window.UDAKEI18N.getCurrentLanguage()
      : "zh-CN";
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

  function saveHomeScrollPosition() {
    try {
      sessionStorage.setItem(HOME_SCROLL_KEY, String(window.scrollY));
      sessionStorage.setItem(HOME_SCROLL_MARK_KEY, "1");
    } catch (error) {
      return;
    }
  }

  function restoreHomeScrollPosition() {
    try {
      const shouldRestore =
        sessionStorage.getItem(HOME_SCROLL_MARK_KEY) === "1";
      if (!shouldRestore) {
        return;
      }

      const raw = sessionStorage.getItem(HOME_SCROLL_KEY);
      const top = raw ? Number(raw) : NaN;
      if (Number.isFinite(top) && top >= 0) {
        window.requestAnimationFrame(function () {
          window.scrollTo({ top: top, behavior: "auto" });
        });
      }

      sessionStorage.removeItem(HOME_SCROLL_MARK_KEY);
    } catch (error) {
      return;
    }
  }

  function getFeatureFromHash() {
    const featureKey = window.location.hash.replace("#", "").trim();
    if (!featureKey) {
      return "";
    }
    return FEATURE_PAGE_MAP[featureKey] ? featureKey : "";
  }

  function isLandingHomePage() {
    const pathname = window.location.pathname;
    return /\/landing-page\/(?:index\.html)?$/.test(pathname);
  }

  function navigateToFeature(featureKey) {
    const pageFile = FEATURE_PAGE_MAP[featureKey];
    if (!pageFile) {
      return;
    }

    saveHomeScrollPosition();
    document.body.classList.add("page-transitioning");
    window.setTimeout(function () {
      window.location.assign("./pages/" + pageFile + "#" + featureKey);
    }, 120);
  }

  function bindFeatureCardActions() {
    document
      .querySelectorAll(".feature-card[data-feature]")
      .forEach(function (card) {
        const featureKey = card.getAttribute("data-feature");
        if (!featureKey || !FEATURE_PAGE_MAP[featureKey]) {
          return;
        }

        card.addEventListener("click", function () {
          navigateToFeature(featureKey);
        });

        card.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            navigateToFeature(featureKey);
          }
        });
      });
  }

  function routeByHashOnHome() {
    const featureKey = getFeatureFromHash();
    if (!featureKey) {
      return;
    }

    navigateToFeature(featureKey);
  }

  function bindBackHomeAction() {
    const backButton = document.getElementById("backHomeButton");
    if (!backButton) {
      return;
    }

    backButton.addEventListener("click", function () {
      document.body.classList.add("page-transitioning");
      window.setTimeout(function () {
        if (
          document.referrer &&
          document.referrer.indexOf("/landing-page/index.html") !== -1
        ) {
          window.history.back();
          return;
        }
        window.location.assign("../index.html#features");
      }, 120);
    });
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
      if (
        target instanceof HTMLElement &&
        target.dataset.closeModal === "true"
      ) {
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
        rootMargin: "0px 0px -8% 0px",
      },
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
    bindBackHomeAction();
    setupRevealAnimation();
    if (isLandingHomePage()) {
      bindFeatureCardActions();
      restoreHomeScrollPosition();
      routeByHashOnHome();
      window.addEventListener("hashchange", routeByHashOnHome);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
