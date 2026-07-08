const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("astock", {
  runDiagnosis(prompt) {
    return ipcRenderer.invoke("diagnosis:run", prompt);
  },
  getRuntimeStatus() {
    return ipcRenderer.invoke("runtime:status");
  },
});
