# ---------------------------------------------------------------

import sys, os
import importlib

PATH = "path/to/src/"

def addToPyPath(path):
    if not os.path.exists(path): 
    	return False
    if not path in sys.path:
        sys.path.append(path)
    return True

addToPyPath(PATH)
# ---------------------------------------------------------------

import lightManager
importlib.reload(lightManager)

#l = lightManager.LightManager().show()
l = lightManager.LightManager(dock=True)