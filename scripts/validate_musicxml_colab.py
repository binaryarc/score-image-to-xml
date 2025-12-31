from google.colab import files
import xml.etree.ElementTree as ET
import os

print("📤 MusicXML 파일을 업로드하세요:")
uploaded = files.upload()

filename = list(uploaded.keys())[0]

print("\n" + "=" * 60)
print("📊 파일 분석")
print("=" * 60)

file_size = os.path.getsize(filename)
print(f"파일명: {filename}")
print(f"크기: {file_size:,} bytes ({file_size/1024:.1f} KB)")

print("\n" + "=" * 60)
print("📄 파일 내용 (처음 500자)")
print("=" * 60)
with open(filename, "r", encoding="utf-8") as handle:
    content = handle.read()
    print(content[:500])

print("\n" + "=" * 60)
print("🔍 XML 검증")
print("=" * 60)
try:
    tree = ET.parse(filename)
    root = tree.getroot()
    print("✅ XML 형식 유효")
    print(f"루트 요소: {root.tag}")

    if root.tag.startswith("{"):
        namespace = root.tag[1 : root.tag.index("}")]
        print(f"네임스페이스: {namespace}")

    version = root.get("version")
    if version:
        print(f"MusicXML 버전: {version}")

    parts = root.findall('.//*[local-name()="part"]')
    print(f"파트 수: {len(parts)}")

    measures = root.findall('.//*[local-name()="measure"]')
    print(f"마디 수: {len(measures)}")

except ET.ParseError as exc:
    print(f"❌ XML 파싱 오류: {exc}")
except Exception as exc:
    print(f"❌ 오류: {exc}")

print("\n" + "=" * 60)
print("🎵 MusicXML 구조 확인")
print("=" * 60)
with open(filename, "r", encoding="utf-8") as handle:
    content = handle.read()

    checks = {
        "score-partwise": "score-partwise" in content,
        "part-list": "part-list" in content,
        "measure": "measure" in content,
        "note": "note" in content,
        "pitch": "pitch" in content,
    }

    for element, found in checks.items():
        status = "✅" if found else "❌"
        print(f"{status} {element}")
