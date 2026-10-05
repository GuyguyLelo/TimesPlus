(function () {
  "use strict";

  function readSeries(id) {
    var node = document.getElementById(id);
    if (!node) {
      return [];
    }
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return [];
    }
  }

  var piePalette = [
    "#007fff", "#ce1021", "#c8960a", "#0b4f8a", "#146c43",
    "#7a5b00", "#5c6b76", "#9b1c2c", "#1f4e79", "#8a6d00",
    "#3d4a5c", "#f7d618"
  ];

  function drawPie(canvas) {
    var series = readSeries(canvas.getAttribute("data-chart")).filter(function (item) {
      return Number(item.value) > 0;
    });
    var context = canvas.getContext("2d");
    var width = canvas.clientWidth || 320;
    var height = canvas.clientHeight || 240;
    var ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    if (!series.length) {
      context.fillStyle = "#5c6b76";
      context.font = "14px Segoe UI, sans-serif";
      context.fillText("Aucune donnée", 8, 24);
      return;
    }
    var total = series.reduce(function (sum, item) {
      return sum + (Number(item.value) || 0);
    }, 0) || 1;
    var legendWidth = Math.min(210, Math.max(120, width * 0.4));
    var pieArea = Math.max(80, width - legendWidth);
    var radius = Math.max(28, Math.min(pieArea, height) / 2 - 14);
    var centerX = pieArea / 2;
    var centerY = height / 2;
    var angle = -Math.PI / 2;
    series.forEach(function (item, index) {
      var slice = ((Number(item.value) || 0) / total) * Math.PI * 2;
      context.beginPath();
      context.moveTo(centerX, centerY);
      context.arc(centerX, centerY, radius, angle, angle + slice);
      context.closePath();
      context.fillStyle = piePalette[index % piePalette.length];
      context.fill();
      angle += slice;
    });
    context.font = "12px Segoe UI, sans-serif";
    var row = 18;
    var legendTop = Math.max(8, (height - series.length * row) / 2);
    series.forEach(function (item, index) {
      var y = legendTop + index * row;
      var part = Math.round(((Number(item.value) || 0) / total) * 100);
      var text = String(item.label || "") + " · " + part + " %";
      context.fillStyle = piePalette[index % piePalette.length];
      context.fillRect(pieArea, y, 10, 10);
      context.fillStyle = "#1f2933";
      while (text.length > 1 && context.measureText(text).width > legendWidth - 22) {
        text = text.slice(0, -2) + "…";
      }
      context.fillText(text, pieArea + 16, y + 10);
    });
  }

  function drawBars(canvas) {
    var series = readSeries(canvas.getAttribute("data-chart"));
    var context = canvas.getContext("2d");
    var width = canvas.clientWidth || 320;
    var height = canvas.height;
    var ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    if (!series.length) {
      context.fillStyle = "#5c6b76";
      context.font = "14px Segoe UI, sans-serif";
      context.fillText("Aucune donnée", 8, 24);
      return;
    }
    var max = series.reduce(function (highest, item) {
      return Math.max(highest, Number(item.value) || 0);
    }, 0) || 1;
    var gap = 8;
    var barWidth = Math.max(12, (width - gap * (series.length + 1)) / series.length);
    series.forEach(function (item, index) {
      var value = Number(item.value) || 0;
      var barHeight = Math.max(2, (value / max) * (height - 36));
      var x = gap + index * (barWidth + gap);
      var y = height - 22 - barHeight;
      var tones = { paye: "#007fff", cours: "#c8960a", avenir: "#c5d0dc" };
      context.fillStyle = tones[item.tone] || "#007fff";
      context.fillRect(x, y, barWidth, barHeight);
      context.fillStyle = "#1f2933";
      context.font = "11px Segoe UI, sans-serif";
      context.save();
      context.translate(x, height - 4);
      context.rotate(-0.5);
      context.fillText(String(item.label || ""), 0, 0);
      context.restore();
    });
  }

  document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
    if (canvas.getAttribute("data-shape") === "cercle") {
      drawPie(canvas);
    } else {
      drawBars(canvas);
    }
  });

  document.querySelectorAll("table.table").forEach(function (table) {
    var heads = Array.prototype.map.call(table.querySelectorAll("thead th"), function (cell) {
      return (cell.textContent || "").replace(/\s+/g, " ").trim();
    });
    table.querySelectorAll("tbody tr").forEach(function (row) {
      Array.prototype.forEach.call(row.children, function (cell, index) {
        if (cell.tagName !== "TD" || cell.hasAttribute("colspan")) {
          return;
        }
        if (heads[index]) {
          cell.setAttribute("data-label", heads[index]);
        }
      });
    });
  });
  document.documentElement.classList.add("lists-ready");

  document.querySelectorAll(".nav-branch").forEach(function (branch) {
    var parent = branch.querySelector(".nav-parent");
    if (!parent) {
      return;
    }
    parent.addEventListener("click", function () {
      var open = branch.classList.toggle("is-open");
      parent.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  var form = document.getElementById("declaration-form");
  if (!form) {
    return;
  }
  var timer = null;

  function preview() {
    var date = document.getElementById("id_date_travail");
    var start = document.getElementById("id_heure_debut");
    var end = document.getElementById("id_heure_fin");
    var agent = document.getElementById("id_agent");
    if (!date || !start || !end || !agent || !date.value || !start.value || !end.value || !agent.value) {
      return;
    }
    var params = new URLSearchParams({
      date: date.value,
      heure_debut: start.value,
      heure_fin: end.value,
      agent: agent.value,
      exclude: form.getAttribute("data-exclude") || ""
    });
    fetch(form.getAttribute("data-preview-url") + "?" + params.toString(), {
      headers: { "X-Requested-With": "fetch" }
    }).then(function (response) {
      return response.json();
    }).then(function (data) {
      document.getElementById("preview-duree").textContent = data.ok ? data.duree : "—";
      document.getElementById("preview-type").textContent = data.ok ? data.type : "—";
      document.getElementById("preview-message").textContent = data.ok
        ? "Règle : " + data.regle + " — coefficient " + data.coefficient
        : data.message;
    }).catch(function () {
      document.getElementById("preview-message").textContent = "L'aperçu n'a pas pu être calculé. L'enregistrement reste possible.";
    });
  }

  var mois = document.getElementById("id_mois");
  var dateField = document.getElementById("id_date_travail");

  function monthBounds(value) {
    var parts = value.split("-");
    var year = Number(parts[0]);
    var month = Number(parts[1]);
    var last = new Date(year, month, 0).getDate();
    var mm = String(month).padStart(2, "0");
    var dd = String(last).padStart(2, "0");
    return { min: year + "-" + mm + "-01", max: year + "-" + mm + "-" + dd };
  }

  function applyMonth() {
    if (!mois || !dateField || !mois.value) {
      return;
    }
    var bounds = monthBounds(mois.value);
    dateField.min = bounds.min;
    dateField.max = bounds.max;
    if (!dateField.value || dateField.value < bounds.min || dateField.value > bounds.max) {
      var today = dateField.getAttribute("data-today") || "";
      dateField.value = today >= bounds.min && today <= bounds.max ? today : bounds.min;
      dateField.dispatchEvent(new Event("change"));
    }
  }

  if (mois) {
    mois.addEventListener("change", applyMonth);
  }

  var query = document.getElementById("agent-query");
  var results = document.getElementById("agent-results");
  var agentField = document.getElementById("id_agent");
  var searchTimer = null;
  var selectedLabel = query ? query.value : "";

  function hideResults() {
    if (!results) {
      return;
    }
    results.hidden = true;
    results.innerHTML = "";
  }

  function showAgent(item) {
    var pick = document.getElementById("agent-pick");
    var photo = document.getElementById("agent-pick-photo");
    var name = document.getElementById("agent-pick-name");
    var matricule = document.getElementById("agent-pick-matricule");
    var role = document.getElementById("agent-pick-role");
    var service = document.getElementById("agent-pick-service");
    var taux = document.getElementById("agent-pick-taux");
    if (!pick || !photo || !name || !matricule || !role || !service || !taux) {
      return;
    }
    photo.textContent = "";
    if (item.photo && item.photo.charAt(0) === "/") {
      var image = document.createElement("img");
      image.src = item.photo;
      image.alt = "Photo de " + (item.nom || "");
      photo.appendChild(image);
    } else {
      var letters = document.createElement("span");
      letters.textContent = item.initiales || "AG";
      photo.appendChild(letters);
    }
    name.textContent = item.nom || "";
    matricule.textContent = item.matricule || "";
    var parts = [];
    if (item.grade) {
      parts.push(item.grade);
    }
    if (item.fonction) {
      parts.push(item.fonction);
    }
    role.textContent = parts.join(" · ");
    service.textContent = item.service || "";
    taux.textContent = "Taux horaire : " + (item.taux || "Aucun barème");
    pick.hidden = false;
  }

  function hideAgent() {
    var pick = document.getElementById("agent-pick");
    if (pick) {
      pick.hidden = true;
    }
  }

  if (query && results && agentField) {
    query.addEventListener("input", function () {
      if (query.value !== selectedLabel) {
        agentField.value = "";
        hideAgent();
      }
      window.clearTimeout(searchTimer);
      var text = query.value.trim();
      if (!text) {
        hideResults();
        return;
      }
      searchTimer = window.setTimeout(function () {
        fetch(form.getAttribute("data-agent-url") + "?q=" + encodeURIComponent(text), {
          headers: { "X-Requested-With": "fetch" }
        }).then(function (response) {
          return response.json();
        }).then(function (data) {
          results.innerHTML = "";
          var items = data.results || [];
          if (!items.length) {
            var empty = document.createElement("li");
            empty.className = "agent-empty";
            empty.textContent = "Aucun agent.";
            results.appendChild(empty);
            results.hidden = false;
            return;
          }
          items.forEach(function (item) {
            var li = document.createElement("li");
            var button = document.createElement("button");
            var chip = document.createElement("span");
            var name = document.createElement("strong");
            var service = document.createElement("span");
            button.type = "button";
            chip.className = "code-chip";
            chip.textContent = item.matricule;
            name.textContent = item.nom;
            service.textContent = item.service;
            button.appendChild(chip);
            button.appendChild(name);
            button.appendChild(service);
            button.addEventListener("click", function () {
              agentField.value = String(item.id);
              selectedLabel = item.matricule + " — " + item.nom;
              query.value = selectedLabel;
              showAgent(item);
              hideResults();
              agentField.dispatchEvent(new Event("change"));
            });
            li.appendChild(button);
            results.appendChild(li);
          });
          results.hidden = false;
        }).catch(function () {
          hideResults();
        });
      }, 200);
    });
  }

  ["id_date_travail", "id_heure_debut", "id_heure_fin", "id_agent"].forEach(function (id) {
    var field = document.getElementById(id);
    if (field) {
      field.addEventListener("change", function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(preview, 200);
      });
    }
  });
})();
