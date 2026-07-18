const video = document.getElementById("video");
const hiddenCanvas = document.getElementById("hiddenCanvas");
const output = document.getElementById("output");
const statusBadge = document.getElementById("status");
const filterBadge = document.getElementById("filterCurrent");
const startBtn = document.getElementById("startBtn");

const ctx = hiddenCanvas.getContext("2d");
const socket = io();

const CAPTURE_WIDTH = 480;
const CAPTURE_HEIGHT = 360;
const MAX_FPS = 10; // upper bound even if the server responds fast
const JPEG_QUALITY = 0.5;

let streaming = false;
let waitingForServer = false;
let sendTimer = null;

socket.on("connect", () => {
  statusBadge.textContent = "Connected";
  waitingForServer = false;
});

socket.on("disconnect", () => {
  statusBadge.textContent = "Disconnected";
});

socket.on("processed_frame", (data) => {
  output.src = data.image;
  filterBadge.textContent = "Current: " + data.filter;
  waitingForServer = false; // server is ready for the next frame
});

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: CAPTURE_WIDTH, height: CAPTURE_HEIGHT },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();

    hiddenCanvas.width = CAPTURE_WIDTH;
    hiddenCanvas.height = CAPTURE_HEIGHT;

    streaming = true;
    startBtn.textContent = "Camera Running";
    startBtn.disabled = true;
    statusBadge.textContent = "Streaming";

    sendTimer = setInterval(sendFrame, 1000 / MAX_FPS);
  } catch (err) {
    statusBadge.textContent = "Camera access denied";
    console.error(err);
  }
}

function sendFrame() {
  if (!streaming) return;
  // Skip this tick if the server hasn't replied to the last frame yet.
  // This is what stops the lag from building up over time.
  if (waitingForServer) return;

  ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  const dataUrl = hiddenCanvas.toDataURL("image/jpeg", JPEG_QUALITY);
  waitingForServer = true;
  socket.emit("frame", dataUrl);
}

startBtn.addEventListener("click", startCamera);
