(function () {
  "use strict";

  var toggle = document.querySelector(".site-nav-toggle");
  var navigation = document.getElementById("navigation");
  var shell = document.querySelector(".site-nav-shell");

  if (!toggle || !navigation || !shell) {
    return;
  }

  var mobileQuery = window.matchMedia("(max-width: 720px)");
  var label = toggle.querySelector(".site-nav-toggle-label");

  function setExpanded(expanded, returnFocus) {
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    toggle.setAttribute(
      "aria-label",
      expanded ? "Close primary navigation" : "Open primary navigation"
    );
    if (label) {
      label.textContent = expanded ? "Close" : "Menu";
    }

    navigation.hidden = mobileQuery.matches ? !expanded : false;

    if (returnFocus) {
      toggle.focus();
    }
  }

  function synchronizeNavigation() {
    if (mobileQuery.matches) {
      toggle.hidden = false;
      setExpanded(false, false);
    } else {
      toggle.hidden = true;
      setExpanded(false, false);
      navigation.hidden = false;
    }
  }

  toggle.addEventListener("click", function () {
    var expanded = toggle.getAttribute("aria-expanded") === "true";
    setExpanded(!expanded, false);
  });

  navigation.addEventListener("click", function (event) {
    if (mobileQuery.matches && event.target.closest("a")) {
      setExpanded(false, false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (
      event.key === "Escape" &&
      mobileQuery.matches &&
      toggle.getAttribute("aria-expanded") === "true"
    ) {
      setExpanded(false, true);
    }
  });

  document.addEventListener("click", function (event) {
    if (
      mobileQuery.matches &&
      toggle.getAttribute("aria-expanded") === "true" &&
      !shell.contains(event.target)
    ) {
      setExpanded(false, false);
    }
  });

  if (typeof mobileQuery.addEventListener === "function") {
    mobileQuery.addEventListener("change", synchronizeNavigation);
  } else {
    mobileQuery.addListener(synchronizeNavigation);
  }

  synchronizeNavigation();
})();
