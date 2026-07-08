const path = require("node:path");
const { app, BrowserWindow, ipcMain } = require("electron");
const { createReadServiceClient } = require("./readServiceClient.cjs");
const { createDiagnosisService } = require("./diagnosisService.cjs");
const { createPiBridge } = require("./piBridge.cjs");

const readClient = createReadServiceClient();
const piBridge = createPiBridge();
const diagnosisService = createDiagnosisService({ readClient, piBridge });

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1080,
    minHeight: 720,
    backgroundColor: "#0d0f12",
    title: "AStock Lens",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    win.loadURL(devUrl);
  } else {
    win.loadFile(path.join(__dirname, "../../dist/index.html"));
  }
}

ipcMain.handle("diagnosis:run", async (_event, prompt) => {
  return diagnosisService.runDiagnosis(String(prompt || ""));
});

ipcMain.handle("runtime:status", async () => {
  const pi = await piBridge.getStatus();
  return {
    readServiceUrl: readClient.baseUrl,
    pi,
  };
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
