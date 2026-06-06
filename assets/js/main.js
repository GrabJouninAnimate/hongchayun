document.documentElement.dataset.ready = "true";

(function () {
  const popupOverlay = document.getElementById("popupOverlay");
  const popupCloseBtn = document.getElementById("popupCloseBtn");

  if (!popupOverlay || !popupCloseBtn) {
    return;
  }

  window.addEventListener("DOMContentLoaded", function () {
    window.setTimeout(function () {
      popupOverlay.classList.add("show");
    }, 500);
  });

  popupCloseBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    popupOverlay.classList.remove("show");
  });
})();
