import customtkinter as ctk
import subprocess
import pathlib
import time
"""for username and hostname"""
import getpass
import socket
import platform

import base64
import xml.etree.ElementTree as et

ctk.set_appearance_mode("dark")

class Terminal(ctk.CTk):

    propmt = ""

    directory = "/"
    is_vfs = False
    vfs_path = ""
    
    vfs = {}
    vfs_name = ""

    def get_current_vfs_dir(self) -> dict:
        if self.directory == "/": return self.vfs["/"]

        parts = self.directory.split("/")[1:]
        try:
            
            t = self.vfs["/"]
            for i in parts:
                t = t["children"][i]

            return t
        except:
            return None


    def read_vfs(self, vfs_path: str):
        tree = et.parse(vfs_path)
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

        self.vfs = {child.get("name"): parse_element(child) for child in root}

    def __init__(self, vfs_path="", start_script=""):
        super().__init__()
        username = getpass.getuser()
        hostname = socket.gethostname()

        if not vfs_path:
            self.title(f"Terminal [{username}@{hostname}]")
            self.directory = str(pathlib.Path(self.directory).resolve())
        else:
            self.command_vfs_init()
        self.geometry("700x400")

        self.terminal = ctk.CTkTextbox(self, width=680, height=300, font=("Courier New", 14) ,text_color="#FFFFFF")
        # self.terminal._textbox.configure()
        self.terminal.pack(pady=10, padx=10, fill="both", expand=True)
        self.terminal._textbox.configure(insertbackground="#FFFFFF", fg="#FFFFFF", state="disabled")
        self.terminal_tags()

        self.line_starter()

        if start_script:
            self.start_script = start_script
            self.execute_script(self.start_script)

    def terminal_tags(self):
        self.terminal.tag_config("green", foreground="#39FF14")
        self.terminal._textbox.tag_config("green_bold", foreground="#39FF14", font=("Courier New", 10, "bold"))
                        
        self.terminal.tag_config("white", foreground="#FFFFFF")
        self.terminal._textbox.tag_config("white_bold",foreground="#FFFFFF", font=("Courier New", 10, "bold"))

        self.terminal.tag_config("red", foreground="#FF3333")
        
        self.terminal.tag_config("cyan", foreground="#00FFFF")
        self.terminal._textbox.tag_config("cyan_bold", foreground="#00FFFF", font=("Courier New", 10, "bold"))
        
        self.terminal.tag_config("blue", foreground="#4E89FF")
        self.terminal._textbox.tag_config("blue_bold", foreground="#4E89FF", font=("Courier New", 10, "bold"))

        current_os = platform.system()

        if current_os == "Linux":
            self.terminal.bind("<Button-4>", self.on_mouse_wheel)
            self.terminal.bind("<Button-5>", self.on_mouse_wheel)
        else:
            self.terminal.bind("<MouseWheel>", self.on_mouse_wheel)

        self.propmt = ""
        self.terminal._textbox.bindtags((self.terminal._textbox, self, "all")) # это кушает все обработчики событий
        self.terminal.bind("<Key>",self.key_grabber)
        self.terminal.focus_force()

    def on_mouse_wheel(self, event):
        scroll_speed = 2
        if event.num == 4 or event.delta > 0:
            self.terminal.yview_scroll(-scroll_speed, "units")
        elif event.num == 5 or event.delta < 0:
            self.terminal.yview_scroll(scroll_speed, "units")
            


    def execute_script(self,script:str):
        f = pathlib.Path(script)
        if f.exists():
            file = open(f)
            for line in file.readlines():
                self.paste_command(line.strip())
                self.propmt = line                
                r = self.send_command()
                if not r:
                    break
        self.terminal.focus_force()
                

    def paste_command(self,command:str):
        self.terminal.insert("end",command,"white_bold")

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



    def execute(self, command, args) -> bool:
        if command == "help":
            self.print_to_console("Terminal ver 1.0")
            self.print_to_console("Available commands:")
            self.print_to_console("- help \t: prints help menu")
            self.print_to_console("- cd \t: changes current directory")
            self.print_to_console("- ls \t: lists files and directories in current")
            self.print_to_console("- pwd \t: prints absolute path for current directory")
            self.print_to_console("- exit \t: disintegrate app")
            if self.is_vfs:
                self.print_to_console("- vfs-init \t: clears current VFS to initial state")
            return True
        elif command == "pwd":
            self.print_to_console(self.directory)
            return True
        elif command == "exit":
            exit()
        elif command == "cd":
            return self.command_cd(args)
        elif command == "ls" or command == "dir":
            return self.command_ls()
        elif command == "vfs-init":
            return self.command_vfs_init()
        elif command == "tail":
            return self.command_tail(args)
        elif command == "cat":
            return self.command_cat(args)
        elif command == "mkdir":
            return self.command_mkdir(args)
        else:
            self.print_to_console("Unknown command, type 'help' for help.")
            return False


    def send_command(self) -> bool:
        self.print_to_console("")
        r = False
        parts = self.propmt.split()
        if len(parts) > 0:
            args = []
            if len(parts) > 1:
                args = parts[1:]
            r = self.execute(parts[0],args)


        # Finished all sequences

        self.propmt = ""
        self.line_starter()
        return r

    
    def command_vfs_init(self) -> bool:
        self.is_vfs = True
        self.vfs_path = self.vfs_path
        self.directory = "/"
        self.read_vfs(vfs_path)
        self.title(f"Terminal [VFS: {pathlib.Path(vfs_path).resolve()} ]")
        return True

    def command_mkdir(self,args) -> bool:
        if len(args) == 0: return False
        dir = args[0]

        path = self.get_current_vfs_dir()
        if dir in path["children"]:
            self.print_to_console("This directory already exists")
            return False

        path["children"][dir] = {
            "type": "dir",
            "children": {}
        }
        
        return True

    def command_cat(self,args) -> bool:
        if len(args) == 0: return False
        f = args[0]
        if self.is_vfs:
            p = self.get_current_vfs_dir()
            if f in p["children"]:
                if p["children"][f]["type"] != "file":
                    self.print_to_console(f"{f} is not a file")
                    return False

                self.print_to_console(p["children"][f]["content"])
                return True
            else:
                return False # file does not exist
        else:
            pass
            # на этом этапе мне стало лень делать функционал функций не для vfs
        return False

    def command_tail(self,args) -> bool:
        if len(args) == 0: return False
        f = args[0]
        if self.is_vfs:
            p = self.get_current_vfs_dir()
            if f in p["children"]:
                if p["children"][f]["type"] != "file":
                    self.print_to_console(f"{f} is not a file")
                    return False

                data = p["children"][f]["content"]
                data = "\n".join(data.split("\n")[-10:])
                self.print_to_console(data)
                return True
            else:
                return False # file does not exist
        else:
            pass
            # на этом этапе мне стало лень делать функционал функций не для vfs
        return False

    def command_cd(self,args) -> bool:
        if len(args) == 0:
            return
        started = self.directory
        d = args[0]
        if self.is_vfs: # VFS
            if d == "/":
                self.directory = "/"
                return True
            else:
                c = self.directory
                for i in d.split("/"):
                    if i == "..":
                        c_parts = c.split("/")
                        if len(c_parts) > 1:
                            c = "/".join(c_parts[:-1])
                        else:
                            c = "/"
                    else:
                        c = c + "/" + i
                if c == "": c = "/"
                self.directory = c.replace("//","/")
                    
            
            p = self.get_current_vfs_dir()
            if not p:
                self.directory = started
                self.print_to_console(f"{d} not found")
                return False
            return True

        else: # ACTUAL
            file = pathlib.Path(self.directory, d)
            if file.exists():
                self.directory = file.resolve()
            else:
                abs_path = pathlib.Path(d)
                if file.exists():
                    self.directory = abs_path.resolve()
                else:
                    self.print_to_console(f"{abs_path.resolve()} not found")

    def command_ls(self) -> bool:

        if self.is_vfs:
            dir = self.get_current_vfs_dir()
            for file in dir["children"]:    
                col = "white_bold"
                if dir["children"][file]["type"] == "dir":
                    col = "blue_bold"
                f = file if file.find(" ") == -1 else f"\"{file}\""
                self.terminal.insert("end", f+" ",col)
            if len(dir["children"]) > 0:
                self.print_to_console("")
        else:
            for file in pathlib.Path(self.directory).iterdir():
                col = "white_bold"
                if file.is_dir():
                    col = "blue_bold"
                f = file.name if file.name.find(" ") == -1 else f"\"{file.name}\""
                self.terminal.insert("end", f+" ",col)
            if len(dir["children"]) > 0:
                self.print_to_console("")
        return True

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

    stupid_const_variable_one = 1
    stupid_const_variable_two = 2
    if len(args) > stupid_const_variable_one:
        vfs_path = args[1]
    if len(args) > stupid_const_variable_two:
        start_script = args[2]

    app = Terminal(vfs_path=vfs_path, start_script=start_script)
    app.mainloop()