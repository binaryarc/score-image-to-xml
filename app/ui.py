def upload_form_html() -> str:
    return """
    <!doctype html>
    <html lang=\"ko\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>악보 이미지 → MusicXML 변환기 v3.1</title>
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
            max-width: 700px;
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
          input[type=\"file\"] {
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
      </head>
      <body>
        <div class=\"container\">
          <h1>🎵 악보 이미지 → MusicXML 변환기</h1>
          <div class=\"version\">Advanced Error Correction v3.1</div>

          <div class=\"badges\">
            <span class=\"badge badge-gpu\">⚡ GPU 가속</span>
            <span class=\"badge badge-ngrok\">🚀 무제한 처리</span>
            <span class=\"badge badge-fix\">🔧 NEW: 오류 자동 수정</span>
          </div>

          <div class=\"new-feature\">
            <strong>🆕 v3.1 업데이트:</strong> MusicXML 오류 자동 수정 기능 추가! (sound 태그, measure 길이 등)
          </div>

          <form id=\"uploadForm\" action=\"/convert\" method=\"post\" enctype=\"multipart/form-data\">
            <div class=\"upload-area\" id=\"uploadArea\" onclick=\"document.getElementById('fileInput').click()\">
              <div class=\"upload-icon\">📷</div>
              <div class=\"upload-text\">악보 이미지를 클릭하거나 드래그하여 업로드</div>
              <div class=\"filename\" id=\"filename\"></div>
            </div>
            <input type=\"file\" name=\"file\" id=\"fileInput\" accept=\"image/*\" required />
            <button type=\"submit\" id=\"submitBtn\">🚀 변환 시작</button>
          </form>

          <div id=\"status\"></div>

          <div class=\"info\">
            <div class=\"info-item\">
              <span class=\"info-icon\">⚡</span>
              <div><strong>GPU 가속:</strong> 2~3분 내 빠른 처리</div>
            </div>
            <div class=\"info-item\">
              <span class=\"info-icon\">🔧</span>
              <div><strong>오류 자동 수정:</strong> MuseScore 호환 보장</div>
            </div>
            <div class=\"info-item\">
              <span class=\"info-icon\">✨</span>
              <div><strong>고급 전처리:</strong> 해상도 최적화, CLAHE, 언샤프 마스킹</div>
            </div>
            <div class=\"info-item\">
              <span class=\"info-icon\">📝</span>
              <div><strong>출력:</strong> .musicxml 파일 (MusicXML 3.1)</div>
            </div>
            <div class=\"info-item\">
              <span class=\"info-icon\">💡</span>
              <div><strong>권장:</strong> 선명한 악보 이미지</div>
            </div>
          </div>
        </div>

        <script>
          const fileInput = document.getElementById('fileInput');
          const uploadArea = document.getElementById('uploadArea');
          const filename = document.getElementById('filename');
          const form = document.getElementById('uploadForm');
          const submitBtn = document.getElementById('submitBtn');
          const status = document.getElementById('status');

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

          form.onsubmit = function(e) {
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ 처리 중...';

            status.className = 'processing';
            status.innerHTML = `
              🎵 <strong>악보 분석 중...</strong><br>
              <small>• 이미지 전처리 (10단계)<br>
              • AI 인식 및 변환<br>
              • MusicXML 오류 자동 수정<br>
              • 2~3분 소요됩니다</small>
            `;
          };
        </script>
      </body>
    </html>
    """
