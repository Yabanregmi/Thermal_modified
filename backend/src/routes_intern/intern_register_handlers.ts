import { Server as SocketIOServer, Socket } from 'socket.io';
import { message } from './routes/message' 

export function intern_register_handlers() {
    return function (socket: Socket) {
        message(socket);
    }
};