// SocketContext.js
import React, { createContext } from "react";
import { io } from "socket.io-client";

export const SocketContext = createContext(null);

export function SocketProvider({ children }) {
  const socket = React.useMemo(
    () => io("http://localhost:4000", { withCredentials: true }),
    []
  );
  return (
    <SocketContext.Provider value={socket}>{children}</SocketContext.Provider>
  );
}
