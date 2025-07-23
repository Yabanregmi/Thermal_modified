'use strict'

// Factory-Funktion für eine Express-Route, die eine Testnachricht zurückgibt
const getTestMessage = function () {
    // Der eigentliche Express-Handler
    return function(req, res) {
        res.json({ message: 'Test: Server express' }); // Sende Test-JSON an den Client
    };
};

module.exports = { getTestMessage };
