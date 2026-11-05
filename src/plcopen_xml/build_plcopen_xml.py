"""Build PLCopen interchange XML from the maintained IEC 61131-3 ST sources."""

from __future__ import annotations

import re
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PLCOPEN = "http://www.plcopen.org/xml/tc6_0201"
XHTML = "http://www.w3.org/1999/xhtml"
ET.register_namespace("", PLCOPEN)
ET.register_namespace("xhtml", XHTML)

TYPE_TAGS = {"BOOL": "BOOL", "REAL": "REAL", "INT": "INT"}
POUS = (
    ROOT / "src" / "iec61131" / "FB_QTA_Controller.st",
    ROOT / "src" / "iec61131" / "FB_Level_PID_Controller.st",
)


def parse_declarations(section: str) -> list[tuple[str, str, str | None, str]]:
    variables = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith("(*") or ":" not in line or ";" not in line:
            continue
        match = re.match(
            r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>BOOL|REAL|INT)"
            r"(?:\s*:=\s*(?P<value>[^;]+))?\s*;"
            r"(?:\s*\(\*\s*(?P<comment>.*?)\s*\*\))?",
            line,
        )
        if match:
            variables.append(
                (match.group("name"), match.group("type"), match.group("value"), match.group("comment") or "")
            )
    return variables


def source_pou(path: Path) -> tuple[str, dict[str, list[tuple[str, str, str | None, str]]], str]:
    text = path.read_text(encoding="utf-8")
    name_match = re.search(r"FUNCTION_BLOCK\s+(\w+)", text)
    if not name_match or "END_FUNCTION_BLOCK" not in text:
        raise ValueError(f"Not a function block source: {path}")
    sections = {}
    for section_name in ("VAR_INPUT", "VAR_OUTPUT", "VAR"):
        match = re.search(rf"\b{section_name}\b(.*?)\bEND_VAR\b", text, re.S)
        if not match:
            raise ValueError(f"Missing {section_name} section in {path}")
        sections[section_name] = parse_declarations(match.group(1))
    body = text.rsplit("END_VAR", 1)[1].split("END_FUNCTION_BLOCK", 1)[0].strip()
    if not body:
        raise ValueError(f"Empty implementation body in {path}")
    return name_match.group(1), sections, body


def add_variable(parent: ET.Element, spec: tuple[str, str, str | None, str]) -> None:
    name, base_type, initial, comment = spec
    variable = ET.SubElement(parent, "variable", {"name": name})
    type_node = ET.SubElement(variable, "type")
    ET.SubElement(type_node, TYPE_TAGS[base_type])
    if initial:
        initial_node = ET.SubElement(variable, "initialValue")
        ET.SubElement(initial_node, "simpleValue", {"value": initial.strip()})
    if comment:
        documentation = ET.SubElement(variable, "documentation")
        ET.SubElement(documentation, f"{{{XHTML}}}p").text = comment


def build() -> Path:
    root = ET.Element(f"{{{PLCOPEN}}}project")
    ET.SubElement(
        root,
        f"{{{PLCOPEN}}}fileHeader",
        {
            "companyName": "Rogério Eduardo Moreira Menegueli",
            "productName": "Academic Industrial Automation Examples",
            "productVersion": "1.1",
            "creationDateTime": "2026-11-05T00:00:00",
        },
    )
    content = ET.SubElement(root, f"{{{PLCOPEN}}}contentHeader", {"name": "Industrial_QTA_and_PID_PLC"})
    coordinates = ET.SubElement(content, f"{{{PLCOPEN}}}coordinateInfo")
    for language in ("fbd", "ld", "sfc"):
        item = ET.SubElement(coordinates, f"{{{PLCOPEN}}}{language}")
        ET.SubElement(item, f"{{{PLCOPEN}}}scaling", {"x": "1", "y": "1"})

    types = ET.SubElement(root, f"{{{PLCOPEN}}}types")
    ET.SubElement(types, f"{{{PLCOPEN}}}dataTypes")
    pous = ET.SubElement(types, f"{{{PLCOPEN}}}pous")
    for path in POUS:
        name, sections, body = source_pou(path)
        pou = ET.SubElement(pous, f"{{{PLCOPEN}}}pou", {"name": name, "pouType": "functionBlock"})
        interface = ET.SubElement(pou, f"{{{PLCOPEN}}}interface")
        for section_name, tag in (("VAR_INPUT", "inputVars"), ("VAR_OUTPUT", "outputVars"), ("VAR", "localVars")):
            parent = ET.SubElement(interface, f"{{{PLCOPEN}}}{tag}")
            for spec in sections[section_name]:
                add_variable(parent, spec)
        body_node = ET.SubElement(pou, f"{{{PLCOPEN}}}body")
        st = ET.SubElement(body_node, f"{{{PLCOPEN}}}ST")
        paragraph = ET.SubElement(st, f"{{{XHTML}}}p")
        paragraph.text = body

    instances = ET.SubElement(root, f"{{{PLCOPEN}}}instances")
    ET.SubElement(instances, f"{{{PLCOPEN}}}configurations")
    ET.indent(root, space="  ")
    output = ROOT / "src" / "plcopen_xml" / "Industrial_QTA_and_PID_PLC.xml"
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return output


if __name__ == "__main__":
    result = build()
    print(f"Generated {result.relative_to(ROOT)}")
