import { Server as SocketIOServer, Socket } from 'socket.io';
import { message } from './routes/message' 
import { clientResponse } from './routes/clientResponse';

export function intern_register_handlers() {
    return function (socket: Socket) {
        message(socket);
        clientResponse(socket);
    }
};