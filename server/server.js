const express = require("express");
const http = require("http");
const { Server } = require("socket.io");

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

const PORT = process.env.PORT || 3000;

app.use(express.static("public"));

const devices = new Map();

io.on("connection", socket => {
    console.log("Connected:", socket.id);

    socket.on("register", data => {
        if (!data || !data.id || !data.type) {
            socket.emit("error-message", {
                message: "Invalid registration"
            });
            return;
        }

        const id = String(data.id);
        const type = String(data.type);

        socket.data.deviceId = id;
        socket.data.type = type;

        devices.set(id, {
            socketId: socket.id,
            type,
            id
        });

        socket.join(id);

        console.log(`Registered: ${id} (${type})`);

        socket.emit("registered", {
            id,
            type
        });
    });

    socket.on("request-connection", data => {
        if (!data || !data.target) return;

        const target = devices.get(String(data.target));

        if (!target) {
            socket.emit("connection-error", {
                message: "PC not found"
            });
            return;
        }

        io.to(target.socketId).emit("connection-request", {
            from: socket.id,
            browserId: socket.data.deviceId || null
        });

        console.log(
            `Connection request: ${socket.data.deviceId || socket.id} -> ${data.target}`
        );
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
        const id = socket.data.deviceId;

        if (id) {
            const device = devices.get(id);

            if (device && device.socketId === socket.id) {
                devices.delete(id);
            }

            console.log(`Unregistered: ${id}`);
        }

        console.log(`Disconnected: ${socket.id} (${reason})`);
    });
});

app.get("/api/devices", (req, res) => {
    const result = [];

    for (const device of devices.values()) {
        result.push({
            id: device.id,
            type: device.type
        });
    }

    res.json(result);
});

server.listen(PORT, "0.0.0.0", () => {
    console.log(`Remote PC server listening on port ${PORT}`);
});
