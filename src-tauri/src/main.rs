#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};

const DEFAULT_PORT: u16 = 8765;

struct BackendState {
    child: Mutex<Option<Child>>,
    owns_process: bool,
}

fn project_root_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut out: Vec<PathBuf> = Vec::new();

    if let Ok(dir) = app.path().resource_dir() {
        out.push(dir);
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(mut p) = exe.parent().map(PathBuf::from) {
            for _ in 0..8 {
                out.push(p.clone());
                if !p.pop() {
                    break;
                }
            }
        }
    }

    if let Ok(cwd) = std::env::current_dir() {
        out.push(cwd);
    }

    out
}

fn find_project_root(app: &tauri::AppHandle) -> Option<PathBuf> {
    for base in project_root_candidates(app) {
        let mut dir = base;
        for _ in 0..10 {
            if dir.join("app.py").is_file() {
                return Some(dir);
            }
            if !dir.pop() {
                break;
            }
        }
    }
    None
}

/// Build the ordered list of (program, args) candidates we will try to spawn
/// in [`start_backend`]. The first candidate that successfully spawns wins.
///
/// Priority:
///   1. Portable embeddable runtime: `<project_root>/runtime/python(.exe) -m uvicorn ...`
///   2. Project virtualenv uvicorn (`.venv`)
///   3. System Python module fallbacks (`python` / `py` / `python3`)
fn uvicorn_candidates(project_root: &Path) -> Vec<(PathBuf, Vec<String>)> {
    let common_args: Vec<String> = vec![
        "app:app".into(),
        "--host".into(),
        "127.0.0.1".into(),
        "--port".into(),
        DEFAULT_PORT.to_string(),
    ];

    let mut candidates: Vec<(PathBuf, Vec<String>)> = Vec::new();

    let mut module_args: Vec<String> = vec!["-m".into(), "uvicorn".into()];
    module_args.extend(common_args.clone());

    // 1) Portable runtime shipped next to the app (Variant A portable pack)
    let portable_python = if cfg!(windows) {
        project_root.join("runtime").join("python.exe")
    } else {
        project_root.join("runtime").join("bin").join("python3")
    };
    if portable_python.is_file() {
        candidates.push((portable_python, module_args.clone()));
    }

    // 2) Project virtualenv uvicorn
    let venv_uvicorn = if cfg!(windows) {
        project_root
            .join(".venv")
            .join("Scripts")
            .join("uvicorn.exe")
    } else {
        project_root.join(".venv").join("bin").join("uvicorn")
    };
    if venv_uvicorn.is_file() {
        candidates.push((venv_uvicorn, common_args));
    }

    // 3) System Python fallbacks
    if cfg!(windows) {
        candidates.push((PathBuf::from("python"), module_args.clone()));
        candidates.push((PathBuf::from("py"), module_args));
    } else {
        candidates.push((PathBuf::from("python3"), module_args.clone()));
        candidates.push((PathBuf::from("python"), module_args));
    }

    candidates
}

fn wait_for_port(addr: SocketAddr, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if TcpStream::connect(addr).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(120));
    }
    false
}

fn probe_http_ok() -> bool {
    let addrs: Vec<SocketAddr> = match format!("127.0.0.1:{}", DEFAULT_PORT).to_socket_addrs() {
        Ok(a) => a.collect(),
        Err(_) => return false,
    };
    let Some(addr) = addrs.first().copied() else {
        return false;
    };

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(400)) {
        Ok(s) => s,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let req = b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(req).is_err() {
        return false;
    }

    let mut buf = [0u8; 32];
    match stream.read(&mut buf) {
        Ok(n) if n >= 4 => {
            let head = &buf[..n.min(12)];
            head.starts_with(b"HTTP/1")
        }
        _ => false,
    }
}

fn start_backend(app: &tauri::AppHandle) -> Result<Child, String> {
    let project_root = find_project_root(app).ok_or_else(|| {
        "MediaFlow project root not found (expected app.py near the executable or in a parent directory)."
            .to_string()
    })?;

    let candidates = uvicorn_candidates(&project_root);
    if candidates.is_empty() {
        return Err("No uvicorn launch candidates available.".into());
    }

    let mut last_err = String::new();
    for (program, args) in candidates {
        let mut cmd = Command::new(&program);
        cmd.args(&args)
            .current_dir(&project_root)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        // Avoid a flashing console window when spawning the portable/system Python.
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        match cmd.spawn() {
            Ok(child) => return Ok(child),
            Err(e) => {
                last_err = format!("'{}' failed: {}", program.display(), e);
            }
        }
    }
    Err(format!("Could not launch uvicorn. Last error: {last_err}"))
}

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendState>();
    if !state.owns_process {
        return;
    }
    let mut guard = state.child.lock().expect("backend mutex poisoned");
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle().clone();

            let listen: SocketAddr = format!("127.0.0.1:{DEFAULT_PORT}")
                .parse()
                .expect("static listen addr");

            if probe_http_ok() {
                app.manage(BackendState {
                    child: Mutex::new(None),
                    owns_process: false,
                });
                return Ok(());
            }

            let mut child = start_backend(&handle)?;

            if !wait_for_port(listen, Duration::from_secs(20)) {
                let _ = child.kill();
                return Err(
                    "FastAPI did not start: port 8765 was not opened within the timeout.".into(),
                );
            }

            if !probe_http_ok() {
                let _ = child.kill();
                return Err("FastAPI is not responding over HTTP on 127.0.0.1:8765.".into());
            }

            app.manage(BackendState {
                child: Mutex::new(Some(child)),
                owns_process: true,
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_backend(app);
            }
        });
}
