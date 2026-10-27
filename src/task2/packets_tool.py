
import sys
from pathlib import Path
import json
import random
import os
from itertools import product

packets_dir = Path("./packets").resolve()

def manifest_version(packet_name:str, version:str):
    global packets_dir
    print(f"    Creating manifest for {packet_name} ({version})...")
    added = 0
    data = {version: []}
    p = Path(packets_dir / packet_name / version)
    for f in p.rglob("*"):
        if f.is_file():
            data[version].append({
                "file":f.name,
                "dl":str(packets_dir/packet_name/version/f.name),
                "size":str(f.stat().st_size)
            })
            added+=1
    f = open(str(p.resolve())+"\\manifest.json","w")
    json.dump(data,f,ensure_ascii=False,indent=4)
    print(f"    [Done] Added {added} files")

def add_random_to_packet(packet_name:str,ver:str,c=1):
    global packets_dir
    p = Path(packets_dir/packet_name/ver)
    KB50_BYTES = 1024 * 50
    for i in range(c):
        random_size = random.randint(1024, KB50_BYTES)
        file_path = p / f"junk{i}.bin"
        file_path.write_bytes(os.urandom(random_size))

def make_packet(packet_name:str, base_version: str):
    global packets_dir
    print(f"Creating packet {name} ({base_version})...")
    p = Path(packets_dir / packet_name / base_version)
    p.mkdir(exist_ok=True,parents=True)
    open(Path(p,"dependencies.txt"),"a").close()
    print(f"Created {packet_name} ({base_version})")

def index_version(packet_name:str, version:str) -> dict|None:
    global packets_dir
    p = Path(packets_dir / packet_name / version)
    if not p.exists():
        print(f"[ERR] {packet_name}/{version} does not exist...")
        return None

def random_versions(count = 10) -> list[str]:
    numbers = []
    if count <= 0: return []
    while len(numbers) != count:
        numbers.append(random.randint(0,count*5))
        numbers = list(set(numbers))
    vers = []
    for i in numbers:
        vers.append(f"1.{i}")
    return vers

def index_packet(packet_name:str)->dict:
    global packets_dir
    print(f"  - Indexing {p}")
    packet_path = Path(packets_dir / packet_name)
    vers = []

    for ver in packet_path.iterdir():
        if ver.is_dir():
            manifest_version(packet_name,ver.name)
            vers.append(ver.name)
            print(f"    Version {ver.name} indexed")
    return vers

def random_dependencies(name:str, ver:str):
    global packets_dir
    packets_path = Path(packets_dir)
    p = packets_path / name / ver
    
    # Открываем через pathlib (автоматически закроется и подставит правильные слэши)
    dependencies_file = p / "dependencies.txt"
    
    # 1. Получаем список ВСЕХ пакетов, но фильтруем его, чтобы избежать циклов
    # Защита: пакет может зависеть только от тех, чьё имя "меньше" его по алфавиту
    all_packets = [d for d in packets_path.iterdir() if d.is_dir() and d.name < name]

    # Если доступных пакетов нет, пишем пустой файл и выходим
    if not all_packets:
        dependencies_file.write_text("")
        return

    count = random.randint(0, min(7, len(all_packets)))
    dep = random.sample(all_packets, count)
    
    lines = []
    for d in dep:
        # Берем случайную версию выбранного пакета
        vers = [v for v in d.iterdir() if v.is_dir()]
        if not vers:
            continue
        v = random.choice(vers)
        
        # Генерируем строку манифеста
        if random.randint(0, 1) == 1:
            lines.append(f"{d.name}[>={v.name}]\n")
        else:
            lines.append(f"{d.name}[{v.name}]\n")
    dependencies_file.write_text("".join(lines), encoding="utf-8")
    print(f"Done for {name} v{ver}. Added random deps")


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("No commands specified. (index, update, create, random)")
        exit()
    arg = sys.argv[1]
    packets_dir.mkdir(exist_ok=True)
    match arg:
        case "index":
            print("Indexing all packets...")
            itdir:list[Path] = list(packets_dir.iterdir())
            print(f"- Found {len(itdir)} packets")
            packets = {}
            for p in itdir:
                packets[p.name] = index_packet(p.name)
            out = open("./index.json","w")
            json.dump(packets,out,ensure_ascii=False,indent=4)      
            print("[Done] All packets indexed.")
        case "update":
            pass
        case "create":
            name = input("Specify packet name > ")
            base_ver = input("Specify basic packet version > ")
            make_packet(name, base_ver)

            print("Done. TIP:")
            print("Added dependencies.txt file, you can list "\
            "all dependencies there. To properly specify version "\
            "follow next format: <packet>[ver]. You can also use "\
            "comparison symbols: <packet>[>=ver] or between "\
            "<packet>[ver1-ver2]")
        case "random":
            print("Info: This will create random packet")
            name = input("Select random packet name > ")

            rvers = random_versions(random.randint(3,10))
            print(f"Creating {len(rvers)} versions")
            for v in rvers:
                make_packet(name,v)
                add_random_to_packet(name,v,random.randint(2,10))
                random_dependencies(name,v)
                manifest_version(name,v)
            print("[Done] Made all random versions")

        case _:
            print("Unknown call. Exit")