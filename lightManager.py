from functools import partial
import logging
import os
import json
import time
import pymel.core as pm
from maya import OpenMayaUI as omui
from Qt import QtWidgets, QtCore, QtGui
import Qt

logging.basicConfig()
log = logging.getLogger("LightManager")
log.setLevel(logging.DEBUG)

# RESOLVING IMPORT -------------------------------------------------------------

# importing wrapInstance, Signal
binding_version = Qt.__binding_version__
if binding_version == "PySide":
    from shiboken import wrapInstance
    from Qt.QtCore import Signal 
    log.debug("Using PySide with shiboken")
elif binding_version.startswith("PyQt"):
    from sip import wrapinstance as wrapInstance
    from Qt.QtCore import pyqtSignal as Signal
    log.debug("Using PyQt with sip")
else: 
    from shiboken2 import wrapInstance
    from Qt.QtCore import Signal 
    log.debug("Using PySide2 with shiboken")

# HELPERS ----------------------------------------------------------------------

def getMayaMainWindow():
    win = omui.MQtUtil_mainWindow()
    ptr = wrapInstance(int(win), QtWidgets.QMainWindow) #???
    return ptr

def getDock(name="LightManagerDock"):
    deleteDock(name)
    ctrl = pm.workspaceControl(name, 
                               dockToMainWindow=("right", 1), 
                               label="LightManager")
    qtControl = omui.MQtUtil_findControl(ctrl)
    ptr = wrapInstance(int(qtControl), QtWidgets.QWidget)
    return ptr

def deleteDock(name="LightManagerDock"):
    if pm.workspaceControl(name, query=True, exists=True):
        pm.deleteUI(name)

# LIGHT MANAGER ----------------------------------------------------------------

class LightManager(QtWidgets.QWidget):

    lightTypes = {
        "Point Light": pm.pointLight,
        "Spot Light": pm.spotLight,
        "Directional Light": pm.directionalLight,
        "Area Light": partial(pm.shadingNode, "areaLight", asLight=True),
        "Volume Light": partial(pm.shadingNode, "volumeLight", asLight=True)
    }

    def __init__(self, dock=True):

        if dock: 
            parent = getDock()
        else: 
            deleteDock()
            try : 
                pm.deleteUI("LightManager")
            except : 
                log.debug("No previous UI exists")

            parent = QtWidgets.QDialog(parent=getMayaMainWindow())
            parent.setObjectName("LightManager")
            parent.setWindowTitle("Light Manager")
            layout = QtWidgets.QVBoxLayout(parent)


        super(LightManager, self).__init__(parent)
        self.buildUI()
        self.populate()
        self.parent().layout().addWidget(self)
        if not dock: parent.show()
        #self.show()

    def populate(self):
        for widget in self.findChildren(LightWidget): 
            widget.deleteLightWidget()
        for light in pm.ls(lights=True):
            self.addLight(light)

    def buildUI(self): 
        layout = QtWidgets.QGridLayout(self)

        self.lighTypeCB = QtWidgets.QComboBox()
        layout.addWidget(self.lighTypeCB, 0, 0)
        for lightType in sorted(self.lightTypes): 
            self.lighTypeCB.addItem(lightType)

        createButton = QtWidgets.QPushButton("Create")
        layout.addWidget(createButton, 0, 1)
        createButton.clicked.connect(self.createLight)

        scrollWidget = QtWidgets.QWidget()

        #???????????????????????????????????????????????????????????????????????
        #scrollWidget.setSizePolicy(QtWidgets.QSizePolicy.Maximum)

        self.scrollLayout = QtWidgets.QVBoxLayout(scrollWidget)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(scrollWidget)
        layout.addWidget(scrollArea, 1, 0, 1, 3)

        saveBtn = QtWidgets.QPushButton("Save")
        saveBtn.clicked.connect(self.saveLights)
        layout.addWidget(saveBtn, 2, 0)

        importBtn = QtWidgets.QPushButton("Import")
        importBtn.clicked.connect(self.importLights)
        layout.addWidget(importBtn, 2, 1)
        
        refreshBtn = QtWidgets.QPushButton("Refresh")
        refreshBtn.clicked.connect(self.populate)
        layout.addWidget(refreshBtn, 2, 2)

    def createLight(self):
        light = self.lightTypes[self.lighTypeCB.currentText()]()
        self.addLight(light)

    def addLight(self, light):
        widget = LightWidget(light)
        self.scrollLayout.addWidget(widget)
        widget.onSolo.connect(self.onSolo)

    def onSolo(self, value):
        lightWidgets = self.findChildren(LightWidget)
        sender = self.sender()

        # un isolating a light if not sender
        for widget in lightWidgets:
            if (widget.isSolo() and widget != sender):
                previous_solo = widget
                for w in lightWidgets : 
                    if w not in (previous_solo, sender):
                        widget.disableLight(False)
                # reemetting the signal once situation is reinitialized.
                sender.setSolo(True)
        # isolating sender
        for widget in lightWidgets: 
            if widget != self.sender():
                widget.disableLight(value)

    def saveLights(self):
        properties = {}
        directory = self.getLightManagerDir()
        for lightWidget in self.findChildren(LightWidget):
            light = lightWidget.light
            transform = light.getTransform()
            properties[str(transform)] = {
                "translate" : list(transform.translate.get()),
                "rotation"  : list(transform.rotate.get()), 
                "lightType" : pm.objectType(light), 
                "intensity" : light.intensity.get(),
                "color" : light.color.get()
            }
        lightFile = os.path.join(
            directory,
            "lightFile_{}.json".format(time.strftime("%m%d")))
        with open(lightFile, "w") as f : 
            json.dump(properties,f , indent=4)
        log.info("saved lights at {}".format(lightFile))

    def importLights(self):
        pass
        # beurk 
        #directory = self.getLightManagerDir()
        #fileName = QtWidgets.QFileDialog.getOpenFileName(self, "Light Broswer", 
        #                                                directory)[0]
        #with open(fileName, "r") as f: 
        #    properties = json.load(f)
        #for light, info in properties.items():
        #    lightType = info.get("lightType")
        #    found=False
        #    for lt in self.lightTypes:
        #        lt = "%sLight" % lt.split()[0].lower()
        #        if lt == lightType:
        #            found = True
        #            break 
        #    if not found: 
        #        log.info("Cannot find a corresponding light type for {}".light)

    def getLightManagerDir(self):
        directory = os.path.join(
            pm.internalVar(userAppDir=True),
            "lightManager")
        if not os.path.exists(directory): os.mkdir(directory)
        return directory



