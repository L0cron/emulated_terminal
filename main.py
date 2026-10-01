import customtkinter as ctk
import subprocess
import pathlib
import time
# for username and hostname
import getpass
import socket

import base64
import xml.etree.ElementTree as ET

ctk.set_appearance_mode("dark")

class Terminal(ctk.CTk):

    propmt = ""

    directory = "/home/locron"
    is_vfs = False
    vfs_path = ""
    
    VFS = {}
    vfs_name = ""

    def get_current_vfs_dir(self) -> dict:
        if self.directory == "/": return self.VFS["/"]

        parts = self.directory.split("/")[1:]
        try:
            
            t = self.VFS["/"]
            for i in parts:
                t = t["children"][i]

            return t
        except:
            print("no such dir?")
            return self.VFS


    def read_vfs(self, vfs_path: str):
        tree = ET.parse(vfs_path)
        root = tree.getroot()
        self.vfs_name = root.get("name")

        def parse_element(element):
            if element.tag == "dir":
                return {
                    "type": "dir",
                    "children": {
                        child.get("name"): parse_element(child)
                        for child in element
                    },
                }
            elif element.tag == "file":
                b64_content = element.get("content", "")
                return {
                    "type": "file",
                    "content": base64.b64decode(b64_content).decode("utf-8"),
                }

        self.VFS = {child.get("name"): parse_element(child) for child in root}

    def __init__(self, vfs_path="", start_script=""):
        super().__init__()
        username = getpass.getuser()
        hostname = socket.gethostname()

        if not vfs_path:
            self.title(f"Terminal [{username}@{hostname}]")
        else:
            self.is_vfs = True
            self.vfs_path = self.vfs_path
            self.directory = "/"
            self.read_vfs(vfs_path)
            self.title(f"Terminal [VFS: {pathlib.Path(vfs_path).resolve()}]")
        self.geometry("700x400")

        self.terminal = ctk.CTkTextbox(self, width=680, height=300, font=("Courier New", 14) ,text_color="#FFFFFF")
        # self.terminal._textbox.configure()
        self.terminal.pack(pady=10, padx=10, fill="both", expand=True)
        self.terminal._textbox.configure(insertbackground="#FFFFFF", fg="#FFFFFF", state="disabled")


        self.terminal.tag_config("green", foreground="#39FF14")
        self.terminal._textbox.tag_config("green_bold", foreground="#39FF14", font=("Courier New", 10, "bold"))
                        
        self.terminal.tag_config("white", foreground="#FFFFFF")
        self.terminal._textbox.tag_config("white_bold", foreground="#FFFFFF", font=("Courier New", 10, "bold"))

        self.terminal.tag_config("red", foreground="#FF3333")
        
        self.terminal.tag_config("cyan", foreground="#00FFFF")
        self.terminal._textbox.tag_config("cyan_bold", foreground="#00FFFF", font=("Courier New", 10, "bold"))
        
        self.terminal.tag_config("blue", foreground="#4E89FF")
        self.terminal._textbox.tag_config("blue_bold", foreground="#4E89FF", font=("Courier New", 10, "bold"))

        self.propmt = ""
        self.terminal._textbox.bindtags((self.terminal._textbox, self, "all")) 
        self.terminal.bind("<Key>",self.key_grabber)
        self.terminal.focus()


        self.line_starter()


        if start_script:
            self.start_script = start_script
            self.execute_script(self.start_script)

    def execute_script(self,script:str):
        pass

    def key_grabber(self,event):

        if event.keysym == "Return":
            self.send_command()
        elif event.keysym == "BackSpace":
            if len(self.propmt) > 0:
                self.propmt = self.propmt[:-1]
                self.terminal.delete("end-2c", "end-1c")
        else:
            if event.char:
                self.propmt += event.char
                self.terminal.insert("end", event.char)
        pass

    def print_to_console(self,text:str):
        self.terminal.insert("end",text+"\n")



    def execute(self, command, args):
        if command == "help":
            self.print_to_console("Terminal ver 1.0")
            self.print_to_console("Available commands:")
            self.print_to_console("- help \t: prints help menu")
            self.print_to_console("- cd \t: changes current directory")
            self.print_to_console("- ls \t: lists files and directories in current")
            self.print_to_console("- pwd \t: prints absolute path for current directory")
            self.print_to_console("- exit \t: disintegrate app")
        elif command == "pwd":
            self.print_to_console(self.directory)
        elif command == "exit":
            self.terminal.insert("end","\nBye-bye\n\n","white_bold")
            exit()
        elif command == "cd":
            if len(args) == 0:
                return
            d = args[0]
            if self.is_vfs:
                file = self.directory + "/" + d
                file = file.replace("//","/")
                p = self.get_current_vfs_dir()
                if d in p["children"]:
                    self.directory = file
                    # TODO: add abs path
                else:
                    self.print_to_console(f"{d} not found")
            else:
                file = pathlib.Path(self.directory, d)
                if file.exists():
                    self.directory = file.resolve()
                else:
                    abs_path = pathlib.Path(d)
                    if file.exists():
                        self.directory = abs_path.resolve()
                    else:
                        self.print_to_console(f"{abs_path.resolve()} not found")

        elif command == "ls" or command == "dir":
            self.command_ls()
        else:
            self.print_to_console("Unknown command, type 'help' for help.")

    def execute_script(self,script_path:str):

        with open(script_path) as f:
            prompts = f.readlines()
            for p in prompts:
                self.propmt = p
                self.send_command()

    def send_command(self):
        self.print_to_console("")
        # Execute command

        parts = self.propmt.split()
        if len(parts) > 0:
            args = []
            if len(parts) > 1:
                args = parts[1:]
            self.execute(parts[0],args)


        # Finished all sequences

        self.propmt = ""
        self.line_starter()
        return

    def command_ls(self):

        if self.is_vfs:
            dir = self.get_current_vfs_dir()
            print(dir)
            for file in dir["children"]:    
                col = "white_bold"
                print(file)
                if dir["children"][file]["type"] == "dir":
                    col = "blue_bold"
                self.terminal.insert("end", file+" ",col)
            self.print_to_console("")
        else:
            for file in pathlib.Path(self.directory).iterdir():
                col = "white_bold"
                if file.is_dir():
                    col = "blue_bold"
                self.terminal.insert("end", file.name+" ",col)
            self.print_to_console("")

    def line_starter(self):
        username = getpass.getuser()
        hostname = socket.gethostname()

        self.terminal.configure(state="normal")

        if self.is_vfs:
            self.terminal.insert("end",f"[VFS] ","cyan_bold")
            self.terminal.insert("end",f"{username}","green_bold")
            self.terminal.insert("end",f":","white_bold")
            self.terminal.insert("end",self.directory, "cyan_bold")
            self.terminal.insert("end",f"$ ","white_bold")
        else:
            self.terminal.insert("end",f"{username}@{hostname}", "green_bold")
            self.terminal.insert("end",f":", "white_bold")
            self.terminal.insert("end",self.directory, "cyan_bold")
            self.terminal.insert("end",f"$ ", "white_bold")

            
        self.terminal.see("end")
        

import sys
if __name__ == "__main__":

    args = sys.argv

    vfs_path = None
    start_script = None
    if len(args) > 1:
        vfs_path = args[1]
    if len(args) > 2:
        start_script = args[2]

    app = Terminal(vfs_path=vfs_path, start_script=start_script)
    app.mainloop()