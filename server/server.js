const express = require("express");
const http = require("http");
const { Server } = require("socket.io");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3000;

app.use(express.static("public"));

io.on("connection", socket => {
    console.log("Connected:", socket.id);

    socket.on("register", data => {
        if (!data || !data.id) return;

        socket.join(data.id);

        socket.data.deviceId = data.id;
        socket.data.type = data.type || "unknown";

        console.log("Registered:", data.id, socket.data.type);

        socket.emit("registered", {
            id: data.id
        });
    });

    socket.on("offer", data => {
        if (!data || !data.target || !data.offer) return;

        io.to(data.target).emit("offer", {
            from: socket.id,
            offer: data.offer
        });
    });

    socket.on("answer", data => {
        if (!data || !data.target || !data.answer) return;

        io.to(data.target).emit("answer", {
            from: socket.id,
            answer: data.answer
        });
    });

    socket.on("ice-candidate", data => {
        if (!data || !data.target || !data.candidate) return;

        io.to(data.target).emit("ice-candidate", {
            from: socket.id,
            candidate: data.candidate
        });
    });

    socket.on("disconnect", reason => {
        console.log("Disconnected:", socket.id, reason);
    });
});

server.listen(PORT, "0.0.0.0", () => {
    console.log(`Server listening on port ${PORT}`);
});
