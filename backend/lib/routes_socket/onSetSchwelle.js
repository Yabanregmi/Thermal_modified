// Handler für das Setzen des Schwellenwerts via Socket.io
const onSetSchwelle = function(socket, io, setSchwelle) {
  // Registriere Event-Handler für "setSchwelle"
  socket.on("setSchwelle", (wert) => {
    const parsed = parseFloat(wert); // Wert in Zahl umwandeln
    // Prüfe, ob der Wert gültig ist
    if (isNaN(parsed) || parsed < 0 || parsed > 200) {
      socket.emit("schwelleError", "Ungültiger Wert");
      return;
    }
    setSchwelle(parsed);              // Schwellenwert speichern/updaten
    io.emit("schwelle", parsed);      // Broadcast an alle Clients
    socket.emit("info", "Neue Schwelle gesetzt: " + parsed + "°C");
    console.log("Neue Schwelle gesetzt:", parsed);
  });
};

module.exports = { onSetSchwelle };
