import base64
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


def build_vfs_xml(target_dir_path, output_xml_path):
    target_path = Path(target_dir_path).resolve()
    root = ET.Element("vfs", name=target_path.name)
    vfs_root_dir = ET.SubElement(root, "dir", name="/")

    dir_elements = {target_path: vfs_root_dir}

    for path in sorted(target_path.rglob("*")):
        if path.is_dir():
            parent_element = dir_elements[path.parent]
            subdir_element = ET.SubElement(
                parent_element, "dir", name=path.name
            )
            dir_elements[path] = subdir_element
        elif path.is_file():
            parent_element = dir_elements[path.parent]
            file_bytes = path.read_bytes()
            base64_content = base64.b64encode(file_bytes).decode("utf-8")
            ET.SubElement(
                parent_element, "file", name=path.name, content=base64_content
            )

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed_str = minidom.parseString(xml_str)
    pretty_xml = parsed_str.toprettyxml(indent="    ", encoding="utf-8")

    Path(output_xml_path).write_bytes(pretty_xml)


import sys
if __name__ == "__main__":
    args = sys.argv
    if len(args) == 1:
        print("ты ниче не вписал олух")
        exit()
    path = Path(args[1])
    build_vfs_xml(path,path.name+".xml")
