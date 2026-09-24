import asyncio
import json
import os
import platform
import uuid

import av
import mss
import numpy as np
import psutil
import pyautogui
import socketio

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack


SERVER_URL = os.environ.get(
    "REMOTE_SERVER_URL",
    "https://remotedesktop-yvgh.onrender.com/"
)

DEVICE_ID_FILE = "agent_id.txt"

sio = socketio.AsyncClient()
connections = {}
screen_track = None


def get_device_id():
    if os.path.exists(DEVICE_ID_FILE):
        with open(DEVICE_ID_FILE, "r", encoding="utf-8") as f:
            device_id = f.read().strip()

        if device_id:
            return device_id

    device_id = uuid.uuid4().hex[:12].upper()

    with open(DEVICE_ID_FILE, "w", encoding="utf-8") as f:
        f.write(device_id)

    return device_id


def get_capture_size():
    with mss.mss() as sct:
        monitor = sct.monitors[1]

        width = monitor["width"]
        height = monitor["height"]

    cpu = psutil.cpu_count(logical=True) or 2
    ram = psutil.virtual_memory().total / (1024 ** 3)

    if cpu <= 2 or ram < 4:
        max_width = 1280
    elif cpu <= 4 or ram < 8:
        max_width = 1600
    else:
        max_width = 1920

    if width > max_width:
        ratio = max_width / width
        width = max_width
        height = int(height * ratio)

    width -= width % 2
    height -= height % 2

    return width, height


class ScreenTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]

        self.width, self.height = get_capture_size()

        print(f"Resolution: {self.width}x{self.height}")
        print("FPS: 30")

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        image = np.asarray(
            self.sct.grab(self.monitor)
        )

        image = image[:, :, :3]

        frame = av.VideoFrame.from_ndarray(
            image,
            format="bgr24"
        )

        if (
            frame.width != self.width
            or frame.height != self.height
        ):
            frame = frame.reformat(
                width=self.width,
                height=self.height,
                format="bgr24"
            )

        frame.pts = pts
        frame.time_base = time_base

        return frame

    def close(self):
        self.sct.close()


def handle_input(message):
    try:
        if isinstance(message, bytes):
            message = message.decode("utf-8")

        data = json.loads(message)
    except Exception:
        return

    event = data.get("event")

    try:
        if event == "mouse_move":
            x = float(data.get("x", 0))
            y = float(data.get("y", 0))

            pyautogui.moveTo(
                x,
                y,
                duration=0
            )

        elif event == "mouse_down":
            button = data.get("button", "left")

            if button in ("left", "right", "middle"):
                pyautogui.mouseDown(
                    button=button
                )

        elif event == "mouse_up":
            button = data.get("button", "left")

            if button in ("left", "right", "middle"):
                pyautogui.mouseUp(
                    button=button
                )

        elif event == "mouse_click":
            button = data.get("button", "left")

            if button in ("left", "right", "middle"):
                pyautogui.click(
                    button=button
                )

        elif event == "mouse_wheel":
            delta = int(data.get("delta", 0))

            pyautogui.scroll(delta)

        elif event == "key_down":
            key = data.get("key")

            if key:
                pyautogui.keyDown(key)

        elif event == "key_up":
            key = data.get("key")

            if key:
                pyautogui.keyUp(key)

        elif event == "key_press":
            key = data.get("key")

            if key:
                pyautogui.press(key)

    except Exception as e:
        print("Input error:", e)


@sio.event
async def connect():
    device_id = get_device_id()

    print("Connected to server")
    print(f"PC ID: {device_id}")

    await sio.emit(
        "register",
        {
            "id": device_id,
            "type": "windows"
        }
    )


@sio.event
async def disconnect():
    print("Disconnected from server")


@sio.on("registered")
async def registered(data):
    print(
        "Registered:",
        data.get("id")
    )


@sio.on("connection-request")
async def connection_request(data):
    global screen_track

    browser_socket_id = data.get("from")

    if not browser_socket_id:
        return

    print(
        "Connection request:",
        browser_socket_id
    )

    pc = RTCPeerConnection()

    connections[browser_socket_id] = pc

    if screen_track is None:
        screen_track = ScreenTrack()

    pc.addTrack(screen_track)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(
            "DataChannel:",
            channel.label
        )

        @channel.on("message")
        def on_message(message):
            handle_input(message)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        state = pc.connectionState

        print(
            f"WebRTC {browser_socket_id}:",
            state
        )

        if state in (
            "failed",
            "closed",
            "disconnected"
        ):
            connections.pop(
                browser_socket_id,
                None
            )

            await pc.close()

    offer = await pc.createOffer()

    await pc.setLocalDescription(offer)

    await sio.emit(
        "offer",
        {
            "target": browser_socket_id,
            "offer": {
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp
            }
        }
    )


@sio.on("answer")
async def answer(data):
    browser_socket_id = data.get("from")
    answer_data = data.get("answer")

    if not browser_socket_id:
        return

    if not answer_data:
        return

    pc = connections.get(
        browser_socket_id
    )

    if pc is None:
        return

    await pc.setRemoteDescription(
        RTCSessionDescription(
            sdp=answer_data["sdp"],
            type=answer_data["type"]
        )
    )

    print(
        "Answer received:",
        browser_socket_id
    )


@sio.on("ice-candidate")
async def ice_candidate(data):
    browser_socket_id = data.get("from")
    candidate = data.get("candidate")

    if not browser_socket_id:
        return

    if not candidate:
        return

    pc = connections.get(
        browser_socket_id
    )

    if pc is None:
        return

    print(
        "ICE candidate received:",
        browser_socket_id
    )


async def main():
    print("================================")
    print("Remote PC Agent")
    print("================================")

    if platform.system() != "Windows":
        print(
            "Warning: this agent is designed for Windows."
        )

    print(
        "PC ID:",
        get_device_id()
    )

    print(
        "Server:",
        SERVER_URL
    )

    print("================================")

    while True:
        try:
            await sio.connect(
                SERVER_URL,
                transports=["websocket"]
            )

            await sio.wait()

        except Exception as e:
            print(
                "Connection error:",
                e
            )

            print(
                "Retrying in 5 seconds..."
            )

            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
