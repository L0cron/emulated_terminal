
import sys
from pathlib import Path
import json
import random
import os

packets_dir = Path(__file__).resolve().parent / "packets"

def manifest_version(packet_name:str, version:str):
    """Write a file listing for a custom package release."""
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
    with (p / "manifest.json").open("w", encoding="utf-8") as manifest:
        json.dump(data, manifest, ensure_ascii=False, indent=4)
    print(f"    [Done] Added {added} files")

def add_random_to_packet(packet_name:str,ver:str,c=1):
    """Generate local binary samples for a custom package."""
    global packets_dir
    p = Path(packets_dir/packet_name/ver)
    max_file_bytes = 1024 * 50
    for i in range(c):
        random_size = random.randint(1024, max_file_bytes)
        file_path = p / f"junk{i}.bin"
        file_path.write_bytes(os.urandom(random_size))

def make_packet(packet_name:str, base_version: str):
    """Create a package directory with a Cargo manifest."""
    global packets_dir
    print(f"Creating packet {packet_name} ({base_version})...")
    p = Path(packets_dir / packet_name / base_version)
    p.mkdir(exist_ok=True,parents=True)
    cargo = (
        "[package]\n"
        f'name = "{packet_name}"\n'
        f'version = "{base_version}"\n\n'
        "[dependencies]\n"
    )
    (p / "Cargo.toml").write_text(cargo, encoding="utf-8")
    print(f"Created {packet_name} ({base_version})")

def index_version(packet_name:str, version:str) -> dict|None:
    """Check whether the custom release directory exists."""
    global packets_dir
    p = Path(packets_dir / packet_name / version)
    if not p.exists():
        print(f"[ERR] {packet_name}/{version} does not exist...")
        return None

def random_versions(count = 10) -> list[str]:
    """Generate distinct numeric version strings."""
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
    """List release directories and generate their manifests."""
    global packets_dir
    print(f"  - Indexing {packet_name}")
    packet_path = Path(packets_dir / packet_name)
    vers = []

    for ver in packet_path.iterdir():
        if ver.is_dir():
            manifest_version(packet_name,ver.name)
            vers.append(ver.name)
            print(f"    Version {ver.name} indexed")
    return vers

def random_dependencies(name:str, ver:str):
    """Choose random dependencies for a custom release."""
    global packets_dir
    packets_path = Path(packets_dir)
    p = packets_path / name / ver
    cargo_file = p / "Cargo.toml"
    all_packets = [d for d in packets_path.iterdir()
                   if d.is_dir() and d.name < name]
    if not all_packets:
        write_cargo(name, ver, [])
        return
    count = random.randint(0, min(7, len(all_packets)))
    dep = random.sample(all_packets, count)
    lines = []
    for d in dep:
        vers = [v for v in d.iterdir() if v.is_dir()]
        if not vers:
            continue
        v = random.choice(vers)

        if random.randint(0, 1) == 1:
            lines.append(f'{d.name} = ">={v.name}"\n')
        else:
            lines.append(f'{d.name} = "={v.name}"\n')
    write_cargo(name, ver, lines)
    print(f"Done for {name} v{ver}. Added random deps")

def write_cargo(name: str, version: str, dependencies: list[str]):
    """Write package metadata and dependencies as Cargo TOML."""
    cargo = (
        f'[package]\nname = "{name}"\nversion = "{version}"\n\n'
        "[dependencies]\n" + "".join(dependencies)
    )
    path = packets_dir / name / version / "Cargo.toml"
    path.write_text(cargo, encoding="utf-8")


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
            with (packets_dir.parent / "index.json").open(
                "w", encoding="utf-8"
            ) as out:
                json.dump(packets, out, ensure_ascii=False, indent=4)
            print("[Done] All packets indexed.")
        case "update":
            pass
        case "create":
            name = input("Specify packet name > ")
            base_ver = input("Specify basic packet version > ")
            make_packet(name, base_ver)

            print("Done. TIP:")
            print("Added Cargo.toml file. List dependencies in "\
            "[dependencies] using Cargo version requirements.")
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
