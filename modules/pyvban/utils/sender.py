# import logging
import socket

import sounddevice as sd
import numpy
import traceback
import time
import threading
import random
import psutil
import math

from .. import VBANAudioHeader
from ..const import *
from ..subprotocols.audio.const import VBANSampleRatesSR2Enum, VBANBitResolution, VBANCodec

import modules.logManager as log

log.settings.debug = True

class allf:
    streamBuffers = {}
    senderUUIDs = {}
    cpuCount = 0
    threadCount = 0

def getCpuCount():
    if not allf.cpuCount:
        allf.cpuCount = psutil.cpu_count()
    return allf.cpuCount

class logging:

    DEBUG = False
    INFO = False

    def getLogger(*args):
        return logging._log()
    
    def basicConfig(*args):
        pass
    
    class _log:
        def __init__(self):
            pass

        def error(self, strf):
            log.printLog("error: " + str(strf))
        
        def info(self, strf):
            log.printLog(strf)

        def debug(self, strf):
            log.printLog(strf)

print = log.printLog

def intenseSleep(i):
    x = time.monotonic() + i
    while time.monotonic() < x:
        pass

class VBAN_Sender:
    def __init__(self, receiver_ip: str, receiver_port: int, stream_name: str, sample_rate: int, channels: int, device_index: int):
        try:
            
            getCpuCount()
            
            self._logger = logging.getLogger(f"VBAN_Sender_{receiver_ip}:{receiver_port}_{stream_name}")
            self._logger.info("Hellow world")

            self._receiver = (receiver_ip, receiver_port)
            self._stream_name = stream_name
            self._sample_rate = sample_rate
            self._vban_sample_rate = VBANSampleRatesSR2Enum[sample_rate]
            self._channels = channels
            self._device_index = device_index
            self._hasStopped = False

            self._uuid = random.random()
            allf.senderUUIDs[self._uuid] = [time.time(), self, False]
            self._uuidTimestampOld = allf.senderUUIDs[self._uuid][0]

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.connect(self._receiver)

            self._samples_per_frame = 256

            try:

                self._p = False

                self._stream = sd.InputStream(
                    dtype='int16',
                    channels=self._channels,
                    samplerate=self._sample_rate,
                    device=self._device_index
                )

                self._stream.start()

            except:
                self._p = False
                self._stream = sd.InputStream(
                    dtype='int16',
                    channels=self._channels,
                    samplerate=self._sample_rate,
                    device=self._device_index
                )

                self._stream.start()

            self._frame_counter = 0
        except:
            print(traceback.format_exc())
            self._hasStopped = True

    lastActivityTimestamp = time.time()
    packetTime = 0
    streamBuffer = []
    
    sendingToVoicemeeter = False
    
    previousError = ""  
    errorCounter = 0
    errorTime = 0
    lastOverflow = 0
    
    lastLoop = 0

    def _run_once_send(self, inArray, startRead):
        
        allf.threadCount = allf.threadCount + 1
        
        try:
            try:

                header = VBANAudioHeader(
                    sample_rate=self._vban_sample_rate,
                    samples_per_frame=self._samples_per_frame,
                    channels=self._channels,
                    format=VBANBitResolution.VBAN_BITFMT_16_INT,
                    codec=VBANCodec.VBAN_CODEC_PCM,
                    stream_name=self._stream_name,
                    frame_counter=int(math.floor((startRead * self._sample_rate) / self._samples_per_frame)),
                )

                data = header.to_bytes() + inArray[0].tobytes()
                # if len(data) != len(data[:VBAN_PROTOCOL_MAX_SIZE]):
                #     print("WARNING: Max packet size exceeded.")
                # data = data[:VBAN_PROTOCOL_MAX_SIZE]

                self._socket.sendto(data, self._receiver)

                _timeing = time.time()
                self.packetTime = _timeing - self.lastActivityTimestamp
                self.lastActivityTimestamp = _timeing

                self._frame_counter += 1
            
            except Exception as e:
                if inArray[0].tobytes(): 
                    allf.streamBuffers[self._uuid].append([inArray, int(math.floor((startRead * self._sample_rate) / self._samples_per_frame))])
                
                errorString = f"An exception occurred: {e}"
                if self.previousError != errorString:
                    print("Previous error occurred " + str(self.errorCounter) + " times. Most Recent at: " + str(self.errorTime))
                    self.previousError = errorString
                    self._logger.error(f"An exception occurred: {e}")
                    print(traceback.format_exc())
                else:
                    self.errorCounter = self.errorCounter + 1
                    self.errorTime = time.time()

                if errorString == "An exception occurred: [WinError 10038] An operation was attempted on something that is not a socket":
                    try:
                        try:
                            self._socket.shutdown(socket.SHUT_WR)
                        except:
                            print("Unnable to shutdown write socket.")
                        try:
                            self._socket.shutdown(socket.SHUT_RD)
                        except:
                            print("Unnable to shutdown read socket.")
                        try:
                            self._socket.close()
                        except:
                            print("Unnable to close socket.")
                        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        self._socket.connect(self._receiver)
                    except:
                        print(traceback.format_exc())
        
        except:
            print(traceback.format_exc())
            
        allf.threadCount = allf.threadCount - 1
    
    arrayBuffer = []
    
    def send_handler(self):
        while len(self.arrayBuffer) > 0:
            # if allf.threadCount < (allf.cpuCount * 20):
            #     threading.Thread(target=self._run_once_send, args=(self.arrayBuffer[0][0], self.arrayBuffer[0][1],)).start()
            #     self.arrayBuffer.pop(0)
            # else:
            self._run_once_send(self.arrayBuffer[0][0], self.arrayBuffer[0][1])
            self.arrayBuffer.pop(0)
    
    def run_once(self):

        if allf.senderUUIDs[self._uuid][0] != self._uuidTimestampOld:
            self.stop()
            return

        allf.senderUUIDs[self._uuid][0] = time.time()
        self._uuidTimestampOld = allf.senderUUIDs[self._uuid][0]

        try:
            streamTime = time.monotonic()
            
            self.arrayBuffer.append([self._stream.read(self._samples_per_frame), streamTime])

        except Exception as e:
            errorString = f"An exception occurred: {e}"
            print(traceback.format_exc())

            if errorString == "An exception occurred: Stream is stopped [PaErrorCode -9983]":
                try:
                    self._stream.stop()
                except:
                    pass

                self._stream = sd.InputStream(
                    dtype='int16',
                    channels=self._channels,
                    samplerate=self._sample_rate,
                    device=self._device_index
                )

                self._stream.start()

    def run_many(self):
        if allf.senderUUIDs[self._uuid][0] != self._uuidTimestampOld:
            self.stop()
            return

        allf.senderUUIDs[self._uuid][0] = time.time()
        self._uuidTimestampOld = allf.senderUUIDs[self._uuid][0]

        try:
            while len(allf.streamBuffers[self._uuid]) > 1:
                
                header = VBANAudioHeader(
                    sample_rate=self._vban_sample_rate,
                    samples_per_frame=self._samples_per_frame,
                    channels=self._channels,
                    format=VBANBitResolution.VBAN_BITFMT_16_INT,
                    codec=VBANCodec.VBAN_CODEC_PCM,
                    stream_name=self._stream_name,
                    frame_counter=allf.streamBuffers[self._uuid][0][1],
                )
                
                data = header.to_bytes() + allf.streamBuffers[self._uuid][0][0][0].tobytes()
                data = data[:VBAN_PROTOCOL_MAX_SIZE]

                self._socket.sendto(data, self._receiver)

                self.lastActivityTimestamp = time.time()

                allf.streamBuffers[self._uuid].pop(0)
                self._frame_counter += 1
        except Exception as e:
            errorString = f"An exception occurred: {e}"
            if self.previousError != errorString:
                print("Previous error occurred " + str(self.errorCounter) + " times. Most Recent at: " + str(self.errorTime))
                self.previousError = errorString
                self._logger.error(f"An exception occurred: {e}")
                print(traceback.format_exc())
            else:
                self.errorCounter = self.errorCounter + 1
                self.errorTime = time.time()

            if errorString == "An exception occurred: Stream is stopped [PaErrorCode -9983]":
                try:
                    self._stream.stop()
                except:
                    pass

                self._stream = sd.InputStream(
                    dtype='int16',
                    channels=self._channels,
                    samplerate=self._sample_rate,
                    device=self._device_index
                )

                self._stream.start()

            if errorString == "An exception occurred: [WinError 10038] An operation was attempted on something that is not a socket":
                try:
                    try:
                        self._socket.shutdown(socket.SHUT_WR)
                    except:
                        print("Unnable to shutdown write socket.")
                    try:
                        self._socket.shutdown(socket.SHUT_RD)
                    except:
                        print("Unnable to shutdown read socket.")
                    try:
                        self._socket.close()
                    except:
                        print("Unnable to close socket.")
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._socket.connect(self._receiver)
                except:
                    print(traceback.format_exc())

    def run(self):
        allf.streamBuffers[self._uuid] = []
        self._running = True
        allf.senderUUIDs[self._uuid][2] = True
        lastLoop = time.time()
        if not self.sendingToVoicemeeter:
            pass
        
        socketHandlerThread = threading.Thread(target=self.runSocket)
        socketHandlerThread.start()
        
        while self._running and allf.senderUUIDs[self._uuid][2]:
            # while len(allf.streamBuffers[self._uuid]) > 1:
            #     threading.Thread(target=print, args=("Running many...",)).start()
            #     self.run_many()
            self.run_once()
            
        self._hasStopped = True
        self.stop()
    
    def runSocket(self):
        while self._running and allf.senderUUIDs[self._uuid][2]:
            initSendTime = time.monotonic()
            self.send_handler()
            intenseSleep((self._samples_per_frame / self._sample_rate) - (time.monotonic() - initSendTime))
            
        self._hasStopped = True
        self.stop()

    def stop(self):
        self._running = False
        allf.senderUUIDs[self._uuid][2] = False
        self._stream.stop()
        try:
            self._socket.shutdown(socket.SHUT_WR)
        except:
            print("Unnable to shutdown write socket.")
        try:
            self._socket.shutdown(socket.SHUT_RD)
        except:
            print("Unnable to shutdown read socket.")
        try:
            self._socket.close()
        except:
            print("Unnable to close socket.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog='VBAN_Sender', description='Python based VBAN streamer')
    parser.add_argument('-a', '--address', required=True, type=str)
    parser.add_argument('-p', '--port', default=6980, type=int)
    parser.add_argument('-s', '--stream', default="Stream1", type=str)
    parser.add_argument('-r', '--rate', default=48000, type=int)
    parser.add_argument('-c', '--channels', default=2, type=int)
    parser.add_argument('-d', '--device', default=-1, required=True, type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    sender = VBAN_Sender(
        receiver_ip=args.address,
        receiver_port=args.port,
        stream_name=args.stream,
        sample_rate=args.rate,
        channels=args.channels,
        device_index=args.device
    )
    sender.run()
