def style_block() -> str:
    return """
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
          }
          .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 760px;
            width: 100%;
          }
          h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
          }
          .version {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
          }
          .badges {
            margin-bottom: 25px;
          }
          .badge {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 8px;
            margin-bottom: 8px;
          }
          .badge-gpu { background: #10b981; color: white; }
          .badge-ngrok { background: #3b82f6; color: white; }
          .badge-fix { background: #ef4444; color: white; animation: pulse 2s infinite; }

          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
          }

          .upload-area {
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
            margin: 30px 0;
          }
          .upload-area:hover {
            border-color: #667eea;
            background: #f8f9ff;
          }
          .upload-area.dragover {
            border-color: #667eea;
            background: #f0f4ff;
          }
          input[type="file"] {
            display: none;
          }
          .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
          }
          .upload-text {
            color: #666;
            font-size: 16px;
          }
          button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 32px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            transition: all 0.3s;
          }
          button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
          }
          button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }
          .info {
            margin-top: 30px;
            padding: 25px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            font-size: 14px;
          }
          .info-item {
            margin: 12px 0;
            display: flex;
            align-items: center;
          }
          .info-icon {
            margin-right: 12px;
            font-size: 20px;
          }
          .new-feature {
            background: #fef3c7;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #ef4444;
          }
          #status {
            margin-top: 20px;
            padding: 18px;
            border-radius: 10px;
            display: none;
            font-weight: 600;
          }
          #status.processing {
            background: #fff3cd;
            color: #856404;
            display: block;
            animation: fadeIn 0.3s;
          }
          #status.error {
            background: #fee2e2;
            color: #991b1b;
            display: block;
          }
          #status.done {
            background: #dcfce7;
            color: #166534;
            display: block;
          }
          .progress {
            margin-top: 20px;
            padding: 16px;
            border-radius: 12px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
          }
          .progress-title {
            font-size: 14px;
            font-weight: 700;
            color: #334155;
            margin-bottom: 8px;
          }
          .progress-message {
            font-size: 13px;
            color: #475569;
            margin-bottom: 10px;
          }
          .step-list {
            list-style: none;
            display: grid;
            gap: 6px;
          }
          .step-list li {
            padding: 8px 10px;
            border-radius: 8px;
            background: #f1f5f9;
            color: #64748b;
            font-size: 13px;
          }
          .step-list li.active {
            background: #e0e7ff;
            color: #1e3a8a;
            font-weight: 600;
          }
          .step-list li.done {
            background: #dcfce7;
            color: #166534;
          }
          .step-list li.error {
            background: #fee2e2;
            color: #991b1b;
            font-weight: 600;
          }
          .log-box {
            margin-top: 16px;
            padding: 12px;
            border-radius: 10px;
            background: #0f172a;
            color: #e2e8f0;
            font-size: 12px;
            height: 160px;
            overflow: auto;
            white-space: pre-wrap;
          }

          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
          }

          .filename {
            font-size: 14px;
            color: #666;
            margin-top: 15px;
            font-style: italic;
          }
        </style>
    """


def header_html() -> str:
    return """
          <h1>🎼 악보 이미지 → MusicXML 변환기</h1>
          <div class="version">Advanced Error Correction v3.1</div>
    """


def badges_html() -> str:
    return """
          <div class="badges">
            <span class="badge badge-gpu">⚡ GPU 가속</span>
            <span class="badge badge-ngrok">🌐 무제한 처리</span>
            <span class="badge badge-fix">🛠️ NEW: 오류 자동 수정</span>
          </div>
    """


def new_feature_html() -> str:
    return """
          <div class="new-feature">
            <strong>✨ v3.1 업데이트:</strong> MusicXML 오류 자동 수정 기능 추가! (sound 태그, measure 길이 등)
          </div>
    """


def form_html() -> str:
    return """
          <form id="uploadForm" action="/convert" method="post" enctype="multipart/form-data">
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
              <div class="upload-icon">📄</div>
              <div class="upload-text">악보 이미지를 클릭하거나 드래그하여 업로드</div>
              <div class="filename" id="filename"></div>
            </div>
            <input type="file" name="file" id="fileInput" accept="image/*" required />
            <button type="submit" id="submitBtn">🚀 변환 시작</button>
          </form>
    """


def status_html() -> str:
    return """
          <div id="status"></div>
          <div class="progress">
            <div class="progress-title">진행 상태</div>
            <div class="progress-message" id="progressMessage">대기 중</div>
            <ul class="step-list" id="stepList">
              <li data-step="upload">파일 수신</li>
              <li data-step="preprocess">이미지 전처리</li>
              <li data-step="oemer">AI 인식</li>
              <li data-step="fix">MusicXML 오류 수정</li>
              <li data-step="complete">변환 완료</li>
            </ul>
            <pre class="log-box" id="logBox">로그 대기 중...</pre>
          </div>
    """


