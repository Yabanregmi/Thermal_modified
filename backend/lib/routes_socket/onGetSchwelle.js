// Handler für das Schwellenwert-Event via Socket.io
const onGetSchwelle = function(socket, io, getSchwelle, setSchwelle) {
  // Aktuellen Schwellenwert anfragenden Client senden
  socket.on("getSchwelle", () => {
    socket.emit("schwelle", getSchwelle());
  });

  // Schwellenwert setzen, validieren und an alle Clients broadcasten
  socket.on("setSchwelle", (wert) => {
    const parsed = parseFloat(wert);
    if (isNaN(parsed) || parsed < 0 || parsed > 200) {
      socket.emit("schwelleError", "Ungültiger Wert");
      return;
    }
    setSchwelle(parsed);
    io.emit("schwelle", parsed); // Broadcast an alle Clients
    socket.emit("info", "Neue Schwelle gesetzt: " + parsed + "°C");
    console.log("Neue Schwelle gesetzt:", parsed);
  });
};

module.exports = { onGetSchwelle };
