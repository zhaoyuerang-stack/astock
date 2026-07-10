const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("astock", {
  apiVersion: 2,
  runDiagnosis(payload) {
    return ipcRenderer.invoke("diagnosis:run", payload);
  },
  getRuntimeStatus() {
    return ipcRenderer.invoke("runtime:status");
  },
});
