// Handler für das "getKonfigStatus"-Event via Socket.io
const onGetKonfigStatus = function(socket, io) {
  let imKonfigModus = false; // Lokaler Status für den Konfigurationsmodus

  socket.on("getKonfigStatus", () => {
    io.emit("konfigStatus", imKonfigModus); // Broadcast an alle Clients
  });
};

module.exports = { onGetKonfigStatus };
