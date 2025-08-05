
import { Socket, Server as SocketIOServer } from 'socket.io';
import { z } from 'zod';

/**
 * Handler für das Starten des Konfigurationsmodus via Socket.io
 *
 * @param socket - Die Socket.io-Verbindung zum Client
 * @param io - Die Socket.io-Server-Instanz (für Broadcasts)
 * @param options - Objekt mit Timeout-Getter/Setter und Getter/Setter für den Konfigurationsstatus
 */
export function ack_config(
  socket: Socket
) {
  socket.on("ack_config", (payload) => {
    console.log(payload);
  });
}
