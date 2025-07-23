'use strict';

const bcrypt = require('bcryptjs');
const sqlite3 = require('sqlite3').verbose();
const { open } = require('sqlite'); // <--- require, nicht import (außer du nutzt ES Modules)
const fs = require('fs').promises;


class Sqlite3Database {
    constructor () {
        this.db = null;
    }

    async initialize () {
        this.db = await open({
            filename: './backend/users.db',
            driver: sqlite3.Database
        });
    }

    async createUserTable() {
        await this.db.run(`
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                role TEXT
            )
        `);
    }

    async writeUserTable() {
        try {
            // Userdaten aus externer JSON-Datei laden
            const data = await fs.readFile(require('path').join(__dirname, 'seedUsers.json'), 'utf-8');
            const seedUsers = JSON.parse(data);

            for (const u of seedUsers) {
                try {
                    const row = await this.db.get("SELECT * FROM users WHERE username = ?", [u.username]);
                    if (!row) {
                        const hashedPw = await bcrypt.hash(u.password, 10);
                        await this.db.run(
                            "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                            [u.username, hashedPw, u.name, u.role]
                        );
                        console.log(`User ${u.username} angelegt`);
                    }
                } catch (userErr) {
                    console.error(`Fehler beim Anlegen von User ${u.username}:`, userErr);
                }
            }
        } catch (err) {
            console.error('Fehler beim Laden oder Verarbeiten der seedUsers.json:', err);
        }
    }

    async getUser(username) {
        return await this.db.get("SELECT * FROM users WHERE username = ?", [username]);
    }

    async checkPassword(username, password) {
        const user = await this.getUser(username);
        if (!user) return false;
        const valid = await bcrypt.compare(password, user.password);
        return valid ? user : false;
    }

    async getHistogramm(database) {
        const binStart = 0.0;
        const binEnd = 250.0;
        const binStep = 0.5;
        const binCount = Math.round((binEnd - binStart) / binStep) + 1;
        const bins = [];

        const rows = await database.all(
            `
            SELECT
            ROUND((wert - ?) / ?) AS bin_index,
            COUNT(*) AS anzahl
            FROM temperatures
            GROUP BY bin_index
            ORDER BY bin_index
            `,
            [binStart, binStep]
        );

        for (let i = 0; i < binCount; i++) {
            const row = rows.find(r => r.bin_index === i);
            bins.push(row ? row.anzahl : 0);
        }
        return bins;
    }
}

module.exports = { Sqlite3Database };