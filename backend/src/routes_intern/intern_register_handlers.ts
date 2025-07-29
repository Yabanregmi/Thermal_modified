import { Server as SocketIOServer, Socket } from 'socket.io';
import { message } from './routes/message' 
import { clientResponse } from './routes/clientResponse';

export function intern_register_handlers() {
    return function (socket: Socket) {
        console.log(socket.handshake.headers === socket.request.headers);
        message(socket);
        clientResponse(socket);
    }
};