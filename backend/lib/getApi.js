'use strict';

const body_parser = require('body-parser');
const cors = require('cors');
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { getTestMessage } = require('./routes_express/getTestMessage');
const { postLogin } = require('./routes_express/postLogin');
const { createSocketHandlers } = require('./routes_socket/onConnection');

/**
 * Initialisiert Express, HTTP-Server und Socket.io, 
 * registriert alle HTTP- und Socket-Handler.
 * Gibt die HTTP-Server-Instanz für den Serverstart zurück.
 */
const getApi = function({ database }) {
    // Globale Servervariablen (werden über Getter/Setter an die Handler gegeben)
    let temperSchwelle = 22;
    let letzteLiveTemperatur = null;
    let konfigAckTimeout = null;
    let konfigReady = false;

    const server_express = express();


    // Setup von CORS und JSON-Body-Parser Middlewareich
    server_express.use(cors({
        origin: "*",
        credentials: true
    }));
    server_express.use(body_parser.json());

    // HTTP-Routen
    server_express.get("/test", getTestMessage());
    server_express.post('/api/login', postLogin({database}));

    // HTTP-Server und Socket.io-Server initialisieren
    const server_http = http.createServer(server_express);

    const io = new Server(server_http, {
        cors: {
            origin:"*",
            credentials: true
        }
    });

    // Socket.io: Registriere alle Event-Handler bei jeder neuen Verbindung
    io.on('connection', createSocketHandlers({
        server_socket: io,
        database,
        getTemperSchwelle: () => temperSchwelle,
        setTemperSchwelle: v => { temperSchwelle = v; },
        getLetzteLiveTemperatur: () => letzteLiveTemperatur,
        setLetzteLiveTemperatur: v => { letzteLiveTemperatur = v; },
        getKonfigAckTimeout: () => konfigAckTimeout,
        setKonfigAckTimeout: v => { konfigAckTimeout = v; },
        getKonfigReady: () => konfigReady,
        setKonfigReady: v => { konfigReady = v; }
    }));

    // Gebe HTTP-Server-Instanz zurück (wird zum Starten des Servers verwendet)
    return { http: server_http };
};

module.exports = { getApi };
