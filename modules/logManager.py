import modules.pytools as pytools

import os
import inspect
import sys

def init(pluginf):
    if os.path.exists(".\\working"):
        try:
            os.mkdir(".\\logs")
        except:
            pass
        try:
            os.mkdir(".\\logs\\" + pluginf)
        except:
            pass
    else:
        try:
            os.mkdir("..\\logs")
        except:
            pass
        try:
            os.mkdir("..\\logs\\" + pluginf)
        except:
            pass
        
class settings:
    debug = False
    logErrors = True
    hasStarted = False

def write(strf, pluginf="system"):
    
    pluginf = pluginf.split(".py")[0]
    
    if not os.path.exists("..\\logs\\" + pluginf):
        if not os.path.exists(".\\logs" + pluginf):
            init(pluginf)
    
    dateArray = pytools.clock.getDateTime()
    dateString = str(dateArray[0]) + "-" + str(dateArray[1]) + "-" + str(dateArray[2]) + "_" + str(dateArray[3]) + "."  + str(dateArray[4]) + "."  + str(dateArray[5])
    print(str(dateArray) + " ;;; " + pluginf + "; " + str(strf))
    try:
        if settings.debug:
            if os.path.exists(".\\working"):
                pytools.IO.appendFile(".\\logs\\" + pluginf + "\\" + dateString.split("_")[0] + "_system.log", "\n" + str(dateArray) + " ;;; " + pluginf + "; " + str(strf))
            else:
                pytools.IO.appendFile("..\\logs\\" + pluginf + "\\" + dateString.split("_")[0] + "_system.log", "\n" + str(dateArray) + " ;;; " + pluginf + "; " + str(strf))
        elif ("Traceback" in str(strf)) or ("Error" in str(strf)) or ("error" in str(strf)) or ("Failed" in str(strf)) or ("failed" in str(strf)) or ("Unable" in str(strf)) or ("unable" in str(strf)) or ("WARNING" in str(strf)) or ("Warning" in str(strf)) or ("warning" in str(strf)):
            if os.path.exists(".\\working"):
                pytools.IO.appendFile(".\\logs\\" + pluginf + "\\" + dateString.split("_")[0] + "_system.log", "\n" + str(dateArray) + " ;;; " + pluginf + "; " + str(strf))
            else:
                pytools.IO.appendFile("..\\logs\\" + pluginf + "\\" + dateString.split("_")[0] + "_system.log", "\n" + str(dateArray) + " ;;; " + pluginf + "; " + str(strf))
    except:
        pass

def printLog(strf):
    
    try:
        write(strf, inspect.stack()[1][1].replace("<", "").replace(">", "").split("\\")[-1].split(".py")[0])
    except:
        write(strf)
        
    if settings.hasStarted:
        return
    
    for arg in sys.argv:
        if arg == "--debug":
            settings.debug = True
    
    settings.hasStarted = True
        
            
            
            