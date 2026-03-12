const { app, BrowserWindow, session } = require('electron');
const path = require('path');

app.setName('Panglossia');
app.name = 'Panglossia';

// Enable speech recognition API before app is ready
app.commandLine.appendSwitch('enable-speech-dispatcher');
app.commandLine.appendSwitch('enable-features', 'WebSpeechAPI');

function createWindow () {
  const mainWindow = new BrowserWindow({
    width: 1100,
    height: 900,
    title: 'Panglossia',
    icon: path.join(__dirname, '../icon.png'),
    backgroundColor: '#1e1e2e',
    frame: true,
    autoHideMenuBar: true, 
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    }
  });

  // Remove the default menu entirely
  mainWindow.setMenu(null);

  // Automatically grant microphone permissions
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    if (permission === 'media' || permission === 'audio-capture') return true;
    return false;
  });

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media' || permission === 'audio-capture') return callback(true);
    callback(false);
  });

  mainWindow.loadURL('http://localhost:5173');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});