const video = document.getElementById("video");
const hiddenCanvas = document.getElementById("hiddenCanvas");
const output = document.getElementById("output");
const statusBadge = document.getElementById("status");
const filterBadge = document.getElementById("filterCurrent");
const startBtn = document.getElementById("startBtn");

const ctx = hiddenCanvas.getContext("2d");
const socket = io();

const SEND_FPS = 12;
let streaming = false;
let sendTimer = null;

socket.on("connect", () => {
  statusBadge.textContent = "Connected";
});

socket.on("disconnect", () => {
  statusBadge.textContent = "Disconnected";
});

socket.on("processed_frame", (data) => {
  output.src = data.image;
  filterBadge.textContent = "Current: " + data.filter;
});

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();

    hiddenCanvas.width = 640;
    hiddenCanvas.height = 480;

    streaming = true;
    startBtn.textContent = "Camera Running";
    startBtn.disabled = true;
    statusBadge.textContent = "Streaming";

    sendTimer = setInterval(sendFrame, 1000 / SEND_FPS);
  } catch (err) {
    statusBadge.textContent = "Camera access denied";
    console.error(err);
  }
}

function sendFrame() {
  if (!streaming) return;
  ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  const dataUrl = hiddenCanvas.toDataURL("image/jpeg", 0.6);
  socket.emit("frame", dataUrl);
}

startBtn.addEventListener("click", startCamera);
