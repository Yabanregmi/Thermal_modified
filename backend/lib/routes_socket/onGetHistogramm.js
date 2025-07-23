/**
 * Registriert den Handler für das Event "getTemperaturHistogramm" auf dem Socket.
 * Wenn das Event ausgelöst wird, liest die Funktion das Temperatur-Histogramm aus der Datenbank
 * und sendet es an den Client zurück.
 *
 * @param {Socket} socket - Die Socket.io-Verbindung zum Client
 * @param {Object} database - Die (async/await-fähige) Datenbankinstanz
 */
const onGetHistogramm = function (socket, database) {
  // Registriere Listener für das Event "getTemperaturHistogramm"
  socket.on("getTemperaturHistogramm", async () => {
    try {
      // Hole das Histogramm aus der Datenbank (z.B. als Array von "Bins")
      const bins = await getHistogramm(database);
      // Sende das Ergebnis an den Client zurück
      socket.emit("temperaturHistogramm", bins);
    } catch (err) {
      // Bei Fehler: Sende eine Fehlermeldung an den Client
      socket.emit("temperaturHistogrammError", "Fehler beim Lesen der Datenbank");
    }
  });
};

module.exports = { onGetHistogramm };