class LightWidget(QtWidgets.QWidget):

    onSolo = Signal(bool)

    def __init__(self, light):
        super(LightWidget, self).__init__()
        if isinstance(light, str):
            light = pm.PyNode(light)
        self.light = light
        self.buildUI()

    def buildUI(self):
        layout = QtWidgets.QGridLayout(self)
        self.name = QtWidgets.QCheckBox(str(self.light.getTransform()))
        self.name.setChecked(self.light.visibility.get())
        self.name.toggled.connect(
            lambda val: self.light.getTransform().visibility.set(val))
        layout.addWidget(self.name, 0,0)

        self.soloBtn = QtWidgets.QPushButton("Solo")
        self.soloBtn.setCheckable(True)
        self.soloBtn.toggled.connect(lambda val : self.onSolo.emit(val))
        layout.addWidget(self.soloBtn, 0, 1)

        deleteBtn = QtWidgets.QPushButton("X")
        deleteBtn.clicked.connect(self.deleteLight)
        deleteBtn.setMaximumWidth(10)
        layout.addWidget(deleteBtn, 0,2)

        intensity = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        intensity.setMinimum(1)
        intensity.setMaximum(1000)
        intensity.setValue(self.light.intensity.get())
        intensity.valueChanged.connect(self.changeIntensity)
        layout.addWidget(intensity, 1, 0, 1, 2)

        self.colorBtn = QtWidgets.QPushButton()
        self.colorBtn.setMaximumWidth(20)
        self.colorBtn.setMaximumHeight(20)
        self.setButtonColor()

        self.colorBtn.clicked.connect(self.setColor)
        layout.addWidget(self.colorBtn, 1, 2)

    def isSolo(self): return self.soloBtn.isChecked()
    def setSolo(self, val): self.soloBtn.setChecked(val) 

    def setColor(self):
        color_str = pm.colorEditor(rgbValue=self.light.color.get())
        r, g, b, a = [float(c) for c in color_str.split()]
        color = (r, g, b)
        self.light.color.set(color)
        self.setButtonColor(color)

    def setButtonColor(self, color=None):
        if not color: 
            color = self.light.color.get()
        assert(len(color)==3)
        r,g,b = [c*255 for c in color] # why?
        self.colorBtn.setStyleSheet(
            "background-color: rgba({}, {}, {}, 1.0)".format(r, g, b))

    def disableLight(self, value):
        self.name.setChecked(not value)
        self.soloBtn.setChecked(False)

    def deleteLight(self):
        self.deleteLightWidget()
        pm.delete(self.light.getTransform())

    def deleteLightWidget(self):
        self.setParent(None)
        self.setVisible(False)
        self.deleteLater()

    def changeIntensity(self, value):
        self.light.intensity.set(value)