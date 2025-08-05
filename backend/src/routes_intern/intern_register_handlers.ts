import { Server as SocketIOServer, Socket } from 'socket.io';
import { message } from './routes/message' 
import { clientResponse } from './routes/clientResponse';
import { ack_config } from './routes/ack_config';

export function intern_register_handlers() {
    return function (socket: Socket) {
        message(socket);
        clientResponse(socket);
        ack_config(socket);
    }
};