use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

/// Holds the handle to the spawned Python backend process.
pub struct BackendProcess(pub Mutex<Option<CommandChild>>);

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // If a second instance is launched, focus the existing window instead.
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            spawn_backend(&handle);
            Ok(())
        })
        .on_window_event(|window, event| {
            // Intercept window close: kill backend first, then exit cleanly.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let app = window.app_handle().clone();
                std::thread::spawn(move || {
                    kill_backend(&app);
                    // Small grace period for the backend to flush any writes.
                    std::thread::sleep(std::time::Duration::from_millis(400));
                    app.exit(0);
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("Voxarah failed to start");
}

/// Spawns the bundled Python backend (voxarah-backend sidecar) on port 8000.
fn spawn_backend(app: &AppHandle) {
    match app.shell().sidecar("voxarah-backend") {
        Err(e) => {
            eprintln!("[voxarah] sidecar not found: {e}");
        }
        Ok(cmd) => {
            match cmd.spawn() {
                Err(e) => eprintln!("[voxarah] failed to spawn backend: {e}"),
                Ok((_rx, child)) => {
                    *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);
                    eprintln!("[voxarah] backend started");
                }
            }
        }
    }
}

/// Sends SIGTERM / TerminateProcess to the backend child process.
fn kill_backend(app: &AppHandle) {
    if let Ok(mut guard) = app.state::<BackendProcess>().0.lock() {
        if let Some(child) = guard.take() {
            let _ = child.kill();
            eprintln!("[voxarah] backend killed");
        }
    }
}
