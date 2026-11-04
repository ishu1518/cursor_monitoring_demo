(function () {
  function text(id, value) {
    var node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function formatBytes(size) {
    var amount = Number(size);
    var units = ["B", "KB", "MB", "GB", "TB"];
    var unit = units[0];
    var index;
    for (index = 0; index < units.length; index += 1) {
      unit = units[index];
      if (amount < 1024 || unit === "TB") {
        break;
      }
      amount /= 1024;
    }
    if (unit === "B") {
      return Math.round(amount) + " B";
    }
    return amount.toFixed(1) + " " + unit;
  }

  function renderCards(data) {
    var ports;
    if (!data.collected) {
      text("metric-cpu", data.detail || "Not collected");
      text("metric-memory", data.detail || "Not collected");
      text("metric-network", data.detail || "Not collected");
      text("metric-ports", data.detail || "Not collected");
      return;
    }
    text("metric-cpu", Number(data.cpu_percent).toFixed(0) + "%");
    text(
      "metric-memory",
      formatBytes(data.memory_used) + " / " + formatBytes(data.memory_total)
    );
    text(
      "metric-network",
      formatBytes(data.bytes_recv) + " in · " + formatBytes(data.bytes_sent) + " out"
    );
    ports = Array.isArray(data.ports) && data.ports.length ? data.ports.join(", ") : "None";
    text("metric-ports", ports);
  }

  function summary(data) {
    if (!data.collected) {
      return data.detail || "Not collected";
    }
    return (
      Number(data.cpu_percent).toFixed(0) +
      "% CPU · " +
      formatBytes(data.memory_used) +
      " / " +
      formatBytes(data.memory_total)
    );
  }

  function watch(url, apply) {
    function refresh() {
      fetch(url, { headers: { Accept: "application/json" } })
        .then(function (response) {
          if (!response.ok) {
            return null;
          }
          return response.json();
        })
        .then(function (data) {
          if (data) {
            apply(data);
          }
        })
        .catch(function () {
          return null;
        });
    }
    refresh();
    window.setInterval(refresh, 5000);
  }

  var cards = document.querySelector(".cards[data-metrics-url]");
  if (cards) {
    watch(cards.getAttribute("data-metrics-url"), renderCards);
  }

  var rows = document.querySelectorAll("[data-server-metrics]");
  Array.prototype.forEach.call(rows, function (row) {
    watch(row.getAttribute("data-server-metrics"), function (data) {
      var status = row.querySelector(".server-status");
      if (status) {
        status.textContent = summary(data);
      }
    });
  });
})();
