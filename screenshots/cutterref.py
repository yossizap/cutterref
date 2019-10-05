import cutter

from PySide2.QtCore import QObject, SIGNAL
from PySide2.QtWidgets import QAction, QTextEdit

import inspect
import os
import glob
import sqlite3 as sq

class CutterRef():
    def __init__(self, arch):
        self.base_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

        self.inst_map = {}
        self.arch = arch

        self.archs = self.find_manuals()
        
        self.load_architecture(self.arch)

    def get_instruction_doc(self, inst):
        orig_inst = inst
        inst = self.clean_instruction(inst)

        if(inst not in self.inst_map):
            inst = inst.upper()

        if(inst in self.inst_map):
            text = self.inst_map[inst]

            doc = ""
            if(len(text) > 0):
                doc += "<h1>" + orig_inst + ": " + text[0] + "</h1>"
                doc += "<pre>"
                if(len(text) > 1):
                    for line in text[1:]:
                        doc += line + "\n"
            doc += "</pre>"
            return doc
        else:
            return inst + " not documented."

    def clean_instruction(self, inst):
        if(inst and self.arch == "x86-64"):
            inst = inst.upper()
            # hacks for x86
            if(inst[0:1] == 'J' and inst != 'JMP'):
                inst = "Jcc"
            elif(inst[0:4] == "LOOP"):
                inst = "LOOP"
            elif(inst[0:3] == "INT"):
                inst = "INT n"
            elif(inst[0:5] == "FCMOV"):
                inst = "FCMOVcc"
            elif(inst[0:4] == "CMOV"):
                inst = "CMOVcc"
            elif(inst[0:3] == "SET"):
                inst = "SETcc"
            return inst

    def find_manuals(self):
        search_path = os.path.join(self.base_path, "archs", "*.sql")
        doc_opts = glob.glob(search_path)

        if(len(doc_opts) == 0):
            Warning("Couldn't find any databases in " + search_path)
            return

        available = []
        
        for c in doc_opts:
            basefile = os.path.splitext(os.path.basename(c))[0]            
            available.append(basefile)

        return available

    def load_architecture(self, name):
        # fix name
        name = name.lower()
        if name.startswith("x86"):
            name = "x86-64"
        if name.startswith("arm"):
            name = "arm"

        self.arch = name

        path = self.base_path
        dbpath = os.path.join(path, "archs", name + ".sql")

        if(not os.path.isfile(dbpath)):
            cutter.message("Manual not found for architecture: %s" % name)
            return False

        con = sq.connect(":memory:")
        con.text_factory = str
        con.executescript(open(dbpath).read())

        cur = con.cursor()
        cur.execute("SELECT mnem, description FROM instructions")
        con.commit()

        rows = cur.fetchall()
        for row in rows:
            inst = row[0]
            lines = row[1].replace("\r\n", "\n").split("\n")

            self.inst_map[inst] = lines

        con.close()

        for (inst, data) in self.inst_map.items():
            data = data[0]

            if(data[0:3] == "-R:"):
                ref = data[3:]

                if(ref in self.inst_map):
                    self.inst_map[inst] = self.inst_map[ref]

        cutter.message("Manual loaded for architecture: %s" % name)
        return True

class CutterRefWidget(cutter.CutterDockWidget):
    def __init__(self, parent, action):
        super(CutterRefWidget, self).__init__(parent, action)
        self.setObjectName("ins_ref")
        self.setWindowTitle("Instruction Reference")

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        self.setWidget(self.view)

        self.cutterref = None 
        self.previous_inst = ""

        QObject.connect(cutter.core(), SIGNAL("seekChanged(RVA)"), self.update_content)

    def update_content(self):
        current_line = cutter.cmdj("pdj 1")

        # Running "ij" during DockWidget init causes a crash
        if not self.cutterref:
            info = cutter.cmdj("ij")["bin"]
            arch = info["arch"]
            self.cutterref = CutterRef(info["arch"] + "-" + str(info["bits"]))

        try:
            inst = current_line[0]["disasm"].split()[0]
        except:
            return

        # Don't update the text box for the same instruction
        if inst != self.previous_inst:
            self.view.setHtml(self.cutterref.get_instruction_doc(inst))
            self.previous_inst = inst
        return

class CutterRefPlugin(cutter.CutterPlugin):
    name = "cutterref"
    description = "Presents complete instruction reference for an instruction under the cursor"
    version = "1.0"
    author = "Yossi Zap"

    def setupPlugin(self):
        pass

    def setupInterface(self, main):
        action = QAction("cutterref", main)
        action.setCheckable(True)
        widget = CutterRefWidget(main, action)
        main.addPluginDockWidget(widget, action)

    def terminate(self):
        pass

def create_cutter_plugin():
    return CutterRefPlugin()
