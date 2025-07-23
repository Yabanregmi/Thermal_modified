'use strict';

// Importiere alle einzelnen Socket-Event-Handler (jeder Handler registriert bestimmte Events für einen Socket)
const { onKonfigStart } = require('./onKonfigStart');
const { onKonfigEnde } = require('./onKonfigEnde');
const { onGetKonfigStatus } = require('./onGetKonfigStatus');
const { onKonfigReady } = require('./onKonfigReady');
const { onSetSchwelle } = require('./onSetSchwelle');
const { onGetSchwelle } = require('./onGetSchwelle');
const { onLiveTemperatur } = require('./onLiveTemperatur');
const { onGetHistogramm } = require('./onGetHistogramm');

/**
 * Factory-Funktion, die bei jeder neuen Socket-Verbindung alle relevanten Event-Handler registriert.
 * 
 * @param {object} param0 - Enthält alle globalen States und Setter/Getter sowie die Server-Instanz und Datenbank.
 * @returns {function} - Handler, der beim 'connection'-Event von Socket.io aufgerufen wird.
 */
const createSocketHandlers = function({ 
    server_socket,                    // Die Socket.io-Server-Instanz (für Broadcasts)
    database,                         // Die Datenbankinstanz (für DB-Zugriffe in Handlers)
    konfigAckTimeout, setKonfigAckTimeout,   // Globale Variable + Setter für Konfig-Ack-Timeout
    konfigReady, setKonfigReady,             // Globale Variable + Setter für Konfig-Status
    temperSchwelle, setTemperSchwelle,       // Globale Variable + Setter für Temperaturschwelle
    letzteLiveTemperatur, setLetzteLiveTemperatur // Globale Variable + Setter für letzte Temperatur
}) {
    // Diese Funktion wird für jeden neuen Socket aufgerufen
    return function(socket) {
        // Registriert Handler für den Start der Konfiguration
        onKonfigStart(socket, server_socket, {
            konfigAckTimeoutRef: () => konfigAckTimeout, // Getter für aktuellen Timeout
            setKonfigAckTimeout,                         // Setter für Timeout
            konfigReadyRef: () => konfigReady,           // Getter für Konfig-Status
            setKonfigReady                               // Setter für Konfig-Status
        });
        // Registriert Handler für das Ende der Konfiguration
        onKonfigEnde(socket, server_socket, {
            konfigAckTimeoutRef: () => konfigAckTimeout,
            setKonfigReady
        });
        // Handler für Statusabfrage der Konfiguration (z.B. ob im Konfig-Modus)
        onGetKonfigStatus(socket, server_socket, {});

        // Handler für das Event "Konfig bereit"
        onKonfigReady(socket, server_socket, {    
            konfigAckTimeoutRef: () => konfigAckTimeout,
            setKonfigReady
        });

        // Handler für das Setzen und Abfragen der Temperaturschwelle
        onSetSchwelle(socket, server_socket, () => temperSchwelle, setTemperSchwelle);
        onGetSchwelle(socket, server_socket, () => temperSchwelle, setTemperSchwelle);

        // Handler für Live-Temperaturdaten (z.B. von der Python-App)
        onLiveTemperatur(socket, server_socket, () => letzteLiveTemperatur, setLetzteLiveTemperatur);

        // Handler für das Histogramm der Temperaturen (z.B. für Statistiken)
        onGetHistogramm(socket, database);
    };
};

module.exports = { createSocketHandlers };
