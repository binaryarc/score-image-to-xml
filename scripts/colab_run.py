import os
import subprocess
import time
from typing import Optional

NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "")


def cleanup_processes() -> None:
    subprocess.run(["pkill", "-9", "-f", "uvicorn"], check=False, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", "ngrok"], check=False, stderr=subprocess.DEVNULL)
    time.sleep(2)


def start_uvicorn() -> subprocess.Popen:
    with open("/tmp/uvicorn.log", "w", encoding="utf-8") as handle:
        handle.write("")
    return subprocess.Popen(
        [
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--log-level",
            "info",
        ],
        stdout=open("/tmp/uvicorn.log", "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )


def start_ngrok(authtoken: str) -> Optional[str]:
    try:
        subprocess.run(["which", "ngrok"], check=True, capture_output=True)
    except Exception:
        subprocess.run(
            [
                "wget",
                "-q",
                "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz",
                "-O",
                "/tmp/ngrok.tgz",
            ],
            check=True,
        )
        subprocess.run(["tar", "xzf", "/tmp/ngrok.tgz", "-C", "/usr/local/bin"], check=True)
        subprocess.run(["chmod", "+x", "/usr/local/bin/ngrok"], check=True)

    if authtoken:
        subprocess.run(
            ["/usr/local/bin/ngrok", "config", "add-authtoken", authtoken],
            check=True,
            capture_output=True,
        )

    process = subprocess.Popen(
        ["/usr/local/bin/ngrok", "http", "8000", "--log", "/tmp/ngrok.log"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)

    try:
        result = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:4040/api/tunnels"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "public_url" in result.stdout:
            import json

            data = json.loads(result.stdout)
            if data.get("tunnels"):
                return data["tunnels"][0]["public_url"]
    except Exception:
        pass
    finally:
        process.poll()

    return None


print("Starting server...")
cleanup_processes()
uvicorn_proc = start_uvicorn()
time.sleep(6)

print("ngrok authtoken URL: https://dashboard.ngrok.com/get-started/your-authtoken")
url = start_ngrok(NGROK_AUTHTOKEN)
print("Uvicorn PID:", uvicorn_proc.pid)
if url:
    print("Public URL:", url)
else:
    print("ngrok URL not available. Check /tmp/ngrok.log")
