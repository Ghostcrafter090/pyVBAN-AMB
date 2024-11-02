import modules.logManager as log

log.settings.debug = True

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

def device_list():

    logger = logging.getLogger(f"device_list")
    import pyaudio
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    logger.info(f"Input:")
    for i in range(info.get('deviceCount')):
        dev = p.get_device_info_by_host_api_device_index(0, i)
        if dev["maxInputChannels"] > 0:
            logger.info(f"\t{i} - {dev.get('name')}")
    logger.info(f"Output:")
    for i in range(info.get('deviceCount')):
        dev = p.get_device_info_by_host_api_device_index(0, i)
        if dev["maxOutputChannels"] > 0:
            logger.info(f"\t{i} - {dev.get('name')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    device_list()
