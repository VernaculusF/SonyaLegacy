// Atrium Tauri shell — minimal Этап 1.
// Frontend lives at ../dist (built by Vite from ../src/).
// Connection to Sonya VPS goes via WS in JS — Rust shell just hosts the WebView.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .run(tauri::generate_context!())
        .expect("error while running atrium");
}
