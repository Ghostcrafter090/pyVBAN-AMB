import modules.pyvban as pyvban
import modules.pytools as pytools
import modules.logManager as log

import sounddevice as sd

import threading
import random
import traceback
import time
import copy
import os

log.settings.debug = True

print = log.printLog

class status:
    exitf = False

class util:

    ports = {
        "clock": 6981,
        "fireplace": 6982,
        "window": 6983,
        "outside": 6984,
        "porch": 6985,
        "generic": 6986,
        "light": 6987
    }

    def getOutputs():
        if os.path.exists(".\\soundInputs.json"):
            speakers = pytools.IO.getJson(".\\soundInputs.json")
        if os.path.exists("..\\soundInputs.json"):
            speakers = pytools.IO.getJson("..\\soundInputs.json")
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for channel in speakers:
                for n in devices:
                    import time
                    time.sleep(0.1)
                    if speakers[channel][0] == n["name"]:
                        if speakers[channel][1] == "MME":
                            if n["hostapi"] == 0:
                                deviceIndex = n["index"]
                                break
                        if speakers[channel][1] == "WDM-KS":
                            if n["hostapi"] == 4:
                                deviceIndex = n["index"]
                                break
                speakers[channel].append(deviceIndex)
            pytools.IO.saveJson("inputSets.json", {
                "speakers": speakers
            })
            return speakers
        except:
            import traceback
            print(traceback.format_exc())

class vbanReceiverThread:
    def __init__(self, speakerType, fromIp, deviceIndex, manualPort=False):

        self.speakerType = speakerType
        self.fromIp = fromIp
        self.deviceIndex = deviceIndex

        if not manualPort:
            self.vbanObj = pyvban.utils.VBAN_Receiver(
                sender_ip=fromIp,
                stream_name="Stream" + speakerType[0].upper() + speakerType[1:],
                port=util.ports[speakerType],
                device_index=deviceIndex
            )
        else:
            self.vbanObj = pyvban.utils.VBAN_Receiver(
                sender_ip=fromIp,
                stream_name="Stream" + speakerType[0].upper() + speakerType[1:],
                port=manualPort,
                device_index=deviceIndex
            )

        self.thread = threading.Thread(target=self.run)

    deviceIndex = -1
    isRunning = False
    hasStopped = False

    def run(self):
        self.isRunning = True
        self.id = random.randint(0, 9999999999)
        print("Stating stream with ID: " + str(self.id) + ", speakerType: " + self.speakerType + ", speaker, IP: " + self.fromIp + ", deviceIndex: " + str(self.deviceIndex) + "...")
        
        try:
            self.vbanObj.run()
        except:
            print(traceback.format_exc())

        print("Stream thread with id " + str(self.id) + " has exited.")
        self.hasStopped = True
        self.isRunning = False

    def start(self):
        if not (self.isRunning and self.hasStopped):
            self.thread.start()
        else:
            print("Stream has already been started.")

    def stop(self):
        self.vbanObj.stop()

class speaker:
    def __init__(self, speakerType, receiveFrom):
        self.speakerType = speakerType
        self.receiveFrom = receiveFrom

        self.mainThread = threading.Thread(target=self.main)
    
    receiverThread = False

    isRunning = False
    hasExited = False

    lastUpdated = time.time()

    deviceIndex = 0

    exitf = False
    
    def settingsModified(self):
        if self.receiverThread:
            self.receiverThread.stop()
        
        try:
            while self.receiverThread.isRunning:
                time.sleep(0.1)
        except:
            pass

        doOverriteReceiver = False
        if self.receiveFrom != False:
            newReceiverThread = vbanReceiverThread(self.speakerType, self.receiveFrom, self.deviceIndex)
            newReceiverThread.start()
            doOverriteReceiver = True
        
        if doOverriteReceiver:
            self.receiverThread = newReceiverThread

    def setSpeakerType(self, speakerType):
        self.speakerType = speakerType
    
    def setReceiveFromIp(self, receiveFrom):
        self.receiveFrom = receiveFrom

    def main(self):
        speakerTypeOld = False
        receiveFromOld = False
        sendToOld = False
        self.isRunning = True

        while (not self.exitf) and (not status.exitf):
            try:
                if self.receiverThread:
                    jsonData = {
                        "receiveFrom": self.receiveFrom,
                        "info": {
                            "receiver": {
                                "deviceIndex": self.receiverThread.deviceIndex,
                                "isRunning": self.receiverThread.isRunning,
                                "hasStopped": self.receiverThread.hasStopped,
                                "lastActivityTimestamp": int(self.receiverThread.vbanObj.lastActivityTimestamp / 10) * 10,
                                "currentBufferSize": len(self.receiverThread.vbanObj.packetBuffer)
                            }
                        },
                        "lastUpdated": pytools.clock.getDateTime()[0:5] 
                    }
                    
                else:
                    jsonData = {
                        "receiveFrom": self.receiveFrom,
                        "info": {
                            "receiver": {
                                "deviceIndex": None,
                                "isRunning": False,
                                "hasStopped": False,
                                "lastActivityTimestamp": 0,
                                "currentBufferSize": 0
                            }
                        },
                        "lastUpdated": pytools.clock.getDateTime()[0:5] 
                    }
                if pytools.IO.getJson(".\\streams\\" + self.speakerType + "_info.json") != jsonData:
                    if not os.path.exists(".\\streams"):
                        os.mkdir(".\\streams")
                    pytools.IO.saveJson(".\\streams\\" + self.speakerType + "_info.json", jsonData)
                
                try:
                    self.deviceIndex = util.getOutputs()[self.speakerType][2]
                except:
                    print(traceback.format_exc())

                if (speakerTypeOld != self.speakerType):
                    print("Settings Modified!")
                    speakerTypeOld = copy.deepcopy(self.speakerType)
                    receiveFromOld = copy.deepcopy(self.receiveFrom)
                    self.settingsModified()

                if (receiveFromOld != self.receiveFrom):
                    print("Receive Settings Modified!")
                    speakerTypeOld = copy.deepcopy(self.speakerType)
                    receiveFromOld = copy.deepcopy(self.receiveFrom)
                    
                    self.settingsModified()

            except:
                print(traceback.format_exc())

            try:
                if (self.receiverThread.vbanObj.lastActivityTimestamp + 80) < time.time():
                    self.settingsModified()
                if (self.receiverThread.vbanObj.lastStreamActivityTimestamp + 80) < time.time():
                    self.settingsModified()
            except:
                self.settingsModified()
                print(traceback.format_exc())

            self.lastUpdated = time.time()
            
            time.sleep(1)
        try:
            self.receiverThread.stop()
        except:
            print("Could not stop receiver thread, or has already stopped.")

        try:
            while self.receiverThread.isRunning:
                self.receiverThread.stop()
                time.sleep(0.1)
        except:
            pass

        self.isRunning = False
        self.hasExited = True
        
    def run(self):
        print("Starting new speaker type " + self.speakerType + "...")
        self.mainThread.start()