def info_html() -> str:
    return """
          <div class="info">
            <div class="info-item">
              <span class="info-icon">⚡</span>
              <div><strong>GPU 가속:</strong> 2~3분 내 빠른 처리</div>
            </div>
            <div class="info-item">
              <span class="info-icon">🛠️</span>
              <div><strong>오류 자동 수정:</strong> MuseScore 호환 보장</div>
            </div>
            <div class="info-item">
              <span class="info-icon">🔍</span>
              <div><strong>고급 전처리:</strong> 해상도 최적화, CLAHE, 언샤프 마스킹</div>
            </div>
            <div class="info-item">
              <span class="info-icon">📤</span>
              <div><strong>출력:</strong> .musicxml 파일 (MusicXML 3.1)</div>
            </div>
            <div class="info-item">
              <span class="info-icon">💡</span>
              <div><strong>권장:</strong> 선명한 악보 이미지</div>
            </div>
          </div>
    """


def script_block() -> str:
    return """
        <script>
          const fileInput = document.getElementById('fileInput');
          const uploadArea = document.getElementById('uploadArea');
          const filename = document.getElementById('filename');
          const form = document.getElementById('uploadForm');
          const submitBtn = document.getElementById('submitBtn');
          const status = document.getElementById('status');
          const progressMessage = document.getElementById('progressMessage');
          const stepList = document.getElementById('stepList');
          const logBox = document.getElementById('logBox');

          const stepOrder = ['upload', 'preprocess', 'oemer', 'fix', 'complete'];

          let pollTimer = null;

          function setStatus(type, message) {
            status.className = type;
            status.textContent = message;
          }

          function updateSteps(activeStep, statusType) {
            const items = stepList.querySelectorAll('li');
            items.forEach((item) => {
              const step = item.getAttribute('data-step');
              item.classList.remove('active', 'done', 'error');
              if (statusType === 'error') {
                if (step === activeStep || step === 'complete') {
                  item.classList.add('error');
                }
                return;
              }
              const currentIndex = stepOrder.indexOf(activeStep);
              const itemIndex = stepOrder.indexOf(step);
              if (itemIndex < 0) return;
              if (itemIndex < currentIndex) {
                item.classList.add('done');
              } else if (itemIndex === currentIndex) {
                item.classList.add('active');
              }
            });
          }

          function renderProgress(data) {
            if (data.message) {
              progressMessage.textContent = data.message;
            }
            if (data.step) {
              updateSteps(data.step, data.status);
            }
            if (Array.isArray(data.logs) && data.logs.length) {
              logBox.textContent = data.logs.join('\\n');
              logBox.scrollTop = logBox.scrollHeight;
            }
          }

          function stopPolling() {
            if (pollTimer) {
              clearInterval(pollTimer);
              pollTimer = null;
            }
          }

          async function pollProgress(jobId) {
            try {
              const res = await fetch(`/progress/${jobId}`);
              if (!res.ok) return;
              const data = await res.json();
              renderProgress(data);
              if (data.status === 'done') {
                setStatus('done', '변환 완료! 파일 다운로드를 확인하세요.');
                stopPolling();
              } else if (data.status === 'error') {
                setStatus('error', data.message || '변환 실패');
                stopPolling();
              }
            } catch (err) {
              console.warn('progress poll failed', err);
            }
          }

          function startPolling(jobId) {
            stopPolling();
            pollProgress(jobId);
            pollTimer = setInterval(() => pollProgress(jobId), 1000);
          }

          function getFilenameFromDisposition(disposition) {
            if (!disposition) return null;
            const match = disposition.match(/filename="?([^"]+)"?/);
            return match ? match[1] : null;
          }

          fileInput.onchange = function(e) {
            if (e.target.files.length > 0) {
              filename.textContent = '선택된 파일: ' + e.target.files[0].name;
            }
          };

          uploadArea.ondragover = function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
          };

          uploadArea.ondragleave = function(e) {
            uploadArea.classList.remove('dragover');
          };

          uploadArea.ondrop = function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            if (e.dataTransfer.files.length > 0) {
              fileInput.files = e.dataTransfer.files;
              filename.textContent = '선택된 파일: ' + e.dataTransfer.files[0].name;
            }
          };

          form.onsubmit = async function(e) {
            e.preventDefault();
            if (!fileInput.files.length) return;

            const jobId = (crypto && crypto.randomUUID) ? crypto.randomUUID() : `job_${Date.now()}`;
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('job_id', jobId);

            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ 처리 중...';
            setStatus('processing', '업로드 및 변환 시작...');
            progressMessage.textContent = '작업 준비 중';
            logBox.textContent = '로그 대기 중...';
            updateSteps('upload', 'processing');

            startPolling(jobId);

            try {
              const response = await fetch('/convert', { method: 'POST', body: formData });
              if (!response.ok) {
                let detail = '변환 실패';
                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                  const data = await response.json();
                  detail = data.detail || detail;
                } else {
                  detail = await response.text();
                }
                setStatus('error', detail);
                stopPolling();
                return;
              }

              const blob = await response.blob();
              const disposition = response.headers.get('Content-Disposition');
              const downloadName = getFilenameFromDisposition(disposition) || 'output.musicxml';
              const url = window.URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = downloadName;
              document.body.appendChild(link);
              link.click();
              link.remove();
              window.URL.revokeObjectURL(url);

              setStatus('done', '변환 완료! 파일이 다운로드되었습니다.');
            } catch (err) {
              setStatus('error', '요청 중 오류가 발생했습니다.');
            } finally {
              submitBtn.disabled = false;
              submitBtn.textContent = '🚀 변환 시작';
            }
          };
        </script>
    """
