import json
import subprocess
import time

# ============================================
# 🔑 여기에 ngrok 토큰을 직접 입력하세요
# ============================================
NGROK_AUTHTOKEN = "여기에_토큰_붙여넣기"  # 예: "2abc123def456..."

# ============================================

def cleanup_processes():
    """기존 프로세스 정리"""
    print("🧹 기존 프로세스 정리 중...")
    subprocess.run(["pkill", "-9", "-f", "uvicorn"], stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["pkill", "-9", "-f", "ngrok"], stderr=subprocess.DEVNULL, check=False)
    time.sleep(2)
    print("✅ 정리 완료")


def check_gpu():
    """GPU 상태 확인"""
    print("🔍 GPU 확인 중...")
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ GPU 감지됨:")
            lines = result.stdout.split("\n")
            for line in lines:
                if "Tesla" in line or "T4" in line or "GPU" in line:
                    print(f"   {line.strip()}")
            return True
        print("❌ GPU를 찾을 수 없습니다")
        print("💡 런타임 → 런타임 유형 변경 → GPU 선택")
        return False
    except Exception as exc:
        print(f"❌ GPU 확인 실패: {exc}")
        return False


def start_uvicorn():
    """Uvicorn 서버 시작"""
    print("🚀 Uvicorn 서버 시작 중...")

    with open("/tmp/uvicorn.log", "w", encoding="utf-8") as handle:
        handle.write("")

    process = subprocess.Popen(
        [
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--timeout-keep-alive",
            "0",
            "--log-level",
            "info",
        ],
        stdout=open("/tmp/uvicorn.log", "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    print("⏳ 서버 초기화 대기 중...")
    time.sleep(8)

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                ["curl", "-s", "http://127.0.0.1:8000/health"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and "healthy" in result.stdout:
                print(f"✅ Uvicorn 실행 성공 (PID: {process.pid})")

                try:
                    health = json.loads(result.stdout)
                    version = health.get("version", "unknown")
                    preprocessing = health.get("preprocessing", "standard")

                    print(f"📌 버전: {version}")
                    print(f"🔧 전처리: {preprocessing}")

                    if health.get("gpu_enabled"):
                        print("⚡ GPU 가속 활성화됨!")
                    else:
                        print("⚠️ CPU 모드로 실행 중")
                except Exception:
                    pass

                return process
        except Exception:
            print(f"   시도 {attempt + 1}/{max_attempts}...")
            time.sleep(3)

    print("❌ Uvicorn 시작 실패")
    print("\n최근 로그:")
    subprocess.run(["tail", "-30", "/tmp/uvicorn.log"], check=False)
    return None


def start_ngrok(authtoken):
    """ngrok 터널 시작"""
    print("🌐 ngrok 설정 중...")

    try:
        subprocess.run(["which", "ngrok"], check=True, capture_output=True)
        print("✅ ngrok 이미 설치됨")
    except Exception:
        print("📥 ngrok 설치 중...")
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
        print("✅ ngrok 설치 완료")

    print("🔑 ngrok 인증 중...")
    subprocess.run(
        ["/usr/local/bin/ngrok", "config", "add-authtoken", authtoken],
        check=True,
        capture_output=True,
    )

    print("🚀 ngrok 터널 시작 중...")
    process = subprocess.Popen(
        ["/usr/local/bin/ngrok", "http", "8000", "--log", "/tmp/ngrok.log"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("⏳ 터널 URL 생성 대기 중...")
    time.sleep(5)

    for _ in range(10):
        try:
            result = subprocess.run(
                ["curl", "-s", "http://127.0.0.1:4040/api/tunnels"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("tunnels") and len(data["tunnels"]) > 0:
                    url = data["tunnels"][0]["public_url"]
                    print(f"✅ ngrok 실행 성공 (PID: {process.pid})")
                    return process, url
        except Exception:
            time.sleep(1)

    print("❌ ngrok URL을 가져올 수 없습니다")
    print("로그 확인:")
    try:
        with open("/tmp/ngrok.log", "r", encoding="utf-8") as handle:
            print(handle.read()[-500:])
    except Exception:
        pass
    return None, None


def monitor_status():
    """서버 상태 모니터링"""
    print("\n" + "=" * 60)
    print("📊 서버 상태")
    print("=" * 60)

    result = subprocess.run(["pgrep", "-f", "uvicorn"], capture_output=True)
    uvicorn_status = "✅ 실행 중" if result.returncode == 0 else "❌ 중지됨"
    print(f"Uvicorn: {uvicorn_status}")

    result = subprocess.run(["pgrep", "-f", "ngrok"], capture_output=True)
    ngrok_status = "✅ 실행 중" if result.returncode == 0 else "❌ 중지됨"
    print(f"ngrok:   {ngrok_status}")

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            gpu_util = result.stdout.strip()
            print(f"GPU:     {gpu_util} 사용 중")
    except Exception:
        print("GPU:     확인 불가")

    print("=" * 60)


print("=" * 60)
print("🎵 MusicXML Converter v3.1 서버 시작")
print("=" * 60)

# 1. GPU 확인
gpu_available = check_gpu()
print()

# 2. authtoken 확인
if not NGROK_AUTHTOKEN or NGROK_AUTHTOKEN == "여기에_토큰_붙여넣기":
    print("🔑 ngrok authtoken이 필요합니다")
    print("   1. https://dashboard.ngrok.com/signup 에서 가입")
    print("   2. https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 복사")
    print()

    authtoken = input("ngrok authtoken을 입력하세요 (또는 스크립트 상단에 저장): ").strip()

    if not authtoken:
        print("\n❌ authtoken이 필요합니다")
        print("💡 스크립트 상단의 NGROK_AUTHTOKEN 변수에 토큰을 저장하면 매번 입력하지 않아도 됩니다")
        raise SystemExit
else:
    authtoken = NGROK_AUTHTOKEN
    print("✅ 저장된 토큰 사용")

print()

# 3. 기존 프로세스 정리
cleanup_processes()

# 4. Uvicorn 시작
uvicorn_proc = start_uvicorn()

if uvicorn_proc:
    print()

    # 5. ngrok 시작
    ngrok_proc, public_url = start_ngrok(authtoken)

    if ngrok_proc and public_url:
        print("\n" + "=" * 60)
        print("🎉 서버 시작 완료!")
        print("=" * 60)
        print("📍 로컬 URL:  http://127.0.0.1:8000")
        print(f"🌍 공개 URL:  {public_url}")
        print("=" * 60)
        print("\n✨ v3.1 새로운 기능:")
        print("   • 10단계 고급 전처리")
        print("   • 4000px 고해상도 업스케일")
        print("   • CLAHE + 언샤프 마스킹")
        print("   • 자동 품질 검증")
        print("\n💡 사용 안내:")
        if gpu_available:
            print("   ⚡ GPU 가속 활성화 - 2~3분 내 처리")
        else:
            print("   ⚠️ CPU 모드 - 5~10분 소요")
        print("   🚀 ngrok 터널 - 타임아웃 없음")
        print("   🎯 향상된 인식률 - 30~50% 개선")
        print("\n📋 유용한 명령어:")
        print("   • 실시간 로그: !tail -f /tmp/uvicorn.log")
        print("   • ngrok 대시보드: http://127.0.0.1:4040")
        print("   • 상태 확인: monitor_status()")
        print("   • 서버 중지: cleanup_processes()")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ ngrok 시작 실패")
        print("=" * 60)
        print("로컬에서는 사용 가능: http://127.0.0.1:8000")
        print("=" * 60)
else:
    print("\n" + "=" * 60)
    print("❌ 서버 시작 실패")
    print("=" * 60)
    subprocess.run(["cat", "/tmp/uvicorn.log"], check=False)
