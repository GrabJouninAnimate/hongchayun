document.documentElement.dataset.ready = "true";

(function () {
  const popupOverlay = document.getElementById("popupOverlay");
  const popupCloseBtn = document.getElementById("popupCloseBtn");

  if (!popupOverlay || !popupCloseBtn) {
    return;
  }

  function showPopup() {
    window.setTimeout(function () {
      popupOverlay.classList.add("show");
    }, 500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showPopup, { once: true });
  } else {
    showPopup();
  }

  popupCloseBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    popupOverlay.classList.remove("show");
  });
})();
