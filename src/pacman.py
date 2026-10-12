

import sys
import re
import requests

class Packet_manager():
    packets = []
    command = ""
    download_repo = "https://github.com/L0cron/emulated_terminal.git"

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
            case "": print("No command specified. Need help? Type --help")
            case _:print("Unknown command specified:",
                    self.command,"\nProgram will exit now.")

    def install_packets(self):
        print("You chose to install packets")
        pass

    def uninstall_packets(self):
        print("You chose to uninstall packets")

    def help(self):
        print("\n  Pacman manual\n")
        print("    pacman [COMMAND] [PACKETS] (OPTIONAL FLAGS)\n")
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

    print("Your inputs are: "," ".join(args))
    print("Your flags are: ",str(flags))
    print()
    Packet_manager(args,flags)