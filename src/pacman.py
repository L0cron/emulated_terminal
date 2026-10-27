

import sys
import re
import requests

class Packet_manager():
    packets = []
    command = ""
    download_repo = "https://raw.githubusercontent.com/L0cron/emulated_terminal/main/src/task2/index.json"

    manifests = {}
    indexes = {}

    is_ASCII = False
    mode = "?"

    max_deps = -1

    def unpack_args(self,args:list[str],flags:dict):
        """
        # Important variables notice:
        * packet_names [REQUIRED] - Installs specified packet by name
            to specify download version place a colon with a version
            e.g. python:3.14.0

        # Flags:
        * --where <LINK> [OPTIONAL] - Can specify from where to download
            the packet (GitHub repo)
        * --mode <MODE> - Idk
        * --ascii - Print download dependencies in ASCII tree
        * --max_deps <full | 0...999+> - Specified max recursive length
            for dependencies analysis
        """
        args.pop(0)
        if len(args) > 0:
            self.command = args[0]
            for i in args[1:]:
                self.packets.append(i)
        for flag in flags.items():
            name,value = map(str, flag)
            match name.lower():
                case "where": self.download_repo = value
                case "ascii": self.is_ASCII = True
                case "mode": self.mode = value
                case "max_deps": self.max_deps=(int(value) if value.isnumeric()
                        else -1)

    def __init__(self,args:list[str],flags:dict):
        self.unpack_args(args,flags)
        print("Packet manager v1.0")
        match self.command.lower():
            case "install": self.install_packets()
            case "uninstall": self.uninstall_packets()
            case "help": self.help()
            case "": print("No command specified. Need help? Run with --help")
            case _:print("Unknown command specified:",
                    self.command,"\nProgram will exit now.")

    def sort_versions(self, packet: dict) -> list[str]:
        versions_dict = next(iter(packet.values()))
        
        version_strings = list(versions_dict.keys())
        
        sorted_versions = sorted(
            version_strings, 
            key=lambda v_str: [int(part) for part in v_str.split(".")]
        )
        
        return sorted_versions

    def update_indexes(self):
        print(f"    Updating {self.download_repo} index")
        r = requests.get(self.download_repo,timeout=10)
        r.raise_for_status()
        self.indexes = r.json()
        print(f"    Updated indexes successfully")

    def split_packet(self,packet_with_version:str):
        packet = packet_with_version
        version = None
        if packet.find("[") != -1:
            p = packet.split("[")
            packet = p[0]
            version = p[1][:-1]
        return (packet,version)


    def install_packets(self):
        self.update_indexes()
        for p in self.packets:
            print(f"    Indexing {p}")
            print(self.indexes)
            packet,version = self.split_packet(p)
            if p in self.indexes:
                # TODO: VERSION IS NONE
                if version in self.indexes[packet]:
                    print(f"  Downloading {packet}")
                else:
                    if version:
                        print(f"      FAIL {packet} with version {version} Not found")
                    else:
                        print(f"      FAIL {packet} with version ANY Not found")
            else:
                print(f"      FAIL {packet} Not found")

    def uninstall_packets(self):
        self.update_indexes()

    def help(self):
        print("\n  Pacman manual\n")
        print("\t  pacman [COMMAND] [PACKETS] (OPTIONAL FLAGS)\n")
        print("\tCommands:")
        print("\tinstall \t- installs specified packet(s)")
        print("\tuninstall \t- uninstalls specified packet(s)")
        print("\thelp \t\t- print this menu")
        print()
        

if __name__ == "__main__":
    args = []
    flags = {}
    flag_key = ""
    for arg in sys.argv:
        if arg.startswith("-"):
            if flag_key != "":
                flags[flag_key] = ""
            flag_key = arg.strip("-")
        else:
            if flag_key != "":
                flags[flag_key] = arg
                flag_key = ""
            else:
                args.append(arg)
    if flag_key:
        flags[flag_key] = ""

    print("Your inputs are: "," ".join(args))
    print("Your flags are: ",str(flags))
    print()
    Packet_manager(args,flags)