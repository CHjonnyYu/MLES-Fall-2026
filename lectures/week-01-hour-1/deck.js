(() => {
  const deck = document.getElementById("deck");
  const slides = [...document.querySelectorAll(".slide")];
  const progress = document.getElementById("progressBar");
  const notesPanel = document.getElementById("notesPanel");
  const notesContent = document.getElementById("notesContent");
  const overviewPanel = document.getElementById("overviewPanel");
  const overviewGrid = document.getElementById("overviewGrid");
  let current = Math.max(
    0,
    Math.min(slides.length - 1, (parseInt(location.hash.slice(1), 10) || 1) - 1),
  );

  const titleOf = (slide) =>
    slide.querySelector("h1, h2")?.textContent.trim() || "Untitled";

  const cueAt = (minutes) => String(minutes).padStart(2, "0") + ":00";
  let elapsedMinutes = 0;

  slides.forEach((slide, index) => {
    const duration = Number(slide.dataset.duration) || 0;
    const startMinute = elapsedMinutes;
    elapsedMinutes += duration;
    slide.dataset.cue = cueAt(startMinute) + "-" + cueAt(elapsedMinutes);

    const footer = document.createElement("div");
    footer.className = "brand-footer";
    footer.innerHTML =
      '<div class="brand-left">' +
        '<span class="brand-chip">' +
          '<img class="ncku" src="assets/ncku.png" alt="NCKU" />' +
          '<span>NCKU · Engineering Science</span>' +
        '</span>' +
      '</div>' +
      '<div class="slide-meta">' +
        '<span class="time-pill">' + slide.dataset.cue + '</span>' +
        '<span class="slide-index">' +
          String(index + 1).padStart(2, "0") + " / " + slides.length +
        '</span>' +
      '</div>' +
      '<div class="brand-right">' +
        '<span class="brand-chip">' +
          '<img src="assets/laimm.png" alt="LAiMM Laboratory" />' +
        '</span>' +
      '</div>';
    slide.appendChild(footer);

    const card = document.createElement("button");
    card.type = "button";
    card.className = "overview-card";
    card.innerHTML =
      "<b>" +
      String(index + 1).padStart(2, "0") +
      " · " +
      slide.dataset.cue +
      "</b><span>" +
      titleOf(slide) +
      "</span>";
    card.addEventListener("click", () => {
      show(index);
      toggleOverview(false);
    });
    overviewGrid.appendChild(card);
  });

  function fitDeck() {
    const scale = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
    deck.style.setProperty("--deck-scale", scale.toFixed(4));
  }

  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("active", slideIndex === current);
      if (slideIndex !== current) slide.classList.remove("show-reveals");
    });

    const active = slides[current];
    const note = active.querySelector(".notes");
    notesContent.innerHTML = note ? note.innerHTML : "No speaker notes.";
    progress.style.width = ((current + 1) / slides.length) * 100 + "%";

    const hash = "#" + (current + 1);
    if (location.hash !== hash) history.replaceState(null, "", hash);

    document.title =
      String(current + 1).padStart(2, "0") +
      " · " +
      titleOf(active) +
      " | W01 H1";
    [...overviewGrid.children].forEach((card, cardIndex) =>
      card.classList.toggle("current", cardIndex === current),
    );
  }

  function move(delta) {
    show(current + delta);
  }

  function reveal() {
    slides[current].classList.toggle("show-reveals");
  }

  function toggleNotes(force) {
    notesPanel.classList.toggle(
      "open",
      force ?? !notesPanel.classList.contains("open"),
    );
  }

  function toggleOverview(force) {
    overviewPanel.classList.toggle(
      "open",
      force ?? !overviewPanel.classList.contains("open"),
    );
  }

  async function toggleFullscreen() {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen?.();
    } else {
      await document.exitFullscreen?.();
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();

    if (["arrowright", "pagedown", " "].includes(key)) {
      event.preventDefault();
      move(1);
    } else if (["arrowleft", "pageup"].includes(key)) {
      event.preventDefault();
      move(-1);
    } else if (key === "home") {
      show(0);
    } else if (key === "end") {
      show(slides.length - 1);
    } else if (key === "r" || key === "enter") {
      reveal();
    } else if (key === "n") {
      toggleNotes();
    } else if (key === "o") {
      toggleOverview();
    } else if (key === "escape") {
      toggleOverview(false);
      toggleNotes(false);
    } else if (key === "f") {
      toggleFullscreen();
    } else if (key === "p") {
      document.body.classList.toggle("presenter");
    }
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;

    if (action === "prev") move(-1);
    if (action === "next") move(1);
    if (action === "reveal") reveal();
    if (action === "notes") toggleNotes();
    if (action === "overview") toggleOverview();
    if (action === "fullscreen") toggleFullscreen();
  });

  let touchStart = 0;
  document.addEventListener(
    "touchstart",
    (event) => {
      touchStart = event.changedTouches[0].clientX;
    },
    { passive: true },
  );
  document.addEventListener(
    "touchend",
    (event) => {
      const distance = event.changedTouches[0].clientX - touchStart;
      if (Math.abs(distance) > 70) move(distance < 0 ? 1 : -1);
    },
    { passive: true },
  );

  window.addEventListener("resize", fitDeck);
  window.addEventListener("hashchange", () => {
    const requested = parseInt(location.hash.slice(1), 10);
    if (Number.isFinite(requested) && requested - 1 !== current) {
      show(requested - 1);
    }
  });

  const divide = (numerator, denominator) =>
    denominator === 0 ? null : numerator / denominator;
  const percentage = (value) =>
    value === null || !Number.isFinite(value)
      ? "undefined"
      : (value * 100).toFixed(1) + "%";

  function initThresholdDemo() {
    const slider = document.getElementById("thresholdSlider");
    const ruler = document.getElementById("scoreRuler");
    const marker = document.getElementById("thresholdMarker");
    if (!slider || !ruler || !marker) return;

    const cases = [
      [0.95, 1], [0.90, 1], [0.85, 0], [0.82, 1], [0.76, 1],
      [0.72, 0], [0.69, 1], [0.61, 0], [0.57, 1], [0.54, 0],
      [0.49, 1], [0.44, 0], [0.39, 1], [0.34, 0], [0.30, 0],
      [0.26, 1], [0.22, 0], [0.18, 0], [0.14, 0], [0.10, 0],
    ];

    const dots = cases.map((item, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className =
        "case-dot " + (item[1] === 1 ? "actual-damage" : "actual-healthy");
      dot.style.left = item[0] * 100 + "%";
      dot.setAttribute(
        "aria-label",
        "Case " +
          (index + 1) +
          ", score " +
          item[0].toFixed(2) +
          ", actual " +
          (item[1] === 1 ? "damage" : "healthy"),
      );
      dot.title =
        "Case " +
        (index + 1) +
        " · score " +
        item[0].toFixed(2) +
        " · actual " +
        (item[1] === 1 ? "damage" : "healthy");
      ruler.appendChild(dot);
      return dot;
    });

    const explanations = {
      tp: [
        "True Positive (TP)",
        "Actual damage and predicted damage: the defect is correctly caught.",
      ],
      fn: [
        "False Negative (FN)",
        "Actual damage but predicted healthy: a missed defect and potential safety risk. In hypothesis-testing language this parallels a Type II error.",
      ],
      fp: [
        "False Positive (FP)",
        "Actual healthy but predicted damage: a false alarm and unnecessary inspection. In hypothesis-testing language this parallels a Type I error.",
      ],
      tn: [
        "True Negative (TN)",
        "Actual healthy and predicted healthy: the asset is correctly cleared.",
      ],
    };

    document.querySelectorAll(".matrix-cell[data-kind]").forEach((cell) => {
      cell.addEventListener("click", () => {
        document
          .querySelectorAll(".matrix-cell[data-kind]")
          .forEach((item) => item.classList.remove("active"));
        cell.classList.add("active");
        const text = explanations[cell.dataset.kind];
        document.getElementById("matrixExplain").innerHTML =
          "<b>" + text[0] + "</b><span>" + text[1] + "</span>";
      });
    });

    function update() {
      const threshold = Number(slider.value) / 100;
      const counts = { tp: 0, fn: 0, fp: 0, tn: 0 };
      document.getElementById("thresholdValue").value = threshold.toFixed(2);
      marker.style.left = threshold * 100 + "%";

      cases.forEach((item, index) => {
        const predicted = item[0] >= threshold ? 1 : 0;
        const actual = item[1];
        const kind =
          actual === 1
            ? predicted === 1
              ? "tp"
              : "fn"
            : predicted === 1
              ? "fp"
              : "tn";
        counts[kind] += 1;
        dots[index].classList.toggle("predicted-damage", predicted === 1);
        dots[index].classList.toggle("predicted-healthy", predicted === 0);
      });

      document.getElementById("tpCount").textContent = counts.tp;
      document.getElementById("fnCount").textContent = counts.fn;
      document.getElementById("fpCount").textContent = counts.fp;
      document.getElementById("tnCount").textContent = counts.tn;
      document.getElementById("metricRecall").textContent = percentage(
        divide(counts.tp, counts.tp + counts.fn),
      );
      document.getElementById("metricPrecision").textContent = percentage(
        divide(counts.tp, counts.tp + counts.fp),
      );
      document.getElementById("metricSpecificity").textContent = percentage(
        divide(counts.tn, counts.tn + counts.fp),
      );
      document.getElementById("metricAccuracy").textContent = percentage(
        divide(counts.tp + counts.tn, cases.length),
      );
      document.getElementById("metricF1").textContent = percentage(
        divide(2 * counts.tp, 2 * counts.tp + counts.fp + counts.fn),
      );
    }

    slider.addEventListener("input", update);
    update();
  }

  function initMetricLab() {
    const lab = document.getElementById("metricLab");
    if (!lab) return;

    const presets = {
      balanced: {
        tp: 45,
        fn: 5,
        fp: 10,
        tn: 40,
        narrative:
          "Balanced test: 85% accuracy, but 1 in 10 actual damaged cases is still missed.",
      },
      rare: {
        tp: 0,
        fn: 8,
        fp: 0,
        tn: 92,
        narrative:
          "Accuracy is 92%, yet recall is 0%: the model clears every damaged case. This is the majority-class trap.",
      },
      safety: {
        tp: 8,
        fn: 0,
        fp: 22,
        tn: 70,
        narrative:
          "Safety-first threshold: recall reaches 100%, but 22 false alarms reduce precision and increase inspection cost.",
      },
    };

    function update(name) {
      const c = presets[name];
      const total = c.tp + c.fn + c.fp + c.tn;
      const values = {
        Recall: divide(c.tp, c.tp + c.fn),
        Precision: divide(c.tp, c.tp + c.fp),
        Specificity: divide(c.tn, c.tn + c.fp),
        Npv: divide(c.tn, c.tn + c.fn),
        Accuracy: divide(c.tp + c.tn, total),
        F1: divide(2 * c.tp, 2 * c.tp + c.fp + c.fn),
        Fpr: divide(c.fp, c.fp + c.tn),
        Fnr: divide(c.fn, c.fn + c.tp),
      };

      document.getElementById("labTp").textContent = c.tp;
      document.getElementById("labFn").textContent = c.fn;
      document.getElementById("labFp").textContent = c.fp;
      document.getElementById("labTn").textContent = c.tn;
      document.getElementById("labNarrative").textContent = c.narrative;
      Object.keys(values).forEach((key) => {
        document.getElementById("lab" + key).textContent = percentage(values[key]);
      });
      document.querySelectorAll("[data-preset]").forEach((button) => {
        button.classList.toggle("active", button.dataset.preset === name);
      });
    }

    document.querySelectorAll("[data-preset]").forEach((button) => {
      button.addEventListener("click", () => update(button.dataset.preset));
    });
    update("rare");
  }

  fitDeck();
  show(current);

  // Interactive labs are enhancements, not prerequisites for displaying the deck.
  // Keep the core presentation usable even if a browser blocks one lab feature.
  try {
    initThresholdDemo();
  } catch (error) {
    console.error("Threshold demo could not be initialized:", error);
  }
  try {
    initMetricLab();
  } catch (error) {
    console.error("Metric lab could not be initialized:", error);
  }
})();
