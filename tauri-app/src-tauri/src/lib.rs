use std::net::TcpListener;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, WebviewWindow};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

pub struct BackendProcess(pub Mutex<Option<CommandChild>>);
pub struct BackendPort(pub u16);

/// Find a free TCP port on localhost.
fn find_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("failed to bind ephemeral port")
        .local_addr()
        .unwrap()
        .port()
}

pub fn run() {
    let port = find_free_port();
    eprintln!("[voxarah] using port {port}");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .manage(BackendProcess(Mutex::new(None)))
        .manage(BackendPort(port))
        .setup(move |app| {
            let handle = app.handle().clone();
            spawn_backend(&handle, port);

            // Inject the port into the WebView before the page logic runs.
            if let Some(win) = app.get_webview_window("main") {
                inject_port(&win, port);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let app = window.app_handle().clone();
                std::thread::spawn(move || {
                    kill_backend(&app);
                    std::thread::sleep(std::time::Duration::from_millis(400));
                    app.exit(0);
                });
            }
        })
        .run(tauri::generate_context!())
        .expect("Voxarah failed to start");
}

/// Inject `window.VOXARAH_PORT` so the frontend JS can construct API URLs.
fn inject_port(win: &WebviewWindow, port: u16) {
    let script = format!("window.VOXARAH_PORT = {port};");
    // eval_script runs before page scripts on the next navigation.
    let _ = win.eval(&script);
}

fn spawn_backend(app: &AppHandle, port: u16) {
    match app.shell().sidecar("voxarah-backend") {
        Err(e) => eprintln!("[voxarah] sidecar not found: {e}"),
        Ok(cmd) => {
            match cmd.env("VOXARAH_PORT", port.to_string()).spawn() {
                Err(e) => eprintln!("[voxarah] failed to spawn backend: {e}"),
                Ok((_rx, child)) => {
                    *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);
                    eprintln!("[voxarah] backend started on port {port}");
                }
            }
        }
    }
}

fn kill_backend(app: &AppHandle) {
    if let Ok(mut guard) = app.state::<BackendProcess>().0.lock() {
        if let Some(child) = guard.take() {
            let _ = child.kill();
            eprintln!("[voxarah] backend killed");
        }
    }
}
