import modules.pyvban as pyvban
import modules.pytools as pytools
import modules.logManager as logManager

import sounddevice as sd

import threading
import random
import traceback
import time
import copy
import os

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

    def getInputs():
        
        try:
        
            outputs = pytools.IO.getJson("speakerSets.json")["speakers"]
            soundInputs = {
                "clock": ["", "MME"],
                "fireplace": ["", "MME"],
                "window": ["", "MME"],
                "outside": ["", "MME"],
                "porch": ["", "MME"],
                "generic": ["", "MME"],
                "light": ["", "MME"]
            }
            
            sortedKey = []
            
            for output in outputs:
                if outputs[output][0] == "Speakers (Realtek(R) Audio)":
                    input = "Microphone (ESS USB Audio)"
                else:
                    input = outputs[output][0].replace("Speakers", "CABLE Output").replace("CABLE Input", "CABLE Output")
                    while len(input) > 31:
                        input = input[:-1]
                sortedKey.append(input)
            
            soundInputs["clock"] = [sortedKey[0], "MME"]
            soundInputs["fireplace"] = [sortedKey[1], "MME"]
            soundInputs["window"] = [sortedKey[2], "MME"]
            soundInputs["outside"] = [sortedKey[3], "MME"]
            soundInputs["porch"] = [sortedKey[4], "MME"]
            soundInputs["generic"] = [sortedKey[5], "MME"]
            soundInputs["light"] = [sortedKey[6], "MME"]
            
            i = 0
            for input in soundInputs:
                if soundInputs[input][0] == "":
                    soundInputs[input][0] = sortedKey[i]
                i = i + 1
            
            for input in soundInputs:
                returnFalse = True
                i = 0
                for device in sd.query_devices():
                    if device["name"] == soundInputs[input][0]:
                        soundInputs[input].append(copy.deepcopy(i))
                        returnFalse = False
                        break
                    i = i + 1
                returnFalse = False
                
                if returnFalse:
                    return False
                
            return soundInputs
    
        except:
            print(traceback.format_exc())
            return False
        
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
                        
                        if speakers[channel][0].lower() == n["name"].lower():
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

class vbanTransmitterThread:
    def __init__(self, speakerType, toIp, deviceIndex, manualPort=False):

        self.speakerType = speakerType
        self.toIp = toIp
        self.deviceIndex = deviceIndex
        
        channels = sd.query_devices()[util.getInputs()[speakerType][2]]["max_input_channels"]
        if channels > 2:
            channels = 2
        
        if not manualPort:
            self.vbanObj = pyvban.utils.VBAN_Sender(
                receiver_ip=toIp,
                receiver_port=util.ports[speakerType],
                stream_name="Stream" + speakerType[0].upper() + speakerType[1:],
                sample_rate=48000,
                channels=channels,
                device_index=util.getInputs()[speakerType][2]
            )
        else:
            self.vbanObj = pyvban.utils.VBAN_Sender(
                receiver_ip=toIp,
                receiver_port=manualPort,
                stream_name="Stream" + speakerType[0].upper() + speakerType[1:],
                sample_rate=48000,
                channels=channels,
                device_index=util.getInputs()[speakerType][2]
            )
            self.vbanObj.sendingToVoicemeeter = True

        self.thread = threading.Thread(target=self.run)

    deviceIndex = -1
    isRunning = False
    hasStopped = False

    def run(self):
        self.isRunning = True
        self.id = random.randint(0, 9999999999)
        print("Starting stream with ID: " + str(self.id) + ", speakerType: " + self.speakerType + ", speaker, IP: " + self.toIp + ", deviceIndex: " + str(self.deviceIndex) + "...")
        
        self.vbanObj.run()

        print("Stream thread with id " + str(self.id) + " has exited.")
        self.hasStopped = True
        self.isRunning = False

    def start(self):
        if not (self.isRunning and self.hasStopped):
            self.thread.start()
        print("Transmitter stream has already been started.")

    def stop(self):
        self.vbanObj.stop()

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
            print("Receive stream has already been started.")

    def stop(self):
        self.vbanObj.stop()

