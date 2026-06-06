document.documentElement.dataset.ready = "true";

(function() {
    const popupOverlay = document.getElementById('popupOverlay');
    const popupCloseBtn = document.getElementById('popupCloseBtn');
    
    // 页面加载完成后显示弹窗
    window.addEventListener('DOMContentLoaded', function() {
      // 延迟 500ms 显示，效果更自然
      setTimeout(() => {
        popupOverlay.classList.add('show');
      }, 500);
    });
    
    // 关闭按钮点击事件
    popupCloseBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      popupOverlay.classList.remove('show');
    });
    
    // 点击遮罩层不关闭（强制引导），如需点击遮罩关闭可取消下面注释
    /*
    popupOverlay.addEventListener('click', function(e) {
      if (e.target === popupOverlay) {
        popupOverlay.classList.remove('show');
      }
    });
    */
  })();
