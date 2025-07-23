'use strict';
const crypto = require('crypto');
const { getApi } = require('./lib/getApi');
const { Sqlite3Database }  = require('./lib/database/Sqlite3Database');

(async () => {
  // Datenbankverbindung aufbauen und Tabellen anlegen
  const database = new Sqlite3Database();
  await database.initialize();
  await database.createUserTable();
  await database.writeUserTable();

  // Initialisiere Express, HTTP-Server und Socket.io, übergebe die Datenbank
  const { http: server_http } = getApi({ database });

  // Server-Konfiguration
  const HOST = "localhost";
  const PORT = 4000;

  // Starte den HTTP-/Socket.io-Server
  server_http.listen(PORT, HOST, () => {
    console.log(`Backend läuft auf http://${HOST}:${PORT}`);
  });
})();
