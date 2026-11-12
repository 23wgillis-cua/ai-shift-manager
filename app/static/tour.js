/* First-run onboarding tour for AI Shift Manager.
   Shows once per browser (localStorage flag). Steps highlight the core loop:
   note -> AI parse -> cascade -> dashboard. */
(function () {
    var KEY = "asm_tour_done";
    try {
        if (localStorage.getItem(KEY)) { return; }
    } catch (e) { return; }

    var steps = [
        {
            title: "Welcome to AI Shift Manager",
            text: "You're looking at the Shift Notes page. Everything starts with a plain-English note about a scheduling change. This quick tour takes about 20 seconds.",
            target: null
        },
        {
            title: "1. Type what happened",
            text: "Type something like \"Mike has a funeral Wednesday and can't come to work\". The AI parses who, what, when, and urgency automatically.",
            target: "#note-form"
        },
        {
            title: "2. Pick coverage, or let the system do it",
            text: "Each open note shows an AI recommendation with ranked candidates. Assign manually, or start a coverage cascade: the best-fit candidate gets an email and SMS with Accept / Decline links, and each decline automatically advances to the next person.",
            target: ".note-item.open-note"
        },
        {
            title: "3. Track everything",
            text: "The Calendar shows coverage by day, the Dashboard has stats and heatmaps, and every action lands in the Audit Log. You're set.",
            target: ".navbar .nav-links"
        }
    ];

    var idx = 0;
    var overlay = document.createElement("div");
    overlay.id = "tour-overlay";
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(5,10,16,0.75);z-index:9998;";
    var card = document.createElement("div");
    card.id = "tour-card";
    card.style.cssText = [
        "position:fixed", "z-index:9999", "background:#152033",
        "border:1px solid #2a3a4a", "border-radius:12px", "padding:1.5rem",
        "max-width:380px", "width:90vw", "color:#e0e0e0",
        "font-family:inherit", "box-shadow:0 8px 32px rgba(0,0,0,0.5)"
    ].join(";");
    card.innerHTML = [
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">',
        '  <span style="color:#4a9eff;font-weight:700;font-size:0.8rem;">',
        '    <span id="tour-step"></span> / ' + steps.length + "</span>",
        '  <a href="#" id="tour-skip" style="color:#556;font-size:0.8rem;text-decoration:none;">Skip</a>',
        "</div>",
        '<h3 id="tour-title" style="margin:0 0 0.5rem 0;font-size:1.05rem;color:#fff;"></h3>',
        '<p id="tour-text" style="margin:0 0 1.25rem 0;font-size:0.9rem;color:#9aa8b8;line-height:1.5;"></p>',
        '<div style="display:flex;justify-content:space-between;align-items:center;">',
        '  <div id="tour-dots" style="display:flex;gap:0.35rem;"></div>',
        '  <button id="tour-next" style="background:#4a9eff;color:#fff;border:none;',
        '    border-radius:6px;padding:0.5rem 1.1rem;font-weight:600;cursor:pointer;">Next</button>',
        "</div>"
    ].join("");
    var highlight = document.createElement("div");
    highlight.id = "tour-highlight";
    highlight.style.cssText = [
        "position:fixed", "z-index:9997", "border:2px solid #4a9eff",
        "border-radius:8px", "pointer-events:none",
        "box-shadow:0 0 0 4000px rgba(5,10,16,0)"
    ].join(";");

    function endTour() {
        try { localStorage.setItem(KEY, "1"); } catch (e) {}
        [overlay, card, highlight].forEach(function (el) {
            if (el.parentNode) { el.parentNode.removeChild(el); }
        });
    }

    function showStep() {
        var s = steps[idx];
        card.querySelector("#tour-step").textContent = (idx + 1);
        card.querySelector("#tour-title").textContent = s.title;
        card.querySelector("#tour-text").textContent = s.text;
        var btn = card.querySelector("#tour-next");
        btn.textContent = (idx === steps.length - 1) ? "Done" : "Next";
        var dots = card.querySelector("#tour-dots");
        dots.innerHTML = "";
        steps.forEach(function (_, i) {
            var d = document.createElement("span");
            d.style.cssText = "width:8px;height:8px;border-radius:50%;background:" +
                (i === idx ? "#4a9eff" : "#2a3a4a") + ";display:inline-block;";
            dots.appendChild(d);
        });

        var target = s.target ? document.querySelector(s.target) : null;
        var vw = window.innerWidth, vh = window.innerHeight;
        if (target) {
            var rect = target.getBoundingClientRect();
            highlight.style.display = "block";
            highlight.style.top = (rect.top - 6) + "px";
            highlight.style.left = (rect.left - 6) + "px";
            highlight.style.width = (rect.width + 12) + "px";
            highlight.style.height = (rect.height + 12) + "px";
            var cardTop = rect.bottom + 14;
            if (cardTop + 260 > vh) { cardTop = Math.max(14, rect.top - 290); }
            var cardLeft = Math.min(Math.max(14, rect.left), vw - 400);
            card.style.top = cardTop + "px";
            card.style.left = cardLeft + "px";
        } else {
            highlight.style.display = "none";
            card.style.top = "50%";
            card.style.left = "50%";
            card.style.transform = "translate(-50%, -50%)";
        }
        if (target && (card.style.top === "50%")) { card.style.transform = "none"; }
        if (!target) { card.style.transform = "translate(-50%, -50%)"; }
    }

    document.body.appendChild(overlay);
    document.body.appendChild(highlight);
    document.body.appendChild(card);

    card.querySelector("#tour-next").addEventListener("click", function () {
        if (idx === steps.length - 1) { endTour(); return; }
        idx += 1;
        showStep();
    });
    card.querySelector("#tour-skip").addEventListener("click", function (e) {
        e.preventDefault();
        endTour();
    });
    overlay.addEventListener("click", endTour);

    // Fix transform when targeting elements (only center-step uses translate)
    var origShow = showStep;
    showStep = function () {
        origShow();
        var s = steps[idx];
        card.style.transform = s.target ? "none" : "translate(-50%, -50%)";
    };
    showStep();
})();
