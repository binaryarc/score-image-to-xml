# 악보이미지 → MusicXML 변환기

악보 이미지(스캔/촬영)를 입력으로 받아 MusicXML 파일로 변환하는 프로젝트입니다.

## 주요 기능
- 악보 이미지 입력 지원
- MusicXML 파일 출력
- 고급 전처리 및 오류 자동 수정

## 개발 환경
- Python 3.x
- 가상환경(venv) 사용

## 설치 및 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# FastAPI 실행
uvicorn main:app --reload
```

## Colab 실행
`scripts/colab_run.py`를 Colab 셀에 넣고 실행하면 ngrok 터널까지 자동으로 띄워집니다.

## Colab 검증
`scripts/validate_musicxml_colab.py`를 Colab 셀에 넣고 실행하면 MusicXML 파일을 업로드해 기본 검증을 수행합니다.

## 사용 방법
1) 변환할 악보 이미지를 준비합니다.
2) 서버 실행 후 브라우저에서 업로드합니다.
3) 출력된 MusicXML 파일을 확인합니다.

## 디렉터리 구조
- `app/`: 서비스 코드
  - `app/api.py`: FastAPI 엔드포인트
  - `app/services/`: 전처리, OEMER 실행, MusicXML 보정
  - `app/ui.py`: 업로드 페이지 템플릿
  - `app/utils/`: 유틸리티
- `legacy/`: 레거시 파일 보관

## 라이선스
필요 시 추가하세요.
