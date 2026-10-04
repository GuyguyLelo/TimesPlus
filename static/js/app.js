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
      context.fillStyle = "#007fff";
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

  document.querySelectorAll("canvas[data-chart]").forEach(drawBars);

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
    if (!pick || !photo || !name || !matricule || !role || !service) {
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
