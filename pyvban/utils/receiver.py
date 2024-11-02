import socket

import sounddevice as sd
import numpy
import traceback
import time
import threading
import random
import os

from ..packet import VBANPacket
from ..const import *
from ..subprotocols.audio.const import VBANSampleRatesEnum2SR

import modules.logManager as log

log.settings.debug = True

class allf:
    packetBuffers = {}
    receiverUUIDs = {}

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

def pcm2float(sig, dtype='float32') -> numpy.ndarray:
    """Convert PCM signal to floating point with a range from -1 to 1.
    Use dtype='float32' for single precision.
    Parameters
    ----------
    sig : array_like
        Input array, must have integral type.
    dtype : data type, optional
        Desired (floating point) data type.
    Returns
    -------
    numpy.ndarray
        Normalized floating point data.
    See Also
    --------
    float2pcm, dtype
    """
    sig = numpy.asarray(sig)
    if sig.dtype.kind not in 'iu':
        raise TypeError("'sig' must be an array of integers")
    dtype = numpy.dtype(dtype)
    if dtype.kind != 'f':
        raise TypeError("'dtype' must be a floating point type")

    i = numpy.iinfo(sig.dtype)
    abs_max = 2 ** (i.bits - 1)
    offset = i.min + abs_max
    return (sig.astype(dtype) - offset) / abs_max

