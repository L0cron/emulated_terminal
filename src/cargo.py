

import sys
import argparse
import re
import io
import json
import tarfile
from pathlib import Path
import tomllib
from urllib.request import Request, urlopen
from urllib.error import HTTPError

HTTP_NOT_FOUND = 404

class PacketManager:
    """Build dependency graphs from crates.io or a local test graph."""
    packets = []
    command = ""
    download_repo = "https://crates.io/api/v1/crates"

    manifests = {}
    indexes = {}

    is_ascii = False
    show_order = False
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
        self.show_order = "order" in flags
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

    def print_status(self, status, text):
        """Print an aligned status label with Cargo-style terminal colors."""
        status = f"{status:>12}"
        if sys.stdout.isatty():
            status = f"\033[1;32m{status}\033[0m"
        print(f"{status} {text}", flush=True)

    def fetch(self, url):
        """Download bytes using only the Python standard library."""
        self.print_status("Fetching", url)
        headers = {"User-Agent": "emulated-terminal-cargo/1.0"}
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return response.read()
        except HTTPError as error:
            if error.code != HTTP_NOT_FOUND:
                raise
            package = url.removeprefix(self.crates_api + "/")
            package = package.removesuffix("/download").replace("/", " v")
            raise ValueError(
                f"Package {package} was not found in the repository"
            ) from error

    def __init__(self,args:list[str],flags:dict):
        """Initialize the application and apply its configuration."""
        self.packets = []
        self.command = ""
        self.unpack_args(args,flags)
        match self.command.lower():
            case "install": self.install_packets()
            case "uninstall": self.uninstall_packets()
            case "help": self.help()
            case "": print("No command specified. Need help? Run with --help")
            case _: raise ValueError(f"Unknown command: {self.command}")

    def read_test_graph(self):
        """Read a graph whose package names are uppercase Latin letters."""
        text = Path(self.download_repo).read_text(encoding="utf-8")
        graph = json.loads(text)
        if not isinstance(graph, dict):
            raise ValueError("Test graph must be a JSON object")
        for name, dependencies in graph.items():
            if not re.fullmatch(r"[A-Z]+", name):
                raise ValueError(f"Invalid test package name: {name}")
            if not isinstance(dependencies, list):
                raise ValueError(f"Dependencies of {name} must be a list")
            for dependency in dependencies:
                if not isinstance(dependency, str) or dependency not in graph:
                    raise ValueError(f"Unknown dependency of {name}")
        self.indexes = graph

    def is_crates_mode(self) -> bool:
        """Return whether the selected source is a crates API."""
        return self.mode.lower() in ("crates", "crates.io")

    def latest_crates_version(self, package: str) -> str:
        """Read the latest stable release from crates.io."""
        data = json.loads(self.fetch(f"{self.crates_api}/{package}"))
        crate = data["crate"]
        return crate["max_stable_version"] or crate["max_version"]

    def version_key(self, version):
        """Order numeric versions and prereleases, ignoring build metadata."""
        release, _, pre = version.split("+", 1)[0].partition("-")
        numbers = tuple(map(int, release.split(".")))
        numbers += (0,) * (3 - len(numbers))
        suffix = tuple((0, int(p)) if p.isdecimal() else (1, p)
                       for p in pre.split(".")) if pre else ((2, ""),)
        return numbers, suffix

    def select_version(self, package, requirement):
        """Choose the newest non-yanked release matching a Cargo range."""
        if not self.is_crates_mode():
            return ""
        if package not in self.versions:
            data = json.loads(self.fetch(f"{self.crates_api}/{package}"))
            releases = [v["num"] for v in data["versions"]
                        if not v["yanked"]]
            self.versions[package] = sorted(
                releases, key=self.version_key, reverse=True)
        for version in self.versions[package]:
            if self.matches_version(version, requirement):
                return version
        raise ValueError(f"No matching version: {package} {requirement}")

    def matches_version(self, version, requirement):
        """Match comma-separated Cargo comparators and prerelease rules."""
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError("Invalid dependency version requirement")
        clauses = requirement.split(",")
        key = self.version_key(version)
        if "-" in version.split("+", 1)[0]:
            prereleases = re.findall(r"\d+\.\d+\.\d+-[\w.-]+", requirement)
            if not any(self.version_key(v)[0] == key[0] for v in prereleases):
                return False
        return all(self.matches_clause(key, clause.strip())
                   for clause in clauses)

    def matches_clause(self, key, clause):
        """Compare one exact, wildcard, caret, tilde or inequality range."""
        match = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?\s*([\w.*+-]+)", clause)
        if not match:
            raise ValueError(f"Invalid Cargo version range: {clause}")
        operator, text = match.groups()
        if text in ("*", "x", "X"):
            return True
        wildcard = re.search(r"\.[*xX]", text)
        if wildcard:
            text = text[:wildcard.start()]
            operator = "="
        lower = self.version_key(text)
        parts = text.split("-", 1)[0].split("+", 1)[0].split(".")
        upper = self.version_upper(lower[0], len(parts), operator)
        complete = len(parts) == len(lower[0])
        comparisons = {
            ">=": key >= lower,
            "<": key < lower,
            ">": key > lower if complete else key >= upper,
            "<=": key <= lower if complete else key < upper,
            "=": key == lower if complete else lower <= key < upper,
        }
        return comparisons.get(operator, lower <= key < upper)

    def version_upper(self, numbers, count, operator):
        """Find the exclusive upper bound of a compatible version range."""
        index = count - 1
        if operator in (None, "^", "~"):
            index = min(1, count - 1)
            if operator != "~":
                index = next((i for i in range(count) if numbers[i]),
                             count - 1)
        upper = list(numbers)
        upper[index] += 1
        upper[index + 1:] = [0] * (len(upper) - index - 1)
        return tuple(upper), ((2, ""),)

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

    def direct_dependencies(self, cargo: dict) -> list[tuple]:
        """Read declared dependencies; load order excludes development tools."""
        tables = [cargo]
        targets = cargo.get("target", {})
        if not isinstance(targets, dict):
            raise ValueError("Cargo target must be a table")
        tables.extend(targets.values())
        names = set()
        kinds = ["dependencies", "build-dependencies"]
        if not self.show_order:
            kinds.append("dev-dependencies")
        for table in tables:
            if not isinstance(table, dict):
                raise ValueError("Cargo target entry must be a table")
            for kind in kinds:
                names.update(self.dependency_specs(table.get(kind, {})))
        return sorted(names)

    def dependency_specs(self, dependencies):
        """Read package names and Cargo version requirements."""
        if not isinstance(dependencies, dict):
            raise ValueError("Cargo dependencies must be a table")
        names = []
        for alias, value in dependencies.items():
            if isinstance(value, str):
                names.append((alias, value))
            elif isinstance(value, dict):
                name = value.get("package", alias)
                if not isinstance(name, str) or not name:
                    raise ValueError("Invalid dependency package name")
                requirement = value.get("version", "*")
                if not isinstance(requirement, str):
                    raise ValueError(f"Invalid version requirement: {name}")
                names.append((name, requirement))
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
        """Build a dependency graph using recursive depth-first search."""
        if not self.packets:
            raise ValueError("Specify at least one package")
        requested = [self.requested_package(p) for p in self.packets]
        names = [f"{p} v{v}" if v else p for p, v in requested]
        self.print_status("Install:", ", ".join(names))
        self.graph = {}
        self.depths = {}
        self.active = set()
        self.versions = {}
        self.manifests = {}
        self.dependency_counts = {}
        self.roots = []
        if self.is_crates_mode():
            self.print_status("Updating", "repository metadata")
        else:
            self.read_test_graph()
        for package, version in requested:
            if self.is_filtered(package):
                continue
            version = self.root_version(package, version)
            self.roots.append((package, version))
            self.visit(package, version, 0)
        if self.show_order:
            self.print_load_order()
        self.print_graph()

    def print_load_order(self):
        """Print every package after its dependencies, without duplicates."""
        order = []
        visited = set()
        active = set()
        for root in self.roots:
            self.order_visit(root, visited, active, order)
        title = "Load order"
        if self.max_deps >= 0:
            title += f" (within depth {self.max_deps})"
        print(title + ":")
        for number, (package, version) in enumerate(order, 1):
            name = f"{package} v{version}" if version else package
            print(f"    {number}. {name}")

    def order_visit(self, node, visited, active, order):
        """Use recursive DFS postorder; a cycle has no valid load order."""
        if node in active:
            raise ValueError(f"Cannot determine load order: cycle at {node[0]}")
        if node in visited:
            return
        active.add(node)
        for dependency in self.graph[node]:
            self.order_visit(dependency, visited, active, order)
        active.remove(node)
        visited.add(node)
        order.append(node)

    def requested_package(self, text):
        """Read a package request and reject conflicting exact versions."""
        package, version = self.split_packet(text)
        if version and self.version and version != self.version:
            raise ValueError("Conflicting package versions")
        return package, version or self.version

    def root_version(self, package, version):
        """Select a root release or validate its test-graph entry."""
        if self.is_crates_mode():
            return version or self.latest_crates_version(package)
        if package not in self.indexes:
            raise ValueError(f"Package not found: {package}")
        return ""

    def is_filtered(self, package):
        """Check whether a package contains the excluded substring."""
        return bool(self.test_filter) and self.test_filter in package

    def visit(self, package, version, depth):
        """Visit dependencies recursively, retaining edges that form cycles."""
        node = (package, version)
        self.graph.setdefault(node, [])
        if node in self.active:
            return
        if node in self.depths and self.depths[node] <= depth:
            return
        self.depths[node] = depth
        at_limit = self.max_deps >= 0 and depth >= self.max_deps
        if at_limit and not self.is_ascii:
            return
        dependencies = self.package_dependencies(node)
        self.dependency_counts[node] = len(dict(dependencies))
        if at_limit:
            return
        self.active.add(node)
        for dependency, requirement in dependencies:
            selected = self.select_version(dependency, requirement)
            child = (dependency, selected)
            if child not in self.graph[node]:
                self.graph[node].append(child)
            self.visit(dependency, selected, depth + 1)
        self.active.remove(node)

    def package_dependencies(self, node):
        """Read each visited manifest once; test graphs need no downloads."""
        package, version = node
        if not self.is_crates_mode():
            dependencies = [(name, "") for name in self.indexes[package]]
        else:
            if node not in self.manifests:
                cargo = self.read_crates_cargo(package, version)
                self.validate_package(cargo, package, version)
                self.manifests[node] = self.direct_dependencies(cargo)
            dependencies = self.manifests[node]
        return [(name, requirement) for name, requirement in dependencies
                if not self.is_filtered(name)]

    def print_graph(self):
        """Save and print each root's PlantUML graph and optional ASCII tree."""
        for root in self.roots:
            nodes = {}
            edges = set()
            self.collect_diagram(root, 0, nodes, edges)
            text = self.plantuml(nodes, edges)
            output = Path(__file__).resolve().parent / f"{root[0]}.puml"
            output.write_text(text, encoding="utf-8")
            print(text, end="")
            self.print_status("Saved", str(output.resolve()))
            if self.is_ascii:
                shown = {}
                print(f"ASCII Graph for packet: {root[0]}")
                self.print_ascii(root, "", set(), shown, 0)
                print(f"Dependencies: {len(shown) - 1}")

    def collect_diagram(self, node, depth, nodes, edges):
        """Collect one root's nodes and edges within its depth limit."""
        if node in nodes and nodes[node] <= depth:
            return
        nodes[node] = depth
        if self.max_deps >= 0 and depth >= self.max_deps:
            return
        for dependency in self.graph[node]:
            edges.add((node, dependency))
            self.collect_diagram(dependency, depth + 1, nodes, edges)

    def plantuml(self, nodes, edges):
        """Describe versioned packages as components with dependency arrows."""
        aliases = {node: f"p{i}" for i, node in enumerate(nodes)}
        lines = ["@startuml"]
        for (package, version), alias in aliases.items():
            name = f"{package} v{version}" if version else package
            lines.append(f'component "{name}" as {alias}')
        for source, target in sorted(edges):
            lines.append(f"{aliases[source]} --> {aliases[target]}")
        lines.append("@enduml")
        return "\n".join(lines) + "\n"

    def print_ascii(self, node, prefix, path, shown, depth, last=True):
        """Print nested branches, marking cycles and repeated dependencies."""
        package, version = node
        name = f"{package} v{version}" if version else package
        branch = "└── " if last else "├── "
        line = prefix + (branch if depth else "") + name
        suffix = self.ascii_suffix(node, path, shown, depth)
        shown[node] = min(depth, shown.get(node, depth))
        if suffix is not None:
            print(line + suffix)
            return
        print(line)
        path.add(node)
        indent = "    " if last else "│   "
        child_prefix = prefix + (indent if depth else "")
        children = self.graph[node]
        for child in children:
            self.print_ascii(child, child_prefix, path, shown, depth + 1,
                             child == children[-1])
        path.remove(node)

    def ascii_suffix(self, node, path, shown, depth):
        """Describe a branch that should not be expanded further."""
        if node in path:
            return " (cycle)"
        if self.max_deps >= 0 and depth >= self.max_deps:
            count = self.dependency_counts.get(node, 0)
            return f" (+{count} dependencies)" if count else ""
        if node in shown and shown[node] <= depth:
            return " (already shown)"
        return None

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
        print("\n  Cargo manual\n")
        print("\t  cargo [COMMAND] [PACKETS] (OPTIONAL FLAGS)\n")
        print("\tCommands:")
        print("\tinstall \t- builds the dependency graph")
        print("\t          prints PlantUML and saves <package>.puml")
        print("\tuninstall \t- reserved for a later stage")
        print("\thelp \t\t- print this menu")
        print("\t--mode test|crates \t- choose the data source")
        print("\t--version VERSION \t- choose a package version")
        print("\t--where URL|PATH \t- crates API URL or test graph.json")
        print("\t--max_deps full|N \t- maximum depth (root is 0)")
        print("\t--filter TEXT \t- skip names containing TEXT")
        print("\t--ascii \t- print dependencies as an ASCII tree")
        print("\t--order \t- print dependencies before their dependents")
        print("\t          crates mode excludes dev-dependencies")
        print()


def parse_cli(argv=None):
    """Parse the existing CLI with explicit option arity."""
    parser = argparse.ArgumentParser(
        prog="cargo", description="Cargo dependency analyzer")
    parser.add_argument("command", choices=("install", "uninstall", "help"))
    parser.add_argument("packets", nargs="*")
    parser.add_argument("--where", default=PacketManager.download_repo)
    parser.add_argument("--mode", choices=("test", "crates", "crates.io"),
                        default="crates")
    parser.add_argument("--version", default="")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--order", action="store_true")
    parser.add_argument("--max_deps", default="full")
    parser.add_argument("--filter", default="")
    options = vars(parser.parse_args(argv))
    depth = options["max_deps"]
    if depth != "full" and not depth.isdecimal():
        parser.error("--max_deps must be full or a nonnegative integer")
    args = ["cargo", options.pop("command"), *options.pop("packets")]
    for flag in ("ascii", "order"):
        if not options[flag]:
            del options[flag]
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
