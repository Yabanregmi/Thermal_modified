const crc = require('crc');

// Hilfsfunktion: Berechnet die CRC32-Prüfsumme aus Wert und Zeit
function getCRC(wert, zeit) {
  return crc.crc32(`${wert}:${zeit}`).toString();
}

// Handler für Live-Temperaturdaten via Socket.io
const onLiveTemperatur = function(socket, io, getLetzteLiveTemperatur, setLetzteLiveTemperatur) {
  // Nach Verbindungsaufbau: Sende letzte bekannte Temperatur an den Client (falls vorhanden)
  const last = getLetzteLiveTemperatur();
  if (last) {
    socket.emit('temperatur', last);
  }

  // Event-Handler für neue Live-Temperaturdaten von der Python-App
  socket.on("liveTemperatur", (data) => {
    // Prüfe, ob alle Felder vorhanden sind
    if (!data || typeof data.wert === 'undefined' || typeof data.zeit === 'undefined' || typeof data.crc === 'undefined') {
      console.log("Ungültige Datenstruktur von Python-Client!", data);
      socket.emit('temperaturError', 'Ungültige Datenstruktur!');
      return;
    } else {
      // Prüfe CRC32-Prüfsumme
      const crcCheck = getCRC(data.wert, data.zeit);
      if (crcCheck === data.crc.toString()) {
        const msg = {
          id: Date.now(),
          wert: data.wert,
          zeit: data.zeit
        };
        setLetzteLiveTemperatur(msg);   // Temperatur speichern
        io.emit('temperatur', msg);     // An alle Clients senden
      } else {
        console.log("Ungültige CRC32-Prüfsumme von Python-Client!", data);
        socket.emit('temperaturError', 'Ungültige CRC32-Prüfsumme!');
      }
    }
  });
};

module.exports = { onLiveTemperatur };
