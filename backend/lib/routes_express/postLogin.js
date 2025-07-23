'use strict';

const bcrypt = require('bcryptjs');

/**
 * Factory-Funktion für den Login-POST-Handler.
 * Erwartet ein Objekt mit einer Datenbankinstanz, die eine getUser-Methode besitzt.
 */
const postLogin = function ({ database }) {
    // Der eigentliche Express-Handler für /api/login
    return async function(req, res) {
        const { username, password } = req.body;
        // Suche User in der Datenbank
        const user = await database.getUser(username);
        if (!user) {
            // Kein User gefunden: Fehler zurückgeben
            return res.status(401).json({ error: "Invalid username or password" });
        }
        // Passwort prüfen
        const valid = await bcrypt.compare(password, user.password);
        if (valid) {
            // Login erfolgreich: Userdaten (ohne Passwort) zurückgeben
            res.json({ name: user.name, username: user.username, role: user.role });
        } else {
            // Passwort falsch: Fehler zurückgeben
            res.status(401).json({ error: "Invalid username or password"  });
        }
    };
};

module.exports = { postLogin };
