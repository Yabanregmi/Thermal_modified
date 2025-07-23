// Handler für das Starten des Konfigurationsmodus via Socket.io
const onKonfigStart  = function(socket, io, {
  konfigAckTimeoutRef,    // Getter für aktuellen Timeout (Bestätigung Python-App)
  setKonfigAckTimeout,    // Setter für Timeout
  konfigReadyRef,         // Getter für globalen Konfigurations-Status
  setKonfigReady          // Setter für globalen Konfigurations-Status
}) {
  let imKonfigModus = false; // Lokaler Status für diesen Socket

  socket.on("konfigStart", () => {
    console.log("konfigStart");
    if (imKonfigModus) {
      socket.emit("info", "Konfigurationsmodus ist bereits aktiv.");
      return;
    }
    imKonfigModus = true;
    setKonfigReady(false); // Setze globalen Status auf "nicht bereit"
    
    io.emit("konfigModusStart"); // Broadcast an alle Clients (inkl. Python-App)

    // Vorherigen Timeout ggf. löschen
    if (konfigAckTimeoutRef()) clearTimeout(konfigAckTimeoutRef());

    // Timeout für die Bestätigung der Python-App starten (5 Sekunden)
    const timeout = setTimeout(() => {
      if (!konfigReadyRef()) {
        socket.emit("info", "Python app - No Response. Config not allowed.");
        imKonfigModus = false;
      }
    }, 5000);
    setKonfigAckTimeout(timeout); // Timeout speichern
  });
};

module.exports = { onKonfigStart };