class speaker:
    def __init__(self, speakerType, receiveFrom, sendTo):
        self.speakerType = speakerType
        self.receiveFrom = receiveFrom
        self.sendTo = sendTo

        self.mainThread = threading.Thread(target=self.main)
    
    receiverThread = False
    transmitterThread = False

    isRunning = False
    hasExited = False

    serverHostname = "127.0.0.1"

    lastUpdated = time.time()

    deviceIndex = 0

    exitf = False
    
    def settingsModified(self, doOnlyTransmit=False, doOnlyReceive=False):
        
        if not doOnlyTransmit:
            if self.receiverThread:
                self.receiverThread.stop()
        if not doOnlyReceive:
            if self.transmitterThread:
                self.transmitterThread.stop()

        if not doOnlyTransmit:
            try:
                while self.receiverThread.isRunning:
                    time.sleep(0.1)
            except:
                pass
            
        if not doOnlyReceive:
            try:
                while self.transmitterThread.isRunning:
                    time.sleep(0.1)
            except:
                pass

        if not doOnlyTransmit:
            doOverriteReceiver = False
            if self.receiveFrom != False:
                newReceiverThread = vbanReceiverThread(self.speakerType, self.receiveFrom, self.deviceIndex)
                newReceiverThread.start()
                doOverriteReceiver = True
        
        # if not doOnlyReceive:
        #     if self.serverHostname == self.sendTo:
        #         newTransmitterThread = vbanTransmitterThread(self.speakerType, self.sendTo, self.deviceIndex) # , manualPort=6980)
        #     else:
        #         newTransmitterThread = vbanTransmitterThread(self.speakerType, self.sendTo, self.deviceIndex)
        #     # newTransmitterThread.start()
        
        if not doOnlyTransmit:
            if doOverriteReceiver:
                self.receiverThread = newReceiverThread
        
        # if not doOnlyReceive:
        #     self.transmitterThread = newTransmitterThread

    def setSpeakerType(self, speakerType):
        self.speakerType = speakerType
    
    def setReceiveFromIp(self, receiveFrom):
        self.receiveFrom = receiveFrom
    
    def setSendToIp(self, sendTo):
        self.sendTo = sendTo

    def main(self):
        speakerTypeOld = False
        receiveFromOld = False
        sendToOld = False
        self.isRunning = True

        while (not self.exitf) and (not status.exitf):
            try:
                if self.receiverThread and self.transmitterThread:
                    jsonData = {
                        "receiveFrom": self.receiveFrom,
                        "sendTo": self.sendTo,
                        "info": {
                            "receiver": {
                                "deviceIndex": self.receiverThread.deviceIndex,
                                "isRunning": self.receiverThread.isRunning,
                                "hasStopped": self.receiverThread.hasStopped,
                                "lastActivityTimestamp": int(self.receiverThread.vbanObj.lastActivityTimestamp / 10) * 10,
                                "currentBufferSize": len(pyvban.utils.receiver.allf.packetBuffers[self.receiverThread.vbanObj._stream_name]["combined"]),
                                "lastReceived": int(self.receiverThread.vbanObj.lastReceived)
                            },
                            "transmitter": {
                                "deviceIndex": -1,
                                "isRunning": False,
                                "hasStopped": False,
                                "lastActivityTimestamp": 0,
                                "currentBufferSize": 0,
                                "sendingLatency": 0,
                                "senderThreadCount": 0,
                                "sendingToVoicemeeter": False
                            }
                        },
                        "lastUpdated": pytools.clock.getDateTime()[0:5] 
                    }
                else:
                    jsonData = {
                        "receiveFrom": self.receiveFrom,
                        "sendTo": self.sendTo,
                        "info": {
                            "receiver": {
                                "deviceIndex": None,
                                "isRunning": False,
                                "hasStopped": False,
                                "lastActivityTimestamp": 0,
                                "currentBufferSize": 0,
                                "lastReceived": 0
                            },
                            "transmitter": {
                                "deviceIndex": None,
                                "isRunning": False,
                                "hasStopped": False,
                                "lastActivityTimestamp": 0,
                                "currentBufferSize": 0,
                                "sendingLatency": 0,
                                "senderThreadCount": 0,
                                "sendingToVoicemeeter": False
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
                    print(self.receiveFrom)
                    receiveFromOld = copy.deepcopy(self.receiveFrom)
                    sendToOld = copy.deepcopy(self.sendTo)
                    
                    self.settingsModified()

                if (receiveFromOld != self.receiveFrom):
                    print("Receive Settings Modified!")
                    speakerTypeOld = copy.deepcopy(self.speakerType)
                    receiveFromOld = copy.deepcopy(self.receiveFrom)
                    
                    self.settingsModified(doOnlyReceive=True)
                
                if (sendToOld != self.sendTo):
                    print("Send Settings Modified!")
                    speakerTypeOld = copy.deepcopy(self.speakerType)
                    sendToOld = copy.deepcopy(self.sendTo)
                    
                    self.settingsModified(doOnlyTransmit=True)

            except:
                print(traceback.format_exc())

            self.lastUpdated = time.time()
            
            time.sleep(1)
        try:
            self.receiverThread.stop()
        except:
            print("Could not stop receiver thread, or has already stopped.")
        
        try:
            self.transmitterThread.stop()
        except:
            print("Could not stop transmitter thread, or has already stopped.")

        try:
            while self.receiverThread.isRunning:
                self.receiverThread.stop()
                time.sleep(0.1)
        except:
            pass

        try:
            while self.transmitterThread.isRunning:
                self.transmitterThread.stop()
                time.sleep(0.1)
        except:
            pass

        self.isRunning = False
        self.hasExited = True
        
    def run(self):
        print("Starting new speaker type " + self.speakerType + "...")
        self.mainThread.start()