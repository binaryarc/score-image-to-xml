import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def validate_musicxml_quality(xml_data: bytes) -> float:
    """MusicXML 품질 점수 (0-100)."""
    try:
        root = ET.fromstring(xml_data)

        measures = root.findall(".//{*}measure")
        notes = root.findall(".//{*}note")
        parts = root.findall(".//{*}part")

        score = 0.0

        if len(parts) > 0:
            score += 10
        if len(measures) >= 2:
            score += 15
        if len(notes) >= 5:
            score += 15

        if len(measures) > 0:
            notes_per_measure = len(notes) / len(measures)
            if notes_per_measure >= 2:
                score += 30
            elif notes_per_measure >= 1:
                score += 15

        xml_str = xml_data.decode("utf-8", errors="ignore")
        if "pitch" in xml_str:
            score += 10
        if "duration" in xml_str:
            score += 10
        if "time" in xml_str:
            score += 10

        return min(100.0, score)
    except Exception:
        return 0.0


def fix_musicxml_complete(xml_data: bytes) -> bytes:
    """MusicXML 완벽 수정 - 모든 오류 해결."""
    try:
        xml_str = xml_data.decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_str)

        logger.info("🔧 Fixing MusicXML structure...")

        for part in root.findall(".//{*}part"):
            sounds = []
            for child in list(part):
                if child.tag.endswith("sound"):
                    sounds.append(child)
                    part.remove(child)

            if sounds:
                first_measure = part.find(".//{*}measure")
                if first_measure is not None:
                    for sound in sounds:
                        first_measure.insert(0, sound)
                    logger.info("✅ Moved %d sound tag(s)", len(sounds))

        for part in root.findall(".//{*}part"):
            for measure in part.findall(".//{*}measure"):
                divisions_elem = measure.find(".//{*}divisions")
                if divisions_elem is not None:
                    try:
                        divisions = int(divisions_elem.text)
                    except Exception:
                        divisions = 16
                else:
                    divisions = 16

                beats_elem = measure.find(".//{*}time/{*}beats")
                beat_type_elem = measure.find(".//{*}time/{*}beat-type")

                if beats_elem is not None and beat_type_elem is not None:
                    try:
                        beats = int(beats_elem.text)
                        beat_type = int(beat_type_elem.text)
                        expected_duration = divisions * beats * (4 / beat_type)
                    except Exception:
                        expected_duration = None
                else:
                    expected_duration = None

                actual_duration = 0
                notes = measure.findall(".//{*}note")

                for note in notes:
                    if note.find(".//{*}chord") is not None:
                        continue

                    duration_elem = note.find(".//{*}duration")
                    if duration_elem is not None:
                        try:
                            actual_duration += int(duration_elem.text)
                        except Exception:
                            pass

                if expected_duration is not None and actual_duration > 0:
                    if actual_duration < expected_duration:
                        missing_duration = int(expected_duration - actual_duration)
                        rest_note = ET.SubElement(measure, "note")
                        ET.SubElement(rest_note, "rest")
                        duration_elem = ET.SubElement(rest_note, "duration")
                        duration_elem.text = str(missing_duration)
                        ET.SubElement(rest_note, "type").text = "quarter"

                        logger.info("✅ Added rest (%d) to complete measure", missing_duration)

                    elif actual_duration > expected_duration:
                        excess = actual_duration - expected_duration
                        last_note_with_duration = None

                        for note in reversed(notes):
                            if note.find(".//{*}chord") is None:
                                duration_elem = note.find(".//{*}duration")
                                if duration_elem is not None:
                                    last_note_with_duration = duration_elem
                                    break

                        if last_note_with_duration is not None:
                            try:
                                current_dur = int(last_note_with_duration.text)
                                new_dur = max(1, current_dur - int(excess))
                                last_note_with_duration.text = str(new_dur)
                                logger.info("✅ Adjusted note duration (%d → %d)", current_dur, new_dur)
                            except Exception:
                                pass

        def remove_empty_elements(element):
            for child in list(element):
                remove_empty_elements(child)
                if len(child) == 0 and not child.text and not child.attrib:
                    element.remove(child)

        remove_empty_elements(root)

        if "version" in root.attrib:
            root.attrib["version"] = "3.1"

        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = (
            "<!DOCTYPE score-partwise PUBLIC \"-//Recordare//DTD MusicXML 3.1 Partwise//EN\" "
            "\"http://www.musicxml.org/dtds/partwise.dtd\">\n"
        )

        indent_xml(root)

        xml_str = ET.tostring(root, encoding="unicode")
        fixed_xml = xml_declaration + doctype + xml_str

        logger.info("✅ MusicXML completely fixed")
        return fixed_xml.encode("utf-8")

    except Exception as exc:
        logger.error("❌ Failed to fix MusicXML: %s", exc, exc_info=True)
        return xml_data


def indent_xml(elem, level=0):
    """XML 들여쓰기 (가독성 향상)."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
