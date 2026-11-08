

import sys
import argparse
import re
import io
import json
import tarfile
from pathlib import Path
import tomllib
from urllib.request import Request, urlopen

class PacketManager:
    """Read direct Cargo dependencies from crates.io or a test repository."""
    packets = []
    command = ""
    download_repo = "https://crates.io/api/v1/crates"

    manifests = {}
    indexes = {}

    is_ascii = False
    mode = "crates"

    max_deps = -1
    version = ""
    test_filter = ""
    crates_api = "https://crates.io/api/v1/crates"

    def unpack_args(self,args:list[str],flags:dict):
        """Read options without modifying the caller's argument list."""
        args = args[1:]
        if args:
            self.command = args[0]
            self.packets.extend(args[1:])
        self.download_repo = flags.get("where", self.download_repo)
        self.mode = flags.get("mode", self.mode)
        self.version = flags.get("version", self.version)
        self.test_filter = flags.get("filter", self.test_filter)
        self.is_ascii = "ascii" in flags
        depth = str(flags.get("max_deps", "full"))
        if depth != "full" and not depth.isdecimal():
            raise ValueError("Maximum depth must be full or nonnegative")
        self.max_deps = -1 if depth == "full" else int(depth)
        self.validate_options()

    def validate_options(self):
        """Reject invalid configuration before accessing the repository."""
        if self.mode not in ("test", "crates", "crates.io"):
            raise ValueError("Mode must be test or crates")
        if not self.download_repo:
            raise ValueError("Repository must not be empty")
        if self.is_crates_mode():
            if not self.download_repo.startswith(("http://", "https://")):
                raise ValueError("Crates repository must be an HTTP(S) URL")
            self.crates_api = self.download_repo.rstrip("/")
            if self.crates_api == "https://crates.io":
                self.crates_api += "/api/v1/crates"
        if self.version:
            self.validate_version(self.version)

    def validate_version(self, version):
        """Accept exact Cargo versions, including prereleases."""
        pattern = r"\d+\.\d+(?:\.\d+)?(?:-[\w.-]+)?(?:\+[\w.-]+)?"
        if not re.fullmatch(pattern, version, flags=re.ASCII):
            raise ValueError(f"Invalid version: {version}")

    def fetch(self, url):
        """Download bytes using only the Python standard library."""
        headers = {"User-Agent": "emulated-terminal-pacman/1.0"}
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            return response.read()

    def __init__(self,args:list[str],flags:dict):
        """Initialize the application and apply its configuration."""
        self.packets = []
        self.command = ""
        self.unpack_args(args,flags)
        print("Packet manager v1.0")
        match self.command.lower():
            case "install": self.install_packets()
            case "uninstall": self.uninstall_packets()
            case "help": self.help()
            case "": print("No command specified. Need help? Run with --help")
            case _: raise ValueError(f"Unknown command: {self.command}")

    def sort_versions(self, packet: dict) -> list[str]:
        """Sort numeric versions from a package description."""
        versions_dict = next(iter(packet.values()))
        version_strings = list(versions_dict.keys())
        sorted_versions = sorted(
            version_strings,
            key=lambda v_str: [int(part) for part in v_str.split(".")]
        )
        return sorted_versions

    def update_indexes(self):
        """Read the package index from a URL or local file."""
        print(f"    Updating {self.download_repo} index")
        if self.download_repo.startswith(("http://", "https://")):
            self.indexes = json.loads(self.fetch(self.download_repo))
        else:
            index_path = Path(self.download_repo)
            self.indexes = json.loads(index_path.read_text(encoding="utf-8"))
        print(f"    Updated indexes successfully")

    def is_crates_mode(self) -> bool:
        """Return whether the selected source is a crates API."""
        return self.mode.lower() in ("crates", "crates.io")

    def latest_test_version(self, package: str) -> str:
        """Choose the highest version in the test index."""
        self.update_indexes()
        versions = self.indexes.get(package)
        if not isinstance(versions, list) or not versions:
            raise ValueError(f"Package not found: {package}")
        return sorted(versions, key=self.version_key)[-1]

    def version_key(self, version: str) -> list[int]:
        """Convert a numeric version to a sortable list."""
        try:
            return [int(part) for part in version.split(".")]
        except ValueError as error:
            raise ValueError(f"Invalid version: {version}") from error

    def latest_crates_version(self, package: str) -> str:
        """Read the latest stable release from crates.io."""
        data = json.loads(self.fetch(f"{self.crates_api}/{package}"))
        crate = data["crate"]
        return crate["max_stable_version"] or crate["max_version"]

    def cargo_url(self, package: str, version: str) -> str:
        """Locate the manifest in the custom repository."""
        if self.download_repo.endswith("Cargo.toml"):
            return self.download_repo
        if self.download_repo.startswith(("http://", "https://")):
            base = self.download_repo.rsplit("/", 1)[0] + "/packets/"
        else:
            return str(Path(self.download_repo).parent / "packets" /
                       package / version / "Cargo.toml")
        return base + f"{package}/{version}/Cargo.toml"

    def read_test_cargo(self, package: str, version: str) -> dict:
        """Read a Cargo manifest from the custom repository."""
        location = self.cargo_url(package, version)
        if location.startswith(("http://", "https://")):
            return tomllib.loads(self.fetch(location).decode("utf-8"))
        return tomllib.loads(Path(location).read_text(encoding="utf-8"))

    def read_crates_cargo(self, package: str, version: str) -> dict:
        """Read the root Cargo manifest from an in-memory archive."""
        url = f"{self.crates_api}/{package}/{version}/download"
        data = io.BytesIO(self.fetch(url))
        with tarfile.open(fileobj=data, mode="r:gz") as archive:
            name = f"{package}-{version}/Cargo.toml"
            try:
                member = archive.getmember(name)
            except KeyError as error:
                raise ValueError("Cargo.toml not found in archive") from error
            if not member.isfile():
                raise ValueError("Cargo.toml must be a regular file")
            with archive.extractfile(member) as content:
                return tomllib.loads(content.read().decode("utf-8"))

    def read_cargo(self, package: str, version: str) -> dict:
        """Read a manifest using the selected repository mode."""
        if self.is_crates_mode():
            return self.read_crates_cargo(package, version)
        return self.read_test_cargo(package, version)

    def direct_dependencies(self, cargo: dict) -> list[str]:
        """Collect all declared kinds, platforms and optional dependencies."""
        tables = [cargo]
        targets = cargo.get("target", {})
        if not isinstance(targets, dict):
            raise ValueError("Cargo target must be a table")
        tables.extend(targets.values())
        names = set()
        for table in tables:
            if not isinstance(table, dict):
                raise ValueError("Cargo target entry must be a table")
            for kind in ("dependencies", "build-dependencies",
                         "dev-dependencies"):
                names.update(self.dependency_names(table.get(kind, {})))
        return sorted(names)

    def dependency_names(self, dependencies):
        """Resolve Cargo aliases to the published package names."""
        if not isinstance(dependencies, dict):
            raise ValueError("Cargo dependencies must be a table")
        names = []
        for alias, value in dependencies.items():
            if isinstance(value, str):
                names.append(alias)
            elif isinstance(value, dict):
                name = value.get("package", alias)
                if not isinstance(name, str) or not name:
                    raise ValueError("Invalid dependency package name")
                names.append(name)
            else:
                raise ValueError(f"Invalid dependency: {alias}")
        return names

    def split_packet(self,packet_with_version:str):
        """Parse name, name[version] or name:version."""
        pattern = r"([A-Za-z0-9_-]+)(?:\[([^\]]+)\]|:([^:]+))?"
        match = re.fullmatch(pattern, packet_with_version)
        if match is None:
            raise ValueError("Invalid package name or version syntax")
        packet, bracket, colon = match.groups()
        version = bracket or colon
        if version:
            self.validate_version(version)
        return packet, version


    def install_packets(self):
        """Print direct dependencies of the requested release."""
        if len(self.packets) != 1:
            raise ValueError("Specify exactly one package")
        package, requested = self.split_packet(self.packets[0])
        if requested and self.version and requested != self.version:
            raise ValueError("Conflicting package versions")
        selected = requested or self.version or self.latest_version(package)
        print(f"    Reading {package} version {selected}")
        cargo = self.read_cargo(package, selected)
        self.validate_package(cargo, package, selected)
        dependencies = self.direct_dependencies(cargo)
        print(f"    Direct dependencies for {package} {selected}:")
        for dependency in dependencies:
            print(f"      {dependency}")
        if not dependencies:
            print("      (none)")

    def latest_version(self, package):
        """Choose a version from the selected repository."""
        if self.is_crates_mode():
            return self.latest_crates_version(package)
        return self.latest_test_version(package)

    def validate_package(self, cargo, package, version):
        """Check that the manifest belongs to the requested release."""
        metadata = cargo.get("package", {})
        if not isinstance(metadata, dict):
            raise ValueError("Cargo package must be a table")
        if (metadata.get("name"), metadata.get("version")) != (
                package, version):
            raise ValueError("Cargo.toml package name or version mismatch")

    def uninstall_packets(self):
        """Report that this analyzer does not uninstall packages."""
        raise ValueError("Uninstall is not supported by this analyzer")

    def help(self):
        """Print supported commands and configuration options."""
        print("\n  Pacman manual\n")
        print("\t  pacman [COMMAND] [PACKETS] (OPTIONAL FLAGS)\n")
        print("\tCommands:")
        print("\tinstall \t- reads direct dependencies of a package")
        print("\tuninstall \t- reserved for a later stage")
        print("\thelp \t\t- print this menu")
        print("\t--mode test|crates \t- choose the data source")
        print("\t--version VERSION \t- choose a package version")
        print("\t--where URL|PATH \t- crates API URL or test index.json")
        print("\t--ascii, --max_deps, --filter: reserved for later stages")
        print()


def parse_cli(argv=None):
    """Parse the existing CLI with explicit option arity."""
    parser = argparse.ArgumentParser(description="Cargo dependency analyzer")
    parser.add_argument("command", choices=("install", "uninstall", "help"))
    parser.add_argument("packets", nargs="*")
    parser.add_argument("--where", default=PacketManager.download_repo)
    parser.add_argument("--mode", choices=("test", "crates", "crates.io"),
                        default="crates")
    parser.add_argument("--version", default="")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--max_deps", default="full")
    parser.add_argument("--filter", default="")
    options = vars(parser.parse_args(argv))
    depth = options["max_deps"]
    if depth != "full" and not depth.isdecimal():
        parser.error("--max_deps must be full or a nonnegative integer")
    args = ["pacman", options.pop("command"), *options.pop("packets")]
    if not options.pop("ascii"):
        return args, options
    options["ascii"] = ""
    return args, options


def main(argv=None):
    """Run the analyzer and report expected input and download errors."""
    args, flags = parse_cli(argv)
    try:
        PacketManager(args, flags)
    except (ValueError, OSError, tarfile.TarError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
