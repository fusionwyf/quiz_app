use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// 后端 sidecar 进程句柄，退出时负责杀掉
struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

fn pick_free_port() -> Result<u16, Box<dyn std::error::Error>> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

/// 等待后端端口可连接（onefile 解压 + FastAPI 启动需要几秒）
fn wait_backend_ready(port: u16) -> Result<(), Box<dyn std::error::Error>> {
    let addr: SocketAddr = format!("127.0.0.1:{port}").parse()?;
    for _ in 0..300 {
        if TcpStream::connect_timeout(&addr, Duration::from_secs(1)).is_ok() {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    Err(format!("后端进程在 60 秒内未就绪（端口 {port}）").into())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // 二次启动时聚焦已有窗口
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            let port = pick_free_port()?;

            let (mut rx, child) = app
                .shell()
                .sidecar("quiz-backend")?
                .args([
                    "--host",
                    "127.0.0.1",
                    "--port",
                    &port.to_string(),
                    "--parent-pid",
                    &std::process::id().to_string(),
                ])
                .spawn()?;

            // 持续消费 sidecar 输出，防止管道写满把后端阻塞住
            tauri::async_runtime::spawn(async move {
                while rx.recv().await.is_some() {}
            });

            *app.state::<BackendState>().child.lock().unwrap() = Some(child);

            wait_backend_ready(port)?;

            // 后端就绪后再建窗口；initialization_script 在页面脚本执行前
            // 注入 window.__BACKEND_PORT__，前端 client.ts 会优先使用它
            WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("刷题助手")
                .inner_size(1280.0, 860.0)
                .min_inner_size(960.0, 640.0)
                .initialization_script(&format!("window.__BACKEND_PORT__ = {port};"))
                .build()?;

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app, event| match event {
            RunEvent::ExitRequested { .. } => {
                eprintln!("[lifecycle] ExitRequested");
            }
            RunEvent::Exit => {
                eprintln!("[lifecycle] Exit, killing backend");
                if let Some(child) = app.state::<BackendState>().child.lock().unwrap().take() {
                    kill_process_tree(child.pid());
                }
                eprintln!("[lifecycle] backend killed");
                // 清理完成后强制退出，兜底事件循环可能的挂起
                std::process::exit(0);
            }
            _ => {}
        });
}

/// PyInstaller onefile 是进程树（bootloader → server），必须整树杀
#[cfg(windows)]
fn kill_process_tree(pid: u32) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = std::process::Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
}

#[cfg(not(windows))]
fn kill_process_tree(pid: u32) {
    let _ = pid; // 非 Windows 下由 --parent-pid 监听兜底
}
