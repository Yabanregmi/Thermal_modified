// Handler für das Ende des Konfigurationsmodus via Socket.io
const onKonfigEnde  = function(socket, io, {
  konfigAckTimeoutRef, // Getter für aktuellen Timeout (z.B. für Bestätigungen)
  setKonfigReady       // Setter für den globalen Konfigurations-Status
}) {
  let imKonfigModus = false; // Lokaler Status für den Konfigurationsmodus

  // Event-Handler für das "konfigEnde"-Event
  socket.on("konfigEnde", () => {
    // Prüfe, ob der Modus überhaupt aktiv ist
    if (!imKonfigModus) {
      socket.emit("info", "Konfigurationsmodus ist nicht aktiv.");
      return;
    }
    imKonfigModus = false; // Modus beenden
    io.emit("konfigModusEnde"); // Broadcast an alle Clients
    if (konfigAckTimeoutRef()) clearTimeout(konfigAckTimeoutRef()); // Timeout ggf. löschen
    setKonfigReady(false); // Globalen Status zurücksetzen
    socket.emit("info", "Konfigurationsmodus verlassen.");
  });
};

module.exports = { onKonfigEnde };
