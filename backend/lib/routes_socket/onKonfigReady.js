'use strict';

// Handler für das "konfigReady"-Event via Socket.io
const onKonfigReady = function(socket, io, {
  konfigAckTimeoutRef, // Getter für aktuellen Timeout
  setKonfigReady       // Setter für globalen Konfigurations-Status
}) {
  // Registriere Event-Handler für "konfigReady"
  socket.on("konfigReady", () => {
    setKonfigReady(true); // Setze globalen Status auf "bereit"

    // Lösche ggf. bestehenden Timeout
    const timeout = konfigAckTimeoutRef();
    if (timeout) clearTimeout(timeout);

    io.emit("info", "System bereit zur Konfiguration."); // Broadcast an alle Clients
    console.log("info", "System bereit zur Konfiguration.");
  });
};

module.exports = { onKonfigReady };
