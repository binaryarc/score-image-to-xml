# 악보 이미지 → MusicXML (정확도 우선 파이프라인)

정확도를 높이기 위해 **악보 줄(staff line) 단위로 분할**한 뒤 OEMER로 각각 인식하고, 결과를 하나의 MusicXML로 병합합니다.

## 구성
- `main.py`: FastAPI 서버
- `pipeline.py`: 전처리 → 분할 → OEMER → 병합
- `scripts/colab_run.py`: Colab 실행 스크립트
- `legacy/`: 기존 코드 보관 (새 파이프라인과 무관)

## 실행 (로컬)
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## 실행 (Colab)
```bash
!git clone https://github.com/<OWNER>/<REPO>.git
%cd <REPO>
!pip install -r requirements.txt
!python scripts/colab_run.py
```

## 동작 흐름
1. 이미지 전처리(대비 강화, 이진화)
2. 악보 줄 기반 분할
3. 분할된 이미지별 OEMER 실행
4. MusicXML 병합 및 키 시그니처 보정
