const socket = io();

const pcIdInput = document.getElementById("pcId");
const connectButton = document.getElementById("connect");
const status = document.getElementById("status");
const screen = document.getElementById("screen");
const noScreen = document.getElementById("no-screen");

let peer = null;
let targetId = null;

connectButton.addEventListener("click", async () => {
    targetId = pcIdInput.value.trim();

    if (!targetId) {
        status.textContent = "PC IDを入力してください";
        return;
    }

    status.textContent = "接続中...";

    socket.emit("register", {
        id: crypto.randomUUID(),
        type: "browser"
    });

    peer = new RTCPeerConnection({
        iceServers: [
            {
                urls: "stun:stun.l.google.com:19302"
            }
        ]
    });

    peer.ontrack = event => {
        if (event.streams.length === 0) return;

        screen.srcObject = event.streams[0];
        screen.style.display = "block";
        noScreen.style.display = "none";

        status.textContent = "接続しました";
    };

    peer.onicecandidate = event => {
        if (!event.candidate) return;

        socket.emit("ice-candidate", {
            target: targetId,
            candidate: event.candidate
        });
    };

    peer.onconnectionstatechange = () => {
        status.textContent = `接続状態: ${peer.connectionState}`;
    };

    socket.emit("request-connection", {
        target: targetId
    });
});

socket.on("offer", async data => {
    if (!peer) return;

    await peer.setRemoteDescription(data.offer);

    const answer = await peer.createAnswer();
    await peer.setLocalDescription(answer);

    socket.emit("answer", {
        target: data.from,
        answer
    });
});

socket.on("ice-candidate", async data => {
    if (!peer || !data.candidate) return;

    try {
        await peer.addIceCandidate(data.candidate);
    } catch (e) {
        console.error(e);
    }
});