class VBAN_Receiver:
    def __init__(self, sender_ip: str, stream_name: str, port: int, device_index: int):
        try:
            self._logger = logging.getLogger(f"VBAN_Receiver_{sender_ip}_{port}_{stream_name}")
            self._logger.info("Hellow world")

            self._sender_ip = sender_ip
            self._stream_name = stream_name
            self._device_index = device_index
            self._hasStopped = False
            self._networkHasStopped = False
            self._streamHasStopped = False

            self._uuid = random.random()
            allf.receiverUUIDs[self._uuid] = [time.time(), time.time(), self, False]
            self._uuidTimestampNetworkOld = allf.receiverUUIDs[self._uuid][0]
            self._uuidTimestampStreamOld = allf.receiverUUIDs[self._uuid][1]
            

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("0.0.0.0", port))
            self._port = port

            self._p = False # pyaudio.PyAudio()
            self._current_pyaudio_config = {
                "channels": 2,
                "rate": 48000
            }
            
            # self._stream = self._p.open(
            #     format=self._p.get_format_from_width(2), 
            #     channels=self._current_pyaudio_config["channels"],
            #     rate=self._current_pyaudio_config["rate"],
            #     output=True,
            #     output_device_index=self._device_index
            # )

            self._stream = sd.OutputStream(
            dtype='int16',
                channels=self._current_pyaudio_config["channels"],
                device=self._device_index,
                samplerate=self._current_pyaudio_config["rate"]
            )

            self._running = False

            self._stream.start()
        
        except:
            self._networkHasStopped = True
            self._streamHasStopped = True
            try:
                self.stop()
            except:
                pass
            print(traceback.format_exc())
    
    lastActivityTimestamp = time.time()
    lastStreamActivityTimestamp = time.time()
    
    samplesPerFrame = 128
    
    packetBuffer = []

    def _check_pyaudio(self, header):
        if VBANSampleRatesEnum2SR[header.sample_rate] != self._current_pyaudio_config["rate"] or header.channels != self._current_pyaudio_config["channels"]:
            self._logger.info("Re-Configuring PyAudio")
            self._current_pyaudio_config["rate"] = VBANSampleRatesEnum2SR[header.sample_rate]
            self._current_pyaudio_config["channels"] = header.channels
            self.samplesPerFrame = header.samples_per_frame
            self._stream.stop()
            self._stream = sd.OutputStream(
                dtype='int16',
                channels=self._current_pyaudio_config["channels"],
                device=self._device_index,
                samplerate=self._current_pyaudio_config["rate"]
            )

            self._stream.start()

    def run_once(self):
        if allf.receiverUUIDs[self._uuid][0] != self._uuidTimestampNetworkOld:
            self.stop()
            return

        allf.receiverUUIDs[self._uuid][0] = time.time()
        self._uuidTimestampNetworkOld = allf.receiverUUIDs[self._uuid][0]

        try:
            data, addr = self._socket.recvfrom(VBAN_PROTOCOL_MAX_SIZE)
            packet = VBANPacket(data)
            if packet.header:
                if packet.header.sub_protocol != VBANProtocols.VBAN_PROTOCOL_AUDIO:
                    self._logger.debug(f"Received non audio packet {packet}")
                    return
                if packet.header.stream_name != self._stream_name:
                    self._logger.debug(f"Unexpected stream name \"{packet.header.stream_name}\" != \"{self._stream_name}\"")
                    return
                if addr[0] != self._sender_ip:
                    self._logger.debug(f"Unexpected sender \"{addr[0]}\" != \"{self._sender_ip}\"")
                    return

                self._check_pyaudio(packet.header)

                outArray = numpy.array(list(zip(numpy.frombuffer(packet.data, dtype=numpy.int16)[0::2], numpy.frombuffer(packet.data, dtype=numpy.int16)[1::2])))
                allf.packetBuffers[self._stream_name].append(outArray)
                
        except Exception as e:
            print(traceback.format_exc())
            errorString = f"An exception occurred: {e}"
            self._logger.error(f"An exception occurred: {e}")

            if errorString == "An exception occurred: [WinError 10038] An operation was attempted on something that is not a socket":
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
                    
                # self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.bind(("0.0.0.0", self._port))

    def run(self):
        allf.packetBuffers[self._stream_name] = []
        self._running = True
        threading.Thread(target=self.runStream).start()
        try:
            while self._running:
                self.run_once()
                self.lastActivityTimestamp = time.time()
        except:
            print(traceback.format_exc())
        self.stop("network")
        
    def runStream(self):
        try:
            while self._running:

                if allf.receiverUUIDs[self._uuid][1] != self._uuidTimestampStreamOld:
                    self.stop()
                    return

                allf.receiverUUIDs[self._uuid][1] = time.time()
                self._uuidTimestampStreamOld = allf.receiverUUIDs[self._uuid][1]

                try:
                    if len(allf.packetBuffers[self._stream_name]) > 1:
                        self._stream.write(allf.packetBuffers[self._stream_name][0])
                        allf.packetBuffers[self._stream_name].pop(0)
                    else:
                        waitTime = time.time() + 1
                        print("Buffer underrun for " + str(self._stream_name) + " detected. Network thread running status: " + str(not self._networkHasStopped) + ". Collecting samples...")
                        if not os.path.exists("stream_buffer_underrun"):
                            log.pytools.IO.saveFile("stream_buffer_underrun", "")
                        samplesToCollect = ((self._current_pyaudio_config["rate"] / self.samplesPerFrame) * 1)
                        while (len(allf.packetBuffers[self._stream_name]) < samplesToCollect) and (waitTime > time.time()):
                            self.lastStreamActivityTimestamp = time.time()
                            time.sleep(0.1)
                
                except Exception as e:
                    print(traceback.format_exc())
                    errorString = f"An exception occurred: {e}"
                    self._logger.error(f"An exception occurred: {e}")

                    if errorString == "An exception occurred: Stream is stopped [PaErrorCode -9983]":
                        try:
                            self._stream.stop()
                        except:
                            pass

                        self._stream = sd.OutputStream(
                            dtype='int16',
                            channels=self._current_pyaudio_config["channels"],
                            device=self._device_index,
                            samplerate=self._current_pyaudio_config["rate"]
                        )

                        self._stream.start()
                
                self.lastStreamActivityTimestamp = time.time()
        except:
            print(traceback.format_exc())
        self.stop("stream")

    def stop(self, typef=False):
        if typef == "stream":
            self._streamHasStopped = True
        elif typef == "network":
            self._networkHasStopped = True
        
        if self._networkHasStopped and self._streamHasStopped:
            self._hasStopped = True

        self._running = False
        try:
            self._stream.stop()
        except:
            print("Count not close sound stream.")
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
        # self._stream = None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog='VBAN_Receiver', description='Python based VBAN receiver')
    parser.add_argument('-a', '--address', required=True, type=str)
    parser.add_argument('-p', '--port', default=6980, type=int)
    parser.add_argument('-s', '--stream', default="Stream1", type=str)
    parser.add_argument('-d', '--device', default=-1, required=True, type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    sender = VBAN_Receiver(
        sender_ip=args.address,
        stream_name=args.stream,
        port=args.port,
        device_index=args.device
    )
    sender.run()